"""Exercise Make Private through the actual API handler with a throwaway SQLite DB.

Only Calibre's disk operations are mocked; authorization, private routing,
record migration and persistence execute against real SQLAlchemy models.
"""
import unittest
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api.library_transfer import copy_book_to_library


class FakeWriteQueue:
    def __init__(self):
        self.calls = []
        self.skip_flags = []
        self.fail_on = None
        self.source_deleted = False

    async def submit(self, operation, payload, path, _skip_persist_on_failure=False):
        self.calls.append((operation, payload, path))
        self.skip_flags.append(_skip_persist_on_failure)
        if self.fail_on == operation:
            if operation == "delete_book" and path == "/fake/shared":
                self.source_deleted = True
            raise RuntimeError(f"Simulated failure: {operation}")
        if operation == "delete_book" and path == "/fake/shared":
            self.source_deleted = True
        if operation == "insert_book":
            return 303
        return None


class PrivateBookRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.format_path = Path(self.temp.name) / "synthetic.epub"
        self.format_path.write_bytes(b"synthetic book bytes".ljust(32, b" "))
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine, tables=[
            models.User.__table__, models.Library.__table__,
            models.LibraryPermission.__table__,
            models.ReadingPosition.__table__, models.ReadingSession.__table__,
            models.Highlight.__table__, models.BookReadingCoverage.__table__,
            models.BookHash.__table__, models.PrivateBookMove.__table__,
            models.Device.__table__,
            models.DeviceBook.__table__, models.SyncQueue.__table__,
            models.DeviceFlaggedBook.__table__, models.StatsCache.__table__,
        ])
        self.db = Session(self.engine)
        self.owner = SimpleNamespace(id=1, is_founder=True, username="owner")
        self.sister = SimpleNamespace(id=2, is_founder=False, username="sister")
        self.db.add_all([
            models.Library(id=1, owner_id=1, name="Shared", folder_name="shared",
                           path="/fake/shared", is_private=False),
            models.Library(id=2, owner_id=1, name="My private", folder_name="private_owner",
                           path="/fake/private_owner", is_private=True),
            models.ReadingPosition(user_id=1, library="shared", calibre_book_id=45,
                                   percentage=.5, progress="page-50"),
            models.ReadingPosition(user_id=2, library="shared", calibre_book_id=45,
                                   percentage=.9, progress="page-90"),
            models.Highlight(user_id=1, library="shared", calibre_book_id=45,
                             text="my personal notes"),
            models.Highlight(user_id=2, library="shared", calibre_book_id=45,
                             text="sister's personal notes"),
            models.BookHash(library="shared", calibre_book_id=45,
                            format="EPUB", file_hash="abc"),
        ])
        self.db.commit()
        self.queue = FakeWriteQueue()
        self.sample = {
            "id": 45, "title": "Shared title", "author": "Author",
            "formats": ["EPUB"], "series_index": None, "series": None,
            "identifiers": {}, "publisher": None, "tags": [],
            "description": None, "cover_path": None,
        }

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    async def _invoke(self, payload, principal=None, book_id=45):
        with (
            patch("app.api.library_transfer.config.library_path",
                  side_effect=lambda folder: "/fake/" + folder),
            patch("app.api.library_transfer.os.path.exists", return_value=True),
            patch("app.api.library_transfer.os.makedirs"),
            patch("app.api.library_transfer.os.path.getsize", return_value=32),
            patch("app.api.library_transfer.shutil.copyfile"),
            patch("app.api.library_transfer.book_hash_service.upsert_book_hash"),
            patch("app.api.library_transfer.author_ingest_hook.maybe_trigger_wiki_scrape"),
            patch("app.api.library_transfer.ensure_private_library",
                  return_value=self.db.query(models.Library).filter_by(folder_name="private_owner").one()) as ensure_private,
            patch("app.api.library_transfer.CalibreLibrary") as cls,
            patch("app.services.private_move_recovery.CalibreLibrary") as recovery_cls,
            patch("app.services.private_move_recovery.config.library_path",
                  side_effect=lambda folder: "/fake/" + folder),
        ):
            lib = cls.return_value
            recovery_cls.return_value = lib
            lib.list_books.return_value = [self.sample]
            lib.get_format_file_path.return_value = str(self.format_path)
            lib.get_formats.return_value = [{"format": "EPUB", "size": 32}]
            lib.find_book_by_private_move_token.return_value = 303
            lib.get_book.side_effect = lambda _id: None if self.queue.source_deleted else self.sample
            result = await copy_book_to_library(
                "shared", book_id, payload, write_queue=self.queue,
                db=self.db, current_user=principal or self.owner,
            )
            return result, ensure_private

    async def test_make_private_moves_book_but_not_other_users_notes(self):
        result, ensure_private = await self._invoke({"make_private": True})
        ensure_private.assert_called_once()
        self.assertEqual(result["target_folder"], "private_owner")
        self.assertTrue(result["made_private"])
        self.assertEqual(result["book_id"], 303)
        self.assertIn("delete_book", [entry[0] for entry in self.queue.calls])
        self.assertTrue(all(self.queue.skip_flags))
        move = self.db.query(models.PrivateBookMove).one()
        self.assertEqual(move.state, "completed")
        self.assertIsNone(move.active_key)
        self.assertEqual(move.target_book_id, 303)
        self.assertEqual(
            self.db.query(models.ReadingPosition).filter_by(user_id=1).one().library,
            "private_owner",
        )
        self.assertEqual(
            self.db.query(models.Highlight).filter_by(user_id=1).one().calibre_book_id,
            303,
        )
        self.assertEqual(
            self.db.query(models.ReadingPosition).filter_by(user_id=2).one().library,
            "shared",
        )
        self.assertEqual(
            self.db.query(models.Highlight).filter_by(user_id=2).one().text,
            "sister's personal notes",
        )
        self.assertEqual(self.db.query(models.BookHash).count(), 0)

    async def test_failed_copy_removes_target_but_never_shared_source(self):
        self.queue.fail_on = "add_format"
        with self.assertRaises(RuntimeError):
            await self._invoke({"make_private": True})
        move = self.db.query(models.PrivateBookMove).one()
        self.assertEqual(move.state, "rolled_back")
        self.assertIsNone(move.active_key)
        self.assertEqual(
            [(op, path) for op, _, path in self.queue.calls if op == "delete_book"],
            [("delete_book", "/fake/private_owner")],
        )
        self.assertEqual(
            self.db.query(models.ReadingPosition).filter_by(user_id=1).one().library,
            "shared",
        )
        self.assertTrue(all(self.queue.skip_flags))

    async def test_error_after_source_deletion_finishes_owner_data(self):
        # Simulate a Calibre deletion that committed but whose worker raised
        # before the caller received the response.
        self.queue.fail_on = "delete_book"
        with self.assertRaises(RuntimeError):
            await self._invoke({"make_private": True})
        move = self.db.query(models.PrivateBookMove).one()
        self.assertEqual(move.state, "completed")
        self.assertEqual(self.db.query(models.ReadingPosition).filter_by(user_id=1).one().library, "private_owner")
        self.assertEqual(self.db.query(models.ReadingPosition).filter_by(user_id=2).one().library, "shared")

    async def test_duplicate_active_private_move_returns_conflict(self):
        from app.services.private_move_recovery import begin
        begin(self.db, self.owner.id, "shared", 45, "private_owner")
        with self.assertRaises(HTTPException) as ctx:
            await self._invoke({"make_private": True})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertEqual([x[0] for x in self.queue.calls], [])

    async def test_only_move_owner_can_read_or_recover_journal(self):
        from app.api.library_transfer import list_my_private_moves, recover_my_private_move
        from app.services.private_move_recovery import begin
        move = begin(self.db, self.sister.id, "shared", 45, "sister_private")
        self.assertEqual(list_my_private_moves(self.db, self.owner), [])
        own = list_my_private_moves(self.db, self.sister)
        self.assertEqual([row["id"] for row in own], [move.id])
        self.assertNotIn("token", own[0])
        with self.assertRaises(HTTPException) as ctx:
            await recover_my_private_move(
                move.id, db=self.db, write_queue=self.queue, current_user=self.owner,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    async def test_reconcile_finds_uncheckpointed_calibre_target_by_token(self):
        from app.services.private_move_recovery import begin, reconcile
        move = begin(self.db, self.owner.id, "shared", 45, "private_owner")
        self.assertIsNone(move.target_book_id)
        with (
            patch("app.services.private_move_recovery.config.library_path",
                  side_effect=lambda folder: "/fake/" + folder),
            patch("app.services.private_move_recovery.CalibreLibrary") as cls,
        ):
            cls.return_value.get_book.return_value = self.sample
            cls.return_value.get_formats.return_value = [{"format": "EPUB", "size": 32}]
            cls.return_value.get_format_file_path.return_value = str(self.format_path)
            cls.return_value.find_book_by_private_move_token.return_value = 303
            result = await reconcile(self.db, move, self.queue)
        self.assertEqual(result["state"], "rolled_back")
        self.assertEqual(result["target_book_id"], 303)
        self.assertEqual(
            [(op, path) for op, _, path in self.queue.calls if op == "delete_book"],
            [("delete_book", "/fake/private_owner")],
        )
        self.assertTrue(self.queue.skip_flags[-1])

    async def test_missing_source_before_ready_requires_manual_review(self):
        from app.services.private_move_recovery import begin, checkpoint, reconcile
        move = begin(self.db, self.owner.id, "shared", 45, "private_owner")
        checkpoint(self.db, move, "copying", target_id=303)
        with (
            patch("app.services.private_move_recovery.config.library_path",
                  side_effect=lambda folder: "/fake/" + folder),
            patch("app.services.private_move_recovery.CalibreLibrary") as cls,
        ):
            cls.return_value.get_book.return_value = None
            cls.return_value.find_book_by_private_move_token.return_value = 303
            result = await reconcile(self.db, move, self.queue)
            # Repeating recovery must not turn the review state into proof
            # that this incomplete copy had once reached the ready checkpoint.
            repeated = await reconcile(self.db, move, self.queue)
            self.assertEqual(repeated["state"], "needs_review")
        self.assertEqual(result["state"], "needs_review")
        self.assertEqual(result["failure_code"], "source_missing_before_copy_ready")
        self.assertFalse(self.queue.calls)
        self.assertEqual(self.db.query(models.ReadingPosition).filter_by(user_id=1).one().library, "shared")

    async def test_generic_copy_and_delete_cannot_bypass_private_migration(self):
        with self.assertRaises(HTTPException) as ctx:
            await self._invoke({"target_folder": "private_owner", "delete_source": True})
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertFalse(self.queue.calls)

    async def test_upload_only_user_cannot_remove_shared_book(self):
        # Sister gets upload permission but still cannot remove shared content.
        self.db.add(models.LibraryPermission(
            library_id=1, user_id=2, can_upload=True, can_edit=False,
        ))
        self.db.commit()
        with self.assertRaises(HTTPException) as ctx:
            await self._invoke({"make_private": True}, principal=self.sister)
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertFalse(self.queue.calls)

    async def test_private_source_cannot_be_made_private_again(self):
        # User owns the target private library, but cannot make it private twice.
        with (
            patch("app.api.library_transfer.config.library_path",
                  side_effect=lambda folder: "/fake/" + folder),
            patch("app.api.library_transfer.os.path.exists", return_value=True),
        ):
            with self.assertRaises(HTTPException) as ctx:
                await copy_book_to_library(
                    "private_owner", 45, {"make_private": True},
                    db=self.db, current_user=self.owner, write_queue=self.queue,
                )
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertFalse(self.queue.calls)


if __name__ == "__main__":
    unittest.main()
