"""Restart must not manufacture grants or claim ownerless private data."""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.services.legacy_permissions import migrate_legacy_library_permissions


class StartupPermissionTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.founder = models.User(username="founder", hashed_password="unused", is_founder=True)
        self.sister = models.User(username="sister", hashed_password="unused")
        self.db.add_all([self.founder, self.sister])
        self.db.flush()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def library(self, name, **kwargs):
        row = models.Library(name=name, folder_name=name, path="/unused/" + name, **kwargs)
        self.db.add(row)
        self.db.commit()
        return row

    def migrate(self):
        migrate_legacy_library_permissions(self.db, self.founder)
        self.db.commit()

    def test_owned_library_without_grant_stays_inaccessible(self):
        self.library("shared", owner_id=self.founder.id)
        self.migrate()
        self.assertEqual(self.db.query(models.LibraryPermission).count(), 0)

    def test_legacy_grant_migrates_once_and_revocation_survives(self):
        library = self.library("legacy")
        self.migrate()
        self.assertEqual(library.owner_id, self.founder.id)
        grant = self.db.query(models.LibraryPermission).one()
        self.assertEqual(grant.user_id, self.sister.id)
        self.assertTrue(grant.can_edit)
        self.db.delete(grant)
        self.db.commit()
        self.migrate()
        self.assertEqual(self.db.query(models.LibraryPermission).count(), 0)

    def test_ownerless_private_catalog_is_never_claimed_or_shared(self):
        library = self.library("private_orphan", is_private=True)
        self.migrate()
        self.assertIsNone(library.owner_id)
        self.assertEqual(self.db.query(models.LibraryPermission).count(), 0)
