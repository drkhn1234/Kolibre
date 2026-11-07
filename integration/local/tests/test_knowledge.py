"""Actual CPU embeddings + HTTP MCP + current Kolibre ACL; disposable books."""

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from fastmcp import Client
from test_live_native import ROOT, TOOLS, stack, populated, epub


def index(lab):
    subprocess.run(
        [sys.executable, "-m", "backend.app.services.knowledge", "--once"],
        env=lab.env,
        cwd=lab.directory,
        check=True,
        timeout=120,
    )


@pytest.mark.asyncio
async def test_hybrid_mcp_privacy_and_lifecycle(populated):
    lab = populated
    lab.backend.terminate()
    lab.backend.wait(timeout=15)
    lab.env["KOLIBRE_KNOWLEDGE_ENABLED"] = "1"
    lab.env["KOLIBRE_MCP_KNOWLEDGE_ENABLED"] = "1"
    cache = lab.directory / "data/embedding-models"
    (ROOT / "runtime/embedding-models").mkdir(parents=True, exist_ok=True)
    cache.symlink_to(ROOT / "runtime/embedding-models", target_is_directory=True)
    lab.start_backend()
    index(lab)
    lab.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], lab.bridge_port)
    async with (
        Client(lab.mcp_url, auth=lab.tokens["founder"]) as f,
        Client(lab.mcp_url, auth=lab.tokens["sister"]) as s,
    ):
        assert {t.name for t in await f.list_tools()} == TOOLS | {
            "kolibre_semantic_search"
        }

        async def call(c, **args):
            return (
                await c.call_tool(
                    "kolibre_semantic_search", {"query": "quasar", **args}
                )
            ).data

        a, b = await asyncio.gather(call(f), call(s))
        assert a["pending_books"] == b["pending_books"] == 0
        assert "sister" not in json.dumps(a)
        assert "founder private" not in json.dumps(b)
        assert any(r["kind"] == "annotation" for r in b["results"])
        assert any(
            r.get("section") == "chapter.xhtml" and r.get("source_sha256")
            for r in b["results"]
        )
        for c, other in [(f, "sister"), (s, "founder")]:
            with pytest.raises(Exception, match="Library not found"):
                await call(c, library=lab.private[other])
        # Existing-session revocation: no shared results including own shared notes.
        lab.ok(
            "PUT",
            "/api/kolibre/libraries/shared/permessi",
            json={"user_id": lab.sister["id"], "revoca": True},
        )
        b = await call(s)
        assert all(r["library"] == lab.private["sister"] for r in b["results"])
        with pytest.raises(Exception):
            await call(s, library="shared")
    async with Client(lab.mcp_url, auth=lab.tokens["sister"]) as s:
        result = (
            await s.call_tool("kolibre_semantic_search", {"query": "quasar"})
        ).data
        assert all(r["library"] == lab.private["sister"] for r in result["results"])
    # Change file after indexing: stale passages are suppressed until worker catches up.
    import sqlite3

    private = lab.directory / "data/libraries" / lab.private["sister"]
    files = list(private.rglob("*.epub"))
    assert len(files) == 1
    files[0].write_bytes(
        epub("replacement", "Electrical impulses travel between nerve cells.")
    )
    r = lab.ok(
        "GET",
        "/api/kolibre/knowledge/search",
        who="sister",
        params={"q": "quasar", "include_annotations": False},
    )
    assert r["results"] == [] and r["pending_books"] == 1
    index(lab)
    r = lab.ok(
        "GET",
        "/api/kolibre/knowledge/search",
        who="sister",
        params={
            "q": "How do neurons communicate?",
            "mode": "semantic",
            "include_annotations": False,
        },
    )
    assert "Electrical impulses" in r["results"][0]["text"]
    assert r["results"][0]["word_start"] == 0
    # API citation is an actual authenticated book download.
    assert (
        lab.request("GET", r["results"][0]["source_url"], who="sister").status_code
        == 200
    )
    files[0].unlink()
    assert (
        lab.ok(
            "GET",
            "/api/kolibre/knowledge/search",
            who="sister",
            params={"q": "neurons", "include_annotations": False},
        )["results"]
        == []
    )
    index(lab)
    with sqlite3.connect(private / "knowledge.sqlite3") as db:
        assert db.execute("select count(*) from passages").fetchone()[0] == 0

    # Actual shared -> founder-private move: stale shared index cannot leak.
    lab.ok(
        "PUT",
        "/api/kolibre/libraries/shared/permessi",
        json={"user_id": lab.sister["id"], "can_edit": True, "can_upload": True},
    )
    moved = lab.ok(
        "POST",
        f"/api/kolibre/library-transfer/shared/books/{lab.books['shared']}/copy-to",
        json={"make_private": True},
    )
    r = lab.ok(
        "GET",
        "/api/kolibre/knowledge/search",
        who="sister",
        params={"q": "quasar", "include_annotations": False},
    )
    assert not any(x["library"] == "shared" for x in r["results"])
    index(lab)
    r = lab.ok(
        "GET",
        "/api/kolibre/knowledge/search",
        params={"q": "quasar", "include_annotations": False},
    )
    assert any(
        x["library"] == moved["target_folder"] and x["book_id"] == moved["book_id"]
        for x in r["results"]
    )
