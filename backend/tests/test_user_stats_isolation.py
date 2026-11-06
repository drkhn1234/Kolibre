"""Reading-statistics hash decisions belong to the reader, not the server."""
import unittest
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.services import stats_service


class PerUserStatisticsDecisionsTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.db.add_all([
            models.User(id=1, username="owner", hashed_password="test", is_founder=True),
            models.User(id=2, username="sister", hashed_password="test"),
            models.Library(id=1, name="Shared", folder_name="shared",
                           path="/fake/shared", owner_id=1, is_private=False),
            models.Library(id=2, name="Sister private", folder_name="private_sister",
                           path="/fake/private_sister", owner_id=2, is_private=True),
            models.Device(id=11, name="Owner Kindle", model="Kindle",
                          device_token="owner", user_id=1),
            models.Device(id=22, name="Sister Kindle", model="Kindle",
                          device_token="sister", user_id=2),
        ])
        for uid, did in [(1, 11), (2, 22)]:
            self.db.add(models.OrphanReadingSession(
                user_id=uid, device_id=did, md5="same-hash",
                title=f"Private notes {uid}", start_time=datetime(2026, 11, 2),
                duration=uid * 100, pages_read=5,
            ))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_owner_pair_cannot_transfer_sisters_orphan_sessions(self):
        result = stats_service.pair_orphan_sessions(
            self.db, 1, "same-hash", "shared", 45,
        )
        self.assertEqual(result["sessions_migrated"], 1)
        self.assertEqual(self.db.query(models.OrphanReadingSession).count(), 1)
        self.assertEqual(self.db.query(models.OrphanReadingSession).one().user_id, 2)
        sessions = self.db.query(models.ReadingSession).all()
        self.assertEqual(len(sessions), 1)
        self.assertEqual(sessions[0].user_id, 1)
        self.assertEqual(sessions[0].duration, 100)

    def test_pairing_resolution_never_inherits_from_other_account(self):
        stats_service.pair_orphan_sessions(self.db, 1, "same-hash", "shared", 45)
        with patch("app.services.stats_service.book_hash_service.resolve_book_identities", return_value=[]):
            self.assertEqual(stats_service._resolve_book_identities(self.db, "same-hash", 1), [("shared", 45)])
            self.assertEqual(stats_service._resolve_book_identities(self.db, "same-hash", 2), [])

    def test_discard_isolated_to_reader(self):
        removed = stats_service.discard_orphan_sessions(self.db, 1, "same-hash")
        self.assertEqual(removed, 1)
        self.assertEqual(self.db.query(models.OrphanReadingSession).one().user_id, 2)
        self.assertEqual(self.db.query(models.UserStatsHashDiscard).one().user_id, 1)

    def test_founder_cannot_pair_reading_state_into_sisters_private_library(self):
        with self.assertRaises(PermissionError):
            stats_service.pair_orphan_sessions(self.db, 1, "same-hash", "private_sister", 45)
        self.assertEqual(self.db.query(models.OrphanReadingSession).count(), 2)

    def test_raw_admin_logs_not_available_with_multiple_users(self):
        from app.api.tools import get_server_logs
        from fastapi import HTTPException
        admin = self.db.query(models.User).filter_by(id=1).one()
        with self.assertRaises(HTTPException) as ctx:
            get_server_logs(_chi=admin, db=self.db)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_entity_helper_cannot_open_other_users_private_library(self):
        from app.api.entities import _biblioteche
        from fastapi import HTTPException
        admin = self.db.query(models.User).filter_by(id=1).one()
        with patch("app.api.entities.CalibreLibrary", side_effect=AssertionError("Private Calibre DB opened")):
            with self.assertRaises(HTTPException) as ctx:
                _biblioteche("private_sister", self.db, admin)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_legacy_global_pairing_not_used_to_open_private_library(self):
        self.db.add(models.StatsHashPairing(
            md5="same-hash", library="private_sister", calibre_book_id=45,
            paired_by_user_id=2,
        ))
        self.db.commit()
        with patch("app.services.stats_service.book_hash_service.resolve_book_identities", return_value=[]):
            self.assertEqual(stats_service._resolve_book_identities(self.db, "same-hash", 1), [])
            self.assertEqual(stats_service._resolve_book_identities(self.db, "same-hash", 2), [])


if __name__ == "__main__":
    unittest.main()
