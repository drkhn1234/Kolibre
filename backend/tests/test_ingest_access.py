"""Cross-user isolation regression tests for the ingest authorization boundary.

Run from backend/: python -m unittest discover -s tests -v
"""
import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.services.ingest_access import get_accessible_ingest, visible_ingest_query
from app.services import permessi


class IngestIsolationTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine, tables=[
            models.User.__table__,
            models.Library.__table__,
            models.LibraryPermission.__table__,
            models.IngestedBook.__table__,
        ])
        self.db = Session(self.engine)
        self.founder = SimpleNamespace(id=1, is_founder=True)
        self.sister = SimpleNamespace(id=2, is_founder=False)
        self.third = SimpleNamespace(id=3, is_founder=False)
        self.admin = SimpleNamespace(id=4, is_founder=False, is_admin=True)
        self.db.add_all([
            models.IngestedBook(id=10, uploader_id=1, file_path="/a", filename="a.epub", file_format="EPUB", title="A"),
            models.IngestedBook(id=11, uploader_id=2, file_path="/b", filename="b.epub", file_format="EPUB", title="B"),
            models.IngestedBook(id=12, uploader_id=None, file_path="/legacy", filename="legacy.epub", file_format="EPUB", title="Legacy"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_founder_does_not_inherit_access_to_sisters_staged_uploads(self):
        ids = {r.id for r in visible_ingest_query(self.db, self.founder).all()}
        self.assertEqual(ids, {10, 12})

    def test_sister_cannot_access_founders_upload_or_unowned_watcher_file(self):
        ids = {r.id for r in visible_ingest_query(self.db, self.sister).all()}
        self.assertEqual(ids, {11})
        for item_id in (10, 12):
            with self.assertRaises(HTTPException) as ctx:
                get_accessible_ingest(self.db, self.sister, item_id)
            self.assertEqual(ctx.exception.status_code, 404)

    def test_other_user_sees_no_staged_files(self):
        self.assertEqual(visible_ingest_query(self.db, self.third).count(), 0)

    def test_nonfounder_system_admin_cannot_read_private_staged_files(self):
        self.assertEqual(visible_ingest_query(self.db, self.admin).count(), 0)

    def test_separate_upload_permission_does_not_grant_edit(self):
        library = models.Library(id=20, name="Shared", folder_name="shared", path="/shared", owner_id=1)
        self.db.add(library)
        self.db.add(models.LibraryPermission(
            user_id=2, library_id=20, can_upload=True, can_edit=False
        ))
        self.db.commit()
        self.assertTrue(permessi.puo_caricare(self.db, self.sister, library))
        self.assertFalse(permessi.puo_modificare(self.db, self.sister, library))
        self.assertFalse(permessi.puo_caricare(self.db, self.third, library))

    def test_founder_cannot_read_or_edit_another_users_private_library(self):
        private = models.Library(
            id=30, name="Sister private", folder_name="sister_private",
            path="/sister_private", owner_id=self.sister.id, is_private=True,
        )
        self.db.add(private)
        self.db.commit()
        self.assertTrue(permessi.puo_leggere(self.db, self.sister, private))
        for operation in (
            permessi.puo_leggere, permessi.puo_modificare,
            permessi.puo_caricare, permessi.puo_condividere,
            permessi.puo_gestire_permessi, permessi.puo_cancellare,
        ):
            self.assertFalse(operation(self.db, self.founder, private))
            self.assertFalse(operation(self.db, self.admin, private))
        self.assertNotIn(
            private.id, {row.id for row in permessi.biblioteche_visibili(self.db, self.founder)}
        )
        self.assertIn(
            private.id, {row.id for row in permessi.biblioteche_visibili(self.db, self.sister)}
        )

    def test_private_upload_creates_personal_destination(self):
        from unittest.mock import patch
        from app.services.ingest_access import require_ingest_destination
        private_upload = models.IngestedBook(
            id=14, uploader_id=self.sister.id, is_private=True,
            file_path="/private", filename="private.epub", file_format="EPUB", title="Private",
        )
        self.db.add(private_upload)
        self.db.commit()
        with patch("app.services.ingest_access.CalibreLibrary") as calibre:
            destination = require_ingest_destination(self.db, self.sister, private_upload, "shared")
            again = require_ingest_destination(self.db, self.sister, private_upload, "shared")
        self.assertEqual(destination, again)
        self.assertEqual(calibre.call_count, 1)
        row = self.db.query(models.Library).filter(
            models.Library.folder_name == destination
        ).one()
        self.assertTrue(row.is_private)
        self.assertEqual(row.owner_id, self.sister.id)
        self.assertFalse(permessi.puo_leggere(self.db, self.founder, row))

    def test_shared_upload_remains_shared_and_requires_can_upload(self):
        from app.services.ingest_access import require_ingest_destination
        shared = models.Library(
            id=40, name="Shared", folder_name="shared", path="/shared",
            owner_id=self.founder.id, is_private=False, sort_order=0,
        )
        self.db.add(shared)
        self.db.add(models.LibraryPermission(
            user_id=self.sister.id, library_id=40, can_upload=True, can_edit=False,
        ))
        self.db.commit()
        staged = models.IngestedBook(
            id=15, uploader_id=self.sister.id, is_private=False,
            file_path="/shared_upload", filename="shared.epub", file_format="EPUB", title="Shared book",
        )
        self.assertEqual(
            require_ingest_destination(self.db, self.sister, staged, None),
            "shared",
        )
        with self.assertRaises(HTTPException) as exc:
            require_ingest_destination(self.db, self.third, staged, None)
        self.assertEqual(exc.exception.status_code, 403)

    def test_opds_library_cannot_be_queried_by_founder(self):
        from app.api.opds import _get_library_row, _list_library_rows
        library = models.Library(
            id=50, name="Other private", folder_name="private_other",
            path="/other", owner_id=self.sister.id, is_private=True,
        )
        self.db.add(library)
        self.db.commit()
        with self.assertRaises(HTTPException) as exc:
            _get_library_row(self.db, "private_other", self.founder)
        self.assertEqual(exc.exception.status_code, 404)
        self.assertEqual(
            _get_library_row(self.db, "private_other", self.sister).id, library.id
        )
        self.assertEqual(_list_library_rows(self.db, self.founder), [])


if __name__ == "__main__":
    unittest.main()
