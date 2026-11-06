"""Reusing a client filename must not reuse an old staging identity."""
import asyncio
import io
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import config, models
from app.api.ingest import upload_ingest_files


class RepeatedUploadTests(unittest.TestCase):
    def test_reupload_after_import_has_new_record_and_private_visibility(self):
        engine = create_engine("sqlite:///:memory:")
        models.Base.metadata.create_all(engine)
        try:
            with tempfile.TemporaryDirectory() as root, Session(engine) as db:
                with patch.object(config, "INGEST_DIR", root):
                    user = SimpleNamespace(id=1)
                    def upload(visibility):
                        return asyncio.run(upload_ingest_files(
                            files=[UploadFile(filename="same.txt", file=io.BytesIO(b"synthetic book"))],
                            visibility=visibility, db=db, current_user=user,
                        ))
                    first = upload("shared")
                    self.assertEqual(first["rejected"], [])
                    original = db.get(models.IngestedBook, first["staged"][0]["id"])
                    original.status = "imported"
                    os.remove(original.file_path)  # import moves the staged file
                    db.commit()
                    second = upload("private")
                    self.assertEqual(second["rejected"], [])
                    fresh = db.get(models.IngestedBook, second["staged"][0]["id"])
                    self.assertNotEqual(fresh.id, original.id)
                    self.assertNotEqual(fresh.file_path, original.file_path)
                    self.assertEqual(fresh.filename, "same.txt")
                    self.assertEqual(fresh.status, "pending")
                    self.assertTrue(fresh.is_private)
                    self.assertFalse(original.is_private)
        finally:
            engine.dispose()
