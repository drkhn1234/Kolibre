"""Signed OIDC identity binding never confers another Kolibre user's access."""
import base64
import json
import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import httpx
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from jose import jwt
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import auth, models


ISSUER = "https://login.example.test/realms/books"
AUDIENCE = "kolibre-mcp"
JWKS_URI = ISSUER + "/protocol/openid-connect/certs"


def _base64url(num: int) -> str:
    raw = num.to_bytes((num.bit_length() + 7) // 8, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


class OIDCUserIdentityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.pem = cls.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        )
        pub = cls.private_key.public_key().public_numbers()
        cls.jwks = {"keys": [{
            "kid": "key-1", "kty": "RSA", "alg": "RS256", "use": "sig",
            "n": _base64url(pub.n), "e": _base64url(pub.e),
        }]}

    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            models.User(
                id=1, username="founder", hashed_password="unused",
                is_admin=True, is_founder=True,
                oidc_issuer=ISSUER, oidc_subject="external-founder",
            ),
            models.User(
                id=2, username="sister", hashed_password="unused",
                oidc_issuer=ISSUER, oidc_subject="external-sister",
            ),
        ])
        self.db.commit()
        self.env = patch.dict(os.environ, {
            "KOLIBRE_OIDC_ISSUER": ISSUER,
            "KOLIBRE_OIDC_AUDIENCE": AUDIENCE,
            "KOLIBRE_OIDC_JWKS_URI": JWKS_URI,
        })
        self.env.start()
        self.addCleanup(self.env.stop)

        real_httpx_client = httpx.Client

        def fake_client(*args, **kwargs):
            transport = httpx.MockTransport(
                lambda req: httpx.Response(200, json=self.jwks)
                if str(req.url) == JWKS_URI else httpx.Response(404)
            )
            return real_httpx_client(transport=transport, **{
                k: v for k, v in kwargs.items() if k != "transport"
            })

        self.mock_http = patch("app.services.oidc_identity.httpx.Client", side_effect=fake_client)
        self.mock_http.start()
        self.addCleanup(self.mock_http.stop)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def signed(self, *, sub="external-sister", iss=ISSUER, aud=AUDIENCE, exp=3600, scope="openid books:read"):
        return jwt.encode({
            "sub": sub, "iss": iss, "aud": aud, "scope": scope,
            "exp": datetime.now(timezone.utc) + timedelta(seconds=exp),
        }, self.pem, algorithm="RS256", headers={"kid": "key-1"})

    def test_valid_external_sister_maps_to_sister_not_founder(self):
        identity = auth._decode_token(self.signed(), self.db)
        self.assertEqual(identity.id, 2)
        self.assertFalse(identity.is_founder)

    def test_verified_unlinked_subject_never_autocreates_or_guesses_by_username(self):
        with self.assertRaises(HTTPException) as ctx:
            auth._decode_token(self.signed(sub="sister"), self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(self.db.query(models.User).count(), 2)

    def test_wrong_audience_issuer_expired_and_unsigned_are_all_rejected(self):
        for token in [
            self.signed(aud="another-service"),
            self.signed(iss="https://evil.example.test"),
            self.signed(exp=-60),
            jwt.encode({"sub": "external-sister"}, "wrong", algorithm="HS256"),
        ]:
            with self.subTest(token=token[:12]):
                with self.assertRaises(HTTPException) as ctx:
                    auth._decode_token(token, self.db)
                self.assertEqual(ctx.exception.status_code, 401)

    def test_missing_insufficient_or_malformed_scope_is_rejected(self):
        for scope in (None, "", "openid", "books:read:all", ["books:read"]):
            with self.subTest(scope=scope):
                with self.assertRaises(HTTPException) as ctx:
                    auth._decode_token(self.signed(scope=scope), self.db)
                self.assertEqual(ctx.exception.status_code, 401)

    def test_tampering_subject_invalidates_signature(self):
        token = self.signed()
        h, p, sig = token.split(".")
        data = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4)))
        data["sub"] = "external-founder"
        p2 = base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
        with self.assertRaises(HTTPException):
            auth._decode_token(f"{h}.{p2}.{sig}", self.db)

    def test_access_token_requires_explicit_audience(self):
        claims = jwt.get_unverified_claims(self.signed())
        del claims["aud"]
        token = jwt.encode(claims, self.pem, algorithm="RS256", headers={"kid": "key-1"})
        with self.assertRaises(HTTPException) as ctx:
            auth._decode_token(token, self.db)
        self.assertEqual(ctx.exception.status_code, 401)

    def test_oidc_is_disabled_without_required_server_configuration(self):
        with patch.dict(os.environ, {"KOLIBRE_OIDC_ISSUER": ""}):
            with self.assertRaises(HTTPException):
                auth._decode_token(self.signed(), self.db)

    def test_account_linking_requires_password_and_the_same_authenticated_owner(self):
        from app.api import users
        sister = self.db.query(models.User).filter_by(id=2).one()
        sister.hashed_password = auth.get_password_hash("sister-password")
        sister.oidc_issuer = None
        sister.oidc_subject = None
        self.db.commit()
        invalid = users.OIDCLinkRequest(
            password="wrong-password", oidc_access_token=self.signed()
        )
        with self.assertRaises(HTTPException) as ctx:
            users.link_my_oidc_account(invalid, db=self.db, current_user=sister)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertIsNone(sister.oidc_subject)

        valid = users.OIDCLinkRequest(
            password="sister-password", oidc_access_token=self.signed()
        )
        result = users.link_my_oidc_account(valid, db=self.db, current_user=sister)
        self.assertTrue(result["linked"])
        self.assertEqual(sister.oidc_subject, "external-sister")

        # Founder cannot take over sister's OIDC identity via the app.
        founder = self.db.query(models.User).filter_by(id=1).one()
        founder.hashed_password = auth.get_password_hash("founder-password")
        founder.oidc_issuer = None
        founder.oidc_subject = None
        self.db.commit()
        take_over = users.OIDCLinkRequest(
            password="founder-password", oidc_access_token=self.signed()
        )
        with self.assertRaises(HTTPException) as ctx:
            users.link_my_oidc_account(take_over, db=self.db, current_user=founder)
        self.assertEqual(ctx.exception.status_code, 409)

    def test_native_login_only_for_credential_linking_and_password_unlink(self):
        from app.api import users
        sister = self.db.query(models.User).filter_by(id=2).one()
        sister.hashed_password = auth.get_password_hash("sister-password")
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            auth.get_current_native_user(token=self.signed(), db=self.db)
        self.assertEqual(ctx.exception.status_code, 401)
        native_token = auth.create_access_token(
            {"sub": "sister"}, expires_delta=timedelta(minutes=5),
        )
        self.assertEqual(auth.get_current_native_user(token=native_token, db=self.db).id, 2)
        with self.assertRaises(HTTPException):
            users.unlink_my_oidc_account(
                users.NativePasswordRequest(password="wrong"),
                db=self.db, current_user=sister,
            )
        response = users.unlink_my_oidc_account(
            users.NativePasswordRequest(password="sister-password"),
            db=self.db, current_user=sister,
        )
        self.assertFalse(response["linked"])
        self.assertIsNone(sister.oidc_subject)

    def test_legacy_kolibre_login_still_works(self):
        token = auth.create_access_token(
            {"sub": "sister"}, expires_delta=timedelta(minutes=5),
        )
        self.assertEqual(auth._decode_token(token, self.db).id, 2)


if __name__ == "__main__":
    unittest.main()
