"""HTTP-level isolation with real throwaway Calibre metadata.db files.

Unlike direct endpoint tests, these exercise FastAPI dependency resolution:
the same `default_library_param` gate used by the React UI, OPDS and MCP
integration paths must deny the founder access to another person's library.
"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app import auth, config, database, models
from app.api import libraries, books, fulltext, annotations, vocabulary, opds
from app.calibre.library import CalibreLibrary


class TwoUserHttpPrivacyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.library_root = self.root / "libraries"
        self.library_root.mkdir()
        self.patchers = [
            patch.object(config, "LIBRARIES_DIR", str(self.library_root)),
            patch.object(libraries, "TRASH_DIR", str(self.root / "trash")),
        ]
        for patcher in self.patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        self.engine = create_engine(
            "sqlite://", connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        models.Base.metadata.create_all(self.engine)
        self.session = Session(self.engine)
        self.founder = models.User(
            id=1, username="founder", hashed_password=auth.get_password_hash("test-password"),
            is_founder=True, is_admin=True,
        )
        self.sister = models.User(
            id=2, username="sister", hashed_password=auth.get_password_hash("test-password"),
            is_founder=False, is_admin=False,
        )
        self.session.add_all([self.founder, self.sister])
        for index, name, owner, private in (
            (1, "shared", 1, False),
            (2, "sister_private", 2, True),
        ):
            path = config.library_path(name)
            lib = CalibreLibrary(path, crea=True)
            lib.insert_book(
                title="Private sister reading" if private else "Shared physics book",
                author="Test Author",
            )
            self.session.add(models.Library(
                id=index, name=name, folder_name=name, path=path,
                sort_order=index, owner_id=owner, is_private=private,
            ))
        self.session.add(models.Highlight(
            id=1, user_id=2, library="sister_private", calibre_book_id=1,
            text="Sister-only annotation",
        ))
        self.session.commit()

        app = FastAPI()
        for router in (libraries.router, books.router, fulltext.router,
                       annotations.router, vocabulary.router, opds.router):
            app.include_router(router)

        def active_user(request: Request):
            user_id = 1 if request.headers.get("X-Test-User") == "founder" else 2
            return self.session.query(models.User).filter_by(id=user_id).one()

        def db_session():
            yield self.session

        app.dependency_overrides[database.get_db] = db_session
        app.dependency_overrides[auth.get_current_user] = active_user
        app.dependency_overrides[auth.get_current_user_flexible] = active_user
        app.dependency_overrides[auth.utente_effettivo_opzionale] = active_user
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        self.session.close()
        self.engine.dispose()

    def get(self, path, founder=False):
        return self.client.get(
            path, headers={"X-Test-User": "founder" if founder else "sister"},
        )

    def test_founder_sees_shared_books_but_not_sisters_private_catalog(self):
        public = self.get("/api/kolibre/books?library=shared", founder=True)
        self.assertEqual(public.status_code, 200, public.text)
        self.assertIn("Shared physics book", str(public.json()))
        hidden = self.get("/api/kolibre/books?library=sister_private", founder=True)
        self.assertEqual(hidden.status_code, 404, hidden.text)
        owned = self.get("/api/kolibre/books?library=sister_private")
        self.assertEqual(owned.status_code, 200, owned.text)
        self.assertIn("Private sister reading", str(owned.json()))

    def test_library_list_does_not_disclose_private_sisters_catalog(self):
        response = self.get("/api/kolibre/libraries", founder=True)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(
            {lib["folder_name"] for lib in response.json()}, {"shared"},
        )
        response = self.get("/api/kolibre/libraries")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertIn("sister_private", {lib["folder_name"] for lib in response.json()})

    def test_fulltext_metadata_is_permission_gated_before_disk_access(self):
        response = self.get("/api/kolibre/fulltext/status?library=sister_private", founder=True)
        self.assertEqual(response.status_code, 404, response.text)

    def test_anonymous_library_path_traversal_does_not_bypass_http_read_gate(self):
        for request_path in (
            "/api/kolibre/books?library=../../sister_private",
            "/api/kolibre/books?library=/tmp/secrets",
        ):
            response = self.get(request_path, founder=True)
            self.assertIn(response.status_code, (400, 404), response.text)

    def test_private_annotation_is_only_returned_to_its_owner(self):
        founder = self.get("/api/kolibre/annotations", founder=True)
        self.assertEqual(founder.status_code, 200, founder.text)
        self.assertNotIn("Sister-only annotation", str(founder.json()))
        sister = self.get("/api/kolibre/annotations")
        self.assertEqual(sister.status_code, 200, sister.text)
        self.assertIn("Sister-only annotation", str(sister.json()))

    def test_http_basic_opds_denies_founder_others_private_books(self):
        with patch("app.api.opds.app_settings.is_opds_feed_enabled", return_value=True):
            founder_root = self.client.get(
                "/opds", auth=("founder", "test-password"),
            )
            self.assertEqual(founder_root.status_code, 200, founder_root.text)
            self.assertNotIn("sister_private", founder_root.text)
            other = self.client.get(
                "/opds/sister_private/all", auth=("founder", "test-password"),
            )
            self.assertEqual(other.status_code, 404, other.text)
            owner_root = self.client.get(
                "/opds", auth=("sister", "test-password"),
            )
            self.assertEqual(owner_root.status_code, 200, owner_root.text)
            self.assertIn("sister_private", owner_root.text)
            own = self.client.get(
                "/opds/sister_private/all", auth=("sister", "test-password"),
            )
            self.assertEqual(own.status_code, 200, own.text)
            self.assertIn("Private sister reading", own.text)

    def test_founder_cannot_write_annotation_into_sisters_private_library(self):
        response = self.client.post(
            "/api/kolibre/annotations",
            json={
                "library": "sister_private", "calibre_book_id": 1,
                "text": "Foreign write", "page": 1,
            },
            headers={"X-Test-User": "founder"},
        )
        self.assertEqual(response.status_code, 404, response.text)
        self.assertEqual(
            self.session.query(models.Highlight).filter_by(user_id=1).count(), 0
        )


if __name__ == "__main__":
    unittest.main()
