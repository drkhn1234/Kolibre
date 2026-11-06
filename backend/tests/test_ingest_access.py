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


if __name__ == "__main__":
    unittest.main()
