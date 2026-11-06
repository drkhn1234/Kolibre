"""Privacy regression tests for an existing shared book moved into private storage."""
import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.services.private_book_move import migrate_owner_records


class PrivateBookMoveTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine, tables=[
            models.User.__table__,
            models.Device.__table__,
            models.DeviceBook.__table__,
            models.SyncQueue.__table__,
            models.DeviceFlaggedBook.__table__,
            models.ReadingPosition.__table__,
            models.ReadingSession.__table__,
            models.Highlight.__table__,
            models.BookReadingCoverage.__table__,
            models.StatsCache.__table__,
            models.BookHash.__table__,
        ])
        self.db = Session(self.engine)
        self.db.add_all([
            models.Device(id=11, device_token="owner-device", name="Owner", model="Kindle", user_id=1),
            models.Device(id=22, device_token="sister-device", name="Sister", model="Kindle", user_id=2),
        ])
        for user_id, device_id in ((1, 11), (2, 22)):
            self.db.add_all([
                models.ReadingPosition(
                    user_id=user_id, library="shared", calibre_book_id=45,
                    device_id=device_id, percentage=.6, progress="page-90",
                ),
                models.ReadingSession(
                    user_id=user_id, library="shared", calibre_book_id=45,
                    device_id=device_id, start_time=datetime(2026, 11, 4), duration=600,
                ),
                models.Highlight(
                    user_id=user_id, library="shared", calibre_book_id=45,
                    device_id=device_id, text=f"private note from user {user_id}",
                ),
                models.BookReadingCoverage(
                    user_id=user_id, library="shared", calibre_book_id=45,
                    bins=bytes(125), coverage=.36,
                ),
                models.DeviceBook(
                    device_id=device_id, library="shared", calibre_book_id=45,
                    format="EPUB", status="synced", device_path="/books/book.epub",
                ),
                models.DeviceFlaggedBook(
                    device_id=device_id, local_path="/books/unmatched.epub",
                    candidate_library="shared", candidate_calibre_book_id=45,
                    pending_action="overwrite", pending_action_library="shared",
                    pending_action_calibre_book_id=45,
                ),
                models.SyncQueue(
                    device_id=device_id, library="shared", calibre_book_id=45,
                    action="queued_download",
                ),
                models.StatsCache(
                    user_id=user_id, library="shared", summary_json="{}",
                    raw_json="[]", timeline_json="[]",
                ),
            ])
        self.db.add(models.BookHash(
            library="shared", calibre_book_id=45, format="EPUB",
            file_hash="historical-shared-hash",
        ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _row_for(self, model, user, current_library, id_number):
        return self.db.query(model).filter(
            model.user_id == user,
            model.library == current_library,
            model.calibre_book_id == id_number,
        ).one()

    def test_only_the_mover_keeps_reading_data_in_private_library(self):
        counts = migrate_owner_records(self.db, "shared", 45, "private_owner", 73, 1)
        self.db.commit()
        for model in (
            models.ReadingPosition,
            models.ReadingSession,
            models.Highlight,
            models.BookReadingCoverage,
        ):
            self.assertEqual(self._row_for(model, 1, "private_owner", 73).user_id, 1)
            self.assertEqual(self._row_for(model, 2, "shared", 45).user_id, 2)
            self.assertEqual(self.db.query(model).count(), 2)
        self.assertEqual(counts["highlights"], 1)
        self.assertEqual(counts["reading_sessions"], 1)
        self.assertEqual(counts["book_reading_coverage"], 1)

    def test_device_copies_are_not_revoked_or_reassigned_across_users(self):
        migrate_owner_records(self.db, "shared", 45, "private_owner", 73, 1)
        self.db.commit()
        one, two = (self.db.query(models.DeviceBook).filter(
            models.DeviceBook.device_id == device
        ).one() for device in (11, 22))
        self.assertEqual((one.library, one.calibre_book_id, one.status),
                         ("private_owner", 73, "synced"))
        self.assertEqual((two.library, two.calibre_book_id, two.status),
                         ("shared", 45, "synced"))
        self.assertEqual(two.device_path, "/books/book.epub")
        owned, sister = (self.db.query(models.DeviceFlaggedBook).filter(
            models.DeviceFlaggedBook.device_id == device
        ).one() for device in (11, 22))
        self.assertEqual(owned.candidate_library, "private_owner")
        self.assertEqual(owned.pending_action_library, "private_owner")
        self.assertEqual(sister.candidate_library, "shared")
        self.assertEqual(sister.pending_action_library, "shared")
        self.assertEqual(
            self.db.query(models.SyncQueue).filter(models.SyncQueue.library == "shared").count(), 1
        )

    def test_private_move_does_not_touch_sisters_cached_statistics(self):
        migrate_owner_records(self.db, "shared", 45, "private_owner", 73, 1)
        self.db.commit()
        self.assertEqual(self.db.query(models.StatsCache).count(), 1)
        self.assertEqual(self.db.query(models.StatsCache).one().user_id, 2)
        self.assertEqual(self.db.query(models.BookHash).count(), 0)

    def test_private_migration_requires_valid_owner_and_different_library(self):
        with self.assertRaises(ValueError):
            migrate_owner_records(self.db, "shared", 45, "private_owner", 73, 0)
        with self.assertRaises(ValueError):
            migrate_owner_records(self.db, "shared", 45, "shared", 73, 1)
        self.assertEqual(self.db.query(models.ReadingPosition).count(), 2)


if __name__ == "__main__":
    unittest.main()
