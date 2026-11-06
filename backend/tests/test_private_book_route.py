"""Exercise Make Private through the actual API handler with a throwaway SQLite DB.

Only Calibre's disk operations are mocked; authorization, private routing,
record migration and persistence execute against real SQLAlchemy models.
"""
import unittest
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

    async def submit(self, operation, payload, path):
        self.calls.append((operation, payload, path))
        if operation == "insert_book":
            return 303
        return None


class PrivateBookRouteTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine, tables=[
            models.User.__table__, models.Library.__table__,
            models.LibraryPermission.__table__,
            models.ReadingPosition.__table__, models.ReadingSession.__table__,
            models.Highlight.__table__, models.BookReadingCoverage.__table__,
            models.BookHash.__table__, models.Device.__table__,
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
            patch("app.api.library_transfer.ensure_private_library",
                  return_value=self.db.query(models.Library).filter_by(folder_name="private_owner").one()) as ensure_private,
            patch("app.api.library_transfer.CalibreLibrary") as cls,
        ):
            lib = cls.return_value
            lib.list_books.return_value = [self.sample]
            lib.get_format_file_path.return_value = "/fake/shared/author/title.epub"
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
