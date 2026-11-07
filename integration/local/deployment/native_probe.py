"""Root-only loopback smoke check. Never print credentials or access tokens."""

import asyncio
import json
import time
from pathlib import Path

import httpx
from fastmcp import Client
from jose import jwt

credentials = json.loads(Path("/etc/kolibre-stage/credentials.json").read_text())
with httpx.Client(
    base_url="http://127.0.0.1:18081", trust_env=False, timeout=15
) as http:
    before = time.time()
    response = http.post(
        "/token",
        data={
            "username": "founder",
            "password": credentials["native_passwords"]["founder"],
        },
    )
    assert response.status_code == 200, response.status_code
    token = response.json()["access_token"]
    claims = jwt.decode(token, credentials["native_signing_key"], algorithms=["HS256"])
    assert claims["sub"] == "founder" and 895 < claims["exp"] - before < 905
    response = http.get("/api/users/me", headers={"Authorization": "Bearer " + token})
    assert response.status_code == 200 and response.json()["username"] == "founder"
    assert http.get("/api/users/me").status_code == 401


async def check():
    async with Client("http://127.0.0.1:18082/mcp", auth=token) as client:
        names = sorted(tool.name for tool in await client.list_tools())
        assert names == [
            "kolibre_list_books",
            "kolibre_list_libraries",
            "kolibre_my_annotations",
            "kolibre_search_fulltext",
        ]
        assert not (await client.call_tool("kolibre_list_libraries")).is_error
        print(
            json.dumps(
                {
                    "native_identity": "founder",
                    "native_lifetime_minutes": 15,
                    "anonymous_rejected": True,
                    "tools": names,
                    "invocation": "passed",
                }
            )
        )


asyncio.run(check())
