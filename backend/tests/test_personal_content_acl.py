"""Private annotations, orphan excerpts, and vocabulary must stay owner scoped."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import models
from app.api import annotations, vocabulary
from app.services import widowed_highlights


class PersonalContentACLTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.founder = models.User(
            id=1, username="founder", hashed_password="x",
            is_founder=True, is_admin=True,
        )
        self.sister = models.User(id=2, username="sister", hashed_password="x")
        self.db.add_all([
            self.founder, self.sister,
            models.Library(id=1, name="Shared", folder_name="shared",
                           path="/fake/shared", owner_id=1),
            models.Library(id=2, name="Sister private",
                           folder_name="private_sister", path="/fake/private_sister",
                           owner_id=2, is_private=True),
            models.Highlight(id=11, user_id=1, library="shared",
                             calibre_book_id=88, text="founder secret excerpt"),
            models.Highlight(id=22, user_id=2, library="shared",
                             calibre_book_id=88, text="sister secret excerpt"),
            models.Highlight(id=33, user_id=1, library="private_sister",
                             calibre_book_id=1, text="invalid former association"),
        ])
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def test_widowed_excerpt_groups_include_only_requesting_users_notes(self):
        with patch.object(widowed_highlights, "_ids_esistenti", return_value=set()):
            founder = widowed_highlights.find_widowed_groups(self.db, user_id=1)
            sister = widowed_highlights.find_widowed_groups(self.db, user_id=2)
        own = next(x for x in founder if x["library"] == "shared")
        other = next(x for x in sister if x["library"] == "shared")
        self.assertEqual(own["count"], 1)
        self.assertEqual(own["samples"], ["founder secret excerpt"])
        self.assertEqual(other["count"], 1)
        self.assertEqual(other["samples"], ["sister secret excerpt"])

    def test_existing_annotation_cannot_read_sisters_private_book_title(self):
        note = self.db.query(models.Highlight).filter_by(id=33).one()
        with patch("app.api.annotations.CalibreLibrary", side_effect=AssertionError("private book opened")):
            meta = annotations._build_book_meta([note], self.db, self.founder)
        self.assertEqual(meta, {})

    def test_manual_notes_and_repair_cannot_target_private_library(self):
        with self.assertRaises(HTTPException) as ctx:
            annotations.create_annotation(
                SimpleNamespace(library="private_sister"),
                db=self.db, current_user=self.founder,
            )
        self.assertEqual(ctx.exception.status_code, 404)
        with self.assertRaises(HTTPException) as ctx:
            annotations.repair_widowed_annotations(
                {"library": "shared", "calibre_book_id": 88,
                 "target_library": "private_sister", "target_book_id": 1},
                db=self.db, current_user=self.founder,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_vocabulary_lookup_rejects_foreign_private_book(self):
        with patch("app.api.vocabulary.CalibreLibrary", side_effect=AssertionError("private book opened")):
            self.assertIsNone(vocabulary._book_title("private_sister", 1, self.db, self.founder))
        with self.assertRaises(HTTPException) as ctx:
            vocabulary.add_word_from_reader(
                {"library": "private_sister", "calibre_book_id": 1, "word": "test"},
                db=self.db, current_user=self.founder,
            )
        self.assertEqual(ctx.exception.status_code, 404)

    def test_personal_widowed_repair_never_reassigns_shared_hash(self):
        self.db.add(models.BookHash(
            library="shared", calibre_book_id=88,
            format="EPUB", file_hash="shared-server-hash",
        ))
        self.db.commit()
        moved = widowed_highlights.repair(self.db, "shared", 88, "shared", 55, user_id=1)
        self.db.commit()
        self.assertEqual(moved, 1)
        self.assertEqual(self.db.query(models.Highlight).filter_by(id=22).one().calibre_book_id, 88)
        self.assertEqual(self.db.query(models.BookHash).one().calibre_book_id, 88)


if __name__ == "__main__":
    unittest.main()
