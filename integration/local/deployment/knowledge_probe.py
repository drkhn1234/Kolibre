"""Public HTTPS native + predefined OIDC/S256 real MCP retrieval, no secret output."""

import asyncio
import base64
import hashlib
import json
import secrets
import time
from urllib.parse import urlencode, urlsplit, parse_qs

import httpx
from fastmcp import Client
from deployment.validate import RemoteLab, ROOT
from deployment.client_support import keycloak_browser


def oidc(lab, who):
    c = json.loads((ROOT / "runtime/chatgpt-client.json").read_text())
    verifier = secrets.token_urlsafe(48)
    state = secrets.token_urlsafe(24)
    with httpx.Client(timeout=30, trust_env=False) as http:
        meta = http.get(lab.issuer + "/.well-known/openid-configuration").json()
        url = (
            meta["authorization_endpoint"]
            + "?"
            + urlencode(
                {
                    "client_id": c["client_id"],
                    "redirect_uri": c["redirect_uri"],
                    "response_type": "code",
                    "scope": "openid books:read",
                    "resource": lab.mcp_url,
                    "state": state,
                    "code_challenge_method": "S256",
                    "code_challenge": base64.urlsafe_b64encode(
                        hashlib.sha256(verifier.encode()).digest()
                    )
                    .rstrip(b"=")
                    .decode(),
                }
            )
        )
        callback = keycloak_browser(lab, url, who)
        assert callback.startswith(c["redirect_uri"] + "?")
        qs = parse_qs(urlsplit(callback).query)
        assert qs["state"] == [state] and qs["iss"] == [lab.issuer]
        r = http.post(
            meta["token_endpoint"],
            data={
                "grant_type": "authorization_code",
                "client_id": c["client_id"],
                "client_secret": c["client_secret"],
                "redirect_uri": c["redirect_uri"],
                "code": qs["code"][0],
                "code_verifier": verifier,
                "resource": lab.mcp_url,
            },
        )
        assert r.status_code == 200
        return r.json()["access_token"]


async def main():
    lab = RemoteLab()
    lab.restore()
    lab.login("founder")
    lab.login("sister")
    for auth in ("native", "oidc"):
        tokens = (
            lab.tokens
            if auth == "native"
            else {w: oidc(lab, w) for w in ("founder", "sister")}
        )
        async with (
            Client(lab.mcp_url, auth=tokens["founder"]) as f,
            Client(lab.mcp_url, auth=tokens["sister"]) as s,
        ):
            tools = {t.name for t in await f.list_tools()}
            assert len(tools) == 5 and "kolibre_semantic_search" in tools

            async def call(c, **args):
                t = time.monotonic()
                r = (
                    await c.call_tool(
                        "kolibre_semantic_search", {"query": "quasar", **args}
                    )
                ).data
                assert r["pending_books"] == 0
                print(
                    auth,
                    "query seconds",
                    round(time.monotonic() - t, 3),
                    "results",
                    len(r["results"]),
                )
                return r

            a, b = await asyncio.gather(call(f), call(s))
            for who, data in [("founder", a), ("sister", b)]:
                allowed = {"shared", lab.private[who]}
                assert {r["library"] for r in data["results"]} <= allowed
                assert any(
                    r["kind"] == "passage" and r.get("source_sha256")
                    for r in data["results"]
                )
                assert any(r["kind"] == "annotation" for r in data["results"])
                other = "sister" if who == "founder" else "founder"
                assert other + "-secret-note" not in json.dumps(data)
            for c, other in [(f, "sister"), (s, "founder")]:
                denied = await c.call_tool(
                    "kolibre_semantic_search",
                    {"query": "quasar", "library": lab.private[other]},
                    raise_on_error=False,
                )
                assert denied.is_error
            try:
                lab.ok(
                    "PUT",
                    "/api/kolibre/libraries/shared/permessi",
                    json={"user_id": lab.sister["id"], "revoca": True},
                )
                denied = await s.call_tool(
                    "kolibre_semantic_search",
                    {"query": "quasar", "library": "shared"},
                    raise_on_error=False,
                )
                assert denied.is_error
                assert all(
                    r["library"] == lab.private["sister"]
                    for r in (await call(s))["results"]
                )
                async with Client(lab.mcp_url, auth=tokens["sister"]) as again:
                    assert all(
                        r["library"] == lab.private["sister"]
                        for r in (await call(again))["results"]
                    )
            finally:
                lab.ok(
                    "PUT",
                    "/api/kolibre/libraries/shared/permessi",
                    json={
                        "user_id": lab.sister["id"],
                        "can_edit": True,
                        "can_upload": True,
                    },
                )
            assert any(r["library"] == "shared" for r in (await call(s))["results"])
            # Existing four operations still usable alongside the opt-in fifth.
            await s.call_tool("kolibre_list_books", {"library": "shared"})
            await s.call_tool("kolibre_my_annotations")
        print(
            auth,
            "five-tool retrieval, own notes, foreign denial, live revoke/reconnect/restore: PASS",
        )


if __name__ == "__main__":
    asyncio.run(main())
