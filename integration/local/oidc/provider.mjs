// Disposable integration provider. No persistent accounts or registration data.
import https from 'node:https';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { Provider, errors } from 'oidc-provider';

const issuer = process.env.LAB_ISSUER;
const resource = process.env.LAB_RESOURCE;
const accounts = JSON.parse(process.env.LAB_ACCOUNTS);
const provider = new Provider(issuer, {
  jwks: JSON.parse(fs.readFileSync(process.env.LAB_JWKS, 'utf8')),
  clients: [],
  cookies: { keys: [crypto.randomBytes(32).toString('hex')] },
  claims: { openid: ['sub'] },
  scopes: ['openid', 'offline_access', 'books:read'],
  pkce: { required: () => true },
  features: {
    devInteractions: { enabled: false },
    registration: { enabled: true },
    resourceIndicators: {
      enabled: true,
      defaultResource: () => resource,
      useGrantedResource: () => true,
      getResourceServerInfo: async (_ctx, requested) => {
        if (requested !== resource) throw new errors.InvalidTarget();
        return { scope: 'books:read', audience: resource, accessTokenFormat: 'jwt',
          accessTokenTTL: 300, jwt: { sign: { alg: 'RS256' } } };
      },
    },
  },
  findAccount: async (_ctx, id) => accounts[id] ? {
    accountId: id, claims: async () => ({ sub: id }),
  } : undefined,
  interactions: { url: (_ctx, interaction) => `/interaction/${interaction.uid}` },
});

const callback = provider.callback();
const server = https.createServer({
  cert: fs.readFileSync(process.env.LAB_TLS_CERT),
  key: fs.readFileSync(process.env.LAB_TLS_KEY),
}, async (req, res) => {
  try {
    if (!req.url.startsWith('/interaction/')) return callback(req, res);
    const interaction = await provider.interactionDetails(req, res);
    res.setHeader('Cache-Control', 'no-store');
    if (req.method === 'GET') {
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ prompt: interaction.prompt.name }));
      return;
    }
    // Cookie-bound interaction plus same-origin form submission. This endpoint
    // is test UI only, but it still authenticates passwords and requires consent.
    if (req.headers.origin !== issuer) { res.writeHead(403).end(); return; }
    let body = '';
    for await (const chunk of req) {
      body += chunk;
      if (body.length > 8192) { res.writeHead(413).end(); return; }
    }
    const fields = new URLSearchParams(body);
    if (interaction.prompt.name === 'login') {
      const user = fields.get('username');
      const expected = accounts[user];
      const supplied = fields.get('password') || '';
      if (!expected || Buffer.byteLength(expected) !== Buffer.byteLength(supplied) ||
          !crypto.timingSafeEqual(Buffer.from(expected), Buffer.from(supplied))) {
        res.writeHead(401).end(); return;
      }
      await provider.interactionFinished(req, res, { login: { accountId: user } }, { mergeWithLastSubmission: false });
    } else if (interaction.prompt.name === 'consent' && fields.get('approve') === 'yes') {
      const grant = interaction.grantId ? await provider.Grant.find(interaction.grantId)
        : new provider.Grant({ accountId: interaction.session.accountId, clientId: interaction.params.client_id });
      const details = interaction.prompt.details;
      if (details.missingOIDCScope) grant.addOIDCScope(details.missingOIDCScope.join(' '));
      if (details.missingOIDCClaims) grant.addOIDCClaims(details.missingOIDCClaims);
      for (const [indicator, scopes] of Object.entries(details.missingResourceScopes || {})) {
        grant.addResourceScope(indicator, scopes.join(' '));
      }
      const grantId = await grant.save();
      await provider.interactionFinished(req, res, { consent: { grantId } }, { mergeWithLastSubmission: true });
    } else { res.writeHead(400).end(); }
  } catch (error) {
    // Avoid logging tokens, interaction identifiers, cookies or passwords.
    console.error(error.name);
    if (!res.headersSent) res.writeHead(500);
    res.end();
  }
});
server.listen(Number(new URL(issuer).port), '127.0.0.1');
