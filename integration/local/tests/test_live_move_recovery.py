"""Real HTTP moves and process crashes with disposable EPUBs and SQLite files."""

import asyncio
import hashlib
import sqlite3

import httpx
import pytest
from fastmcp import Client

from test_live_native import stack, populated  # noqa: F401


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sql(lab, statement, parameters=()):
    with sqlite3.connect(lab.directory / "app.db") as db:
        db.row_factory = sqlite3.Row
        return [dict(row) for row in db.execute(statement, parameters)]


def seed_readers(lab):
    book = lab.books["shared"]
    lab.ok("PUT", "/api/kolibre/settings/web-reader-tracking", json={"enabled": True})
    devices = {}
    for who, percentage in [("founder", 0.42), ("sister", 0.78)]:
        lab.ok(
            "PUT",
            f"/api/kolibre/books/{book}/reading-position?library=shared",
            who=who,
            json={"percentage": percentage},
        )
        assert (
            lab.ok(
                "GET",
                f"/api/kolibre/books/{book}/reading-position?library=shared",
                who=who,
            )["percentage"]
            == percentage
        )
        devices[who] = lab.ok(
            "POST",
            "/api/devices/register",
            who=who,
            json={"name": who + "-synthetic-reader", "model": "synthetic"},
        )["id"]
        lab.ok(
            "POST",
            f"/api/devices/{devices[who]}/queue",
            who=who,
            json={
                "library": "shared",
                "calibre_book_id": book,
                "action": "queued_download",
                "format": "EPUB",
            },
        )
    return devices


def assert_personal_state(lab, mover, target, target_id, devices):
    other = "sister" if mover == "founder" else "founder"
    for who, folder, book_id in [
        (mover, target, target_id),
        (other, "shared", lab.books["shared"]),
    ]:
        expected = 0.42 if who == "founder" else 0.78
        assert (
            lab.ok(
                "GET",
                f"/api/kolibre/books/{book_id}/reading-position?library={folder}",
                who=who,
            )["percentage"]
            == expected
        )
        notes = lab.ok("GET", "/api/kolibre/annotations", who=who)
        note_id = lab.notes[who, "shared"]["id"]
        own = next(note for note in notes if note["id"] == note_id)
        assert own["library"] == folder and own["calibre_book_id"] == book_id
        rows = sql(
            lab,
            "SELECT library, calibre_book_id FROM device_books WHERE device_id=?",
            (devices[who],),
        )
        assert rows == [{"library": folder, "calibre_book_id": book_id}]
    assert (
        lab.request(
            "GET",
            f"/api/kolibre/books/{target_id}/reading-position?library={target}",
            who=other,
        ).status_code
        == 404
    )


@pytest.mark.parametrize("mover", ["founder", "sister"])
@pytest.mark.asyncio
async def test_live_move_transfers_only_current_readers_state(populated, mover):
    lab = populated
    devices = seed_readers(lab)
    source_file = next((lab.directory / "data/libraries/shared").rglob("*.epub"))
    original_hash = digest(source_file)
    result = lab.ok(
        "POST",
        f"/api/kolibre/library-transfer/shared/books/{lab.books['shared']}/copy-to",
        who=mover,
        json={"make_private": True},
    )
    assert result["target_folder"] == lab.private[mover]
    target_id = result["book_id"]
    target_files = list(
        (lab.directory / "data/libraries" / lab.private[mover]).rglob("*.epub")
    )
    assert any(digest(file) == original_hash for file in target_files)
    assert not source_file.exists()
    assert_personal_state(lab, mover, lab.private[mover], target_id, devices)
    lab.start("bridge", ["-m", "calibre_mcp.kolibre_bridge"], lab.bridge_port)

    async def read(who):
        async with Client(lab.mcp_url, auth=lab.tokens[who]) as client:
            notes = await client.call_tool("kolibre_my_annotations")
            other = "sister" if who == "founder" else "founder"
            assert who + "-secret-note" in str(notes.data)
            assert other + "-secret-note" not in str(notes.data)
            # The shared library was indexed before the move. Stale full-text
            # data must not disclose a book that has become private.
            search = await client.call_tool(
                "kolibre_search_fulltext", {"library": "shared", "query": "quasar"}
            )
            assert search.data["results"] == []

    await asyncio.gather(read("founder"), read("sister"))


def crash_during_move(lab, state):
    lab.backend.terminate()
    lab.backend.wait(timeout=15)
    # Instrument only a durable checkpoint in this test process. No auth or
    # Calibre operation is replaced. os._exit prevents exception compensation.
    lab.env["LAB_CRASH_STATE"] = state
    script = """import os, uvicorn
from backend.app.services import private_move_recovery as recovery
original = recovery.checkpoint
def checkpoint(db, move, state, target_id=None):
    original(db, move, state, target_id)
    if state == os.environ['LAB_CRASH_STATE']:
        os._exit(89)
recovery.checkpoint = checkpoint
uvicorn.run('backend.app.main:app', host='127.0.0.1', port=int(os.environ['LAB_BACKEND_PORT']))
"""
    lab.env["LAB_BACKEND_PORT"] = str(lab.backend_port)
    lab.backend = lab.start("crashing-backend", ["-c", script], lab.backend_port)
    with pytest.raises(httpx.RemoteProtocolError):
        lab.request(
            "POST",
            f"/api/kolibre/library-transfer/shared/books/{lab.books['shared']}/copy-to",
            who="sister",
            json={"make_private": True},
        )
    assert lab.backend.wait(timeout=15) == 89
    journal = sql(lab, "SELECT * FROM private_book_moves")[0]
    assert journal["state"] == state
    # A confirmed dead process cannot still be moving. Age only the test
    # journal to exercise the endpoint's two-minute anti-concurrency guard.
    sql(lab, "UPDATE private_book_moves SET updated_at=datetime('now', '-3 minutes')")
    lab.start_backend()
    return journal


@pytest.mark.parametrize(
    "state,expected", [("ready", "rolled_back"), ("source_deleted", "completed")]
)
def test_live_crash_and_journal_recovery(populated, state, expected):
    lab = populated
    devices = seed_readers(lab)
    original = next((lab.directory / "data/libraries/shared").rglob("*.epub"))
    original_hash = digest(original)
    journal = crash_during_move(lab, state)
    endpoint = f"/api/kolibre/library-transfer/private-moves/{journal['id']}/recover"
    assert lab.request("POST", endpoint, who="founder").status_code == 404
    assert (
        lab.ok("GET", "/api/kolibre/library-transfer/private-moves", who="founder")
        == []
    )
    result = lab.ok("POST", endpoint, who="sister")
    assert result["state"] == expected
    assert lab.ok("POST", endpoint, who="sister")["state"] == expected
    if expected == "completed":
        assert_personal_state(
            lab, "sister", journal["target_library"], journal["target_book_id"], devices
        )
    else:
        assert original.exists() and digest(original) == original_hash
    survivors = list((lab.directory / "data/libraries").rglob("*.epub"))
    assert any(digest(file) == original_hash for file in survivors)
    assert sql(lab, "SELECT * FROM pending_calibre_writes") == []


@pytest.mark.parametrize("damage", ["missing", "truncated", "same_size_corruption"])
def test_recovery_never_deletes_only_valid_copy(populated, damage):
    lab = populated
    source = next((lab.directory / "data/libraries/shared").rglob("*.epub"))
    original_hash = digest(source)
    journal = crash_during_move(lab, "ready")
    # The source catalog row survives but its file is no longer valid.
    if damage == "missing":
        source.unlink()
    elif damage == "truncated":
        source.write_bytes(b"broken")
    else:
        source.write_bytes(b"x" * source.stat().st_size)
    target_files = list(
        (lab.directory / "data/libraries" / journal["target_library"]).rglob("*.epub")
    )
    valid_target = next(file for file in target_files if digest(file) == original_hash)
    result = lab.ok(
        "POST",
        f"/api/kolibre/library-transfer/private-moves/{journal['id']}/recover",
        who="sister",
    )
    assert valid_target.exists(), "Recovery deleted the only valid EPUB copy"
    assert digest(valid_target) == original_hash
    assert result["state"] == "needs_review"
    assert result["failure_code"] == "source_integrity_unverified"
    repeated = lab.ok(
        "POST",
        f"/api/kolibre/library-transfer/private-moves/{journal['id']}/recover",
        who="sister",
    )
    assert repeated["state"] == "needs_review" and valid_target.exists()
    assert sql(lab, "SELECT * FROM pending_calibre_writes") == []


def test_repeated_review_cannot_promote_incomplete_copy(populated):
    lab = populated
    journal = crash_during_move(lab, "copying")
    # Model source removal by another operation while this copy was incomplete.
    # Keep its real SQLite catalog valid, but remove only this synthetic row.
    path = lab.directory / "data/libraries/shared/metadata.db"
    with sqlite3.connect(path) as db:
        db.execute("DELETE FROM books WHERE id=?", (lab.books["shared"],))
    endpoint = f"/api/kolibre/library-transfer/private-moves/{journal['id']}/recover"
    for _ in range(2):
        result = lab.ok("POST", endpoint, who="sister")
        assert result["state"] == "needs_review"
        assert result["failure_code"] == "source_missing_before_copy_ready"
