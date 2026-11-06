"""Application-level private-library isolation for import, trash and restore."""
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api import libraries


class PrivateLibraryLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.lib_root = self.root / "libraries"
        self.trash_root = self.root / "trash"
        self.lib_root.mkdir()
        self.trash_root.mkdir()
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.owner = SimpleNamespace(id=2, username="sister", is_founder=False, is_admin=False)
        self.admin = SimpleNamespace(id=1, username="founder", is_founder=True, is_admin=True)
        self.folder = "private_2_abcd"
        path = self.lib_root / self.folder
        path.mkdir()
        (path / "metadata.db").write_bytes(b"test catalog")
        self.db.add(models.Library(
            name="Sister Private", folder_name=self.folder, path=str(path),
            sort_order=1, owner_id=2, is_private=True,
        ))
        self.db.add(models.ReadingPosition(
            user_id=2, library=self.folder, calibre_book_id=5,
            percentage=.4, progress="page-10",
        ))
        self.db.commit()
        self.patches = [
            patch.object(libraries, "TRASH_DIR", str(self.trash_root)),
            patch.object(libraries.config, "LIBRARIES_DIR", str(self.lib_root)),
            patch.object(libraries.config, "library_path", side_effect=lambda folder: str(self.lib_root / folder)),
            patch.object(libraries.author_stats_service, "safe_mark_author_pages_dirty"),
        ]
        for p in self.patches:
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def _delete(self):
        return libraries.delete_library(self.folder, db=self.db, current_user=self.owner)

    def test_founder_cannot_reimport_private_catalog_by_directory_or_symlink(self):
        from unittest.mock import Mock
        original = str(self.lib_root / self.folder)
        alias = self.root / "external_alias"
        alias.symlink_to(original, target_is_directory=True)
        for path in (original, str(alias)):
            with self.subTest(path=path):
                with self.assertRaises(HTTPException) as exc:
                    libraries.import_library(
                        {"name": "Stolen Catalog", "path": path},
                        background_tasks=BackgroundTasks(),
                        request=Mock(), db=self.db, current_user=self.admin,
                    )
                self.assertEqual(exc.exception.status_code, 403)
        self.assertEqual(self.db.query(models.Library).count(), 1)

    def test_private_trash_is_hidden_and_cannot_be_restored_or_purged_by_founder(self):
        self._delete()
        record = self.db.query(models.TrashedLibrary).one()
        self.assertEqual(record.owner_id, 2)
        self.assertTrue(record.is_private)
        self.assertEqual(libraries.list_trashed_libraries(db=self.db, current_user=self.admin)["items"], [])
        visible = libraries.list_trashed_libraries(db=self.db, current_user=self.owner)["items"]
        self.assertEqual([x["id"] for x in visible], [record.entry])
        with self.assertRaises(HTTPException) as exc:
            libraries.restore_trashed_library(record.entry, BackgroundTasks(), SimpleNamespace(), db=self.db, current_user=self.admin)
        self.assertEqual(exc.exception.status_code, 404)
        with self.assertRaises(HTTPException) as exc:
            libraries.purge_trashed_library(record.entry, db=self.db, current_user=self.admin)
        self.assertEqual(exc.exception.status_code, 404)
        self.assertTrue((self.trash_root / record.entry / "metadata.db").exists())

    def test_owner_restoring_private_trash_keeps_owner_privacy_and_progress(self):
        self._delete()
        record = self.db.query(models.TrashedLibrary).one()
        result = libraries.restore_trashed_library(
            record.entry, BackgroundTasks(),
            SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(write_queue=None))),
            db=self.db, current_user=self.owner,
        )
        self.assertEqual(result["folder_name"], self.folder)
        restored = self.db.query(models.Library).filter_by(folder_name=self.folder).one()
        self.assertTrue(restored.is_private)
        self.assertEqual(restored.owner_id, 2)
        self.assertEqual(self.db.query(models.TrashedLibrary).count(), 0)
        progress = self.db.query(models.ReadingPosition).one()
        self.assertEqual(progress.user_id, 2)
        self.assertEqual(progress.progress, "page-10")

    def test_missing_registry_row_cannot_open_files_even_as_founder(self):
        with self.assertRaises(HTTPException) as ctx:
            libraries.default_library_param("hidden_unregistered", self.db, self.admin)
        self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            libraries.biblioteca_scrivibile("hidden_unregistered", self.db, self.admin)
        self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            libraries.default_library_param(self.folder, self.db, None)
        self.assertEqual(ctx.exception.status_code, 401)
        self.assertEqual(
            libraries.default_library_param(self.folder, self.db, self.owner), self.folder
        )

    def test_crash_orphan_private_library_cannot_be_auto_registered_shared(self):
        # Creation writes metadata.db before the registration commit. A crash
        # between these operations must not expose the private files on boot.
        folder = "private_999_unregistered"
        orphan = self.lib_root / folder
        orphan.mkdir()
        (orphan / "metadata.db").write_bytes(b"private")
        libraries.sync_library_registry(self.db)
        self.assertIsNone(
            self.db.query(models.Library).filter_by(folder_name=folder).first()
        )
        self.assertEqual(self.db.query(models.Library).count(), 1)

    def test_legacy_private_trash_is_fail_closed(self):
        entry = "private_55_legacy_111111"
        (self.trash_root / entry).mkdir()
        self.assertEqual(libraries.list_trashed_libraries(db=self.db, current_user=self.admin)["items"], [])
        with self.assertRaises(HTTPException) as exc:
            libraries.purge_trashed_library(entry, db=self.db, current_user=self.admin)
        self.assertEqual(exc.exception.status_code, 404)


if __name__ == "__main__":
    unittest.main()
