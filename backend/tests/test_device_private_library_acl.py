"""Device-token and web-device actions cannot open other users' private books."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api import devices


class DeviceLibraryIsolationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.founder = models.User(
            id=1, username="founder", hashed_password="test", is_founder=True,
            is_admin=True,
        )
        self.sister = models.User(
            id=2, username="sister", hashed_password="test", is_founder=False,
        )
        self.db.add_all([
            self.founder, self.sister,
            models.Library(
                id=1, name="Shared", folder_name="shared", path="/fake/shared",
                owner_id=1, is_private=False,
            ),
            models.Library(
                id=2, name="Sister private", folder_name="sister_private",
                path="/fake/sister_private", owner_id=2, is_private=True,
            ),
            models.Device(id=7, name="Founder Kindle", model="Kindle",
                          device_token="founder-token", user_id=1),
            models.Device(id=8, name="Sister Kindle", model="Kindle",
                          device_token="sister-token", user_id=2),
            models.DeviceFlaggedBook(
                id=22, device_id=7, local_path="/books/local.epub",
                pending_action="overwrite", pending_action_library="sister_private",
                pending_action_calibre_book_id=12,
            ),
            models.DeviceFlaggedBook(
                id=23, device_id=7, local_path="/books/delete-me.epub",
                pending_action="delete",
            ),
        ])
        self.db.commit()
        self.founder_device = self.db.query(models.Device).filter_by(id=7).one()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_founder_cannot_read_sisters_device_library(self):
        with self.assertRaises(HTTPException) as ctx:
            devices.require_device_library(self.db, self.founder_device, "sister_private")
        self.assertEqual(ctx.exception.status_code, 404)

    def test_pending_overwrite_cannot_advertise_private_book(self):
        with patch("app.api.devices.CalibreLibrary", side_effect=AssertionError("private catalog opened")):
            actions = devices._build_file_actions(self.db, self.founder_device)
        self.assertEqual(len(actions), 1)
        self.assertEqual(actions[0]["action"], "delete")
        self.assertNotIn("download_url", actions[0])

    def test_manual_pair_and_overwrite_reject_other_users_private_library(self):
        for action in ("pair", "overwrite"):
            with self.subTest(action=action):
                with self.assertRaises(HTTPException) as ctx:
                    devices.queue_flagged_book_action(
                        device_id=7, flagged_id=22,
                        payload={"action": action, "library": "sister_private",
                                 "calibre_book_id": 12},
                        db=self.db, current_user=self.founder,
                    )
                self.assertEqual(ctx.exception.status_code, 404)

    def test_device_cannot_auto_pair_or_flag_another_users_library(self):
        with self.assertRaises(HTTPException) as ctx:
            devices.auto_pair_orphan_annotations(
                payload={"local_path": "/file.epub", "file_hash": "hash123",
                         "library": "sister_private", "calibre_book_id": 12},
                db=self.db, current_device=self.founder_device,
            )
        self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            devices.report_flagged_book(
                payload={"candidate_library": "sister_private",
                         "candidate_calibre_book_id": 12,
                         "match_status": "flagged_started",
                         "match_source": "fingerprint"},
                db=self.db, current_device=self.founder_device,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_hash_resolution_does_not_expose_private_books_to_founder(self):
        match = SimpleNamespace(library="sister_private", calibre_book_id=12)
        with patch("app.api.devices.book_hash_service.resolve_first_book_match", return_value=match):
            self.assertIsNone(devices.resolve_accessible_device_match(
                self.db, "hash123", self.founder_device,
            ))
        with patch("app.api.devices.book_hash_service.resolve_first_book_match", return_value=match):
            result = devices.push_device_annotations(
                payload={"annotations": [{"hash": "hash123", "text": "local quote"}]},
                db=self.db, current_device=self.founder_device,
            )
        self.assertEqual(result["unresolved"], 1)
        self.assertEqual(self.db.query(models.Highlight).count(), 0)


if __name__ == "__main__":
    unittest.main()
