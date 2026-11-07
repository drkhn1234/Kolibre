"""Derived index recovery and extraction; no models/network needed."""

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from app.services import knowledge as k


class Engine:
    identity = "test-model-v1"

    def encode(self, texts):
        return [[1.0, 0.0] for _ in texts]


class IndexTests(unittest.TestCase):
    def test_atomic_failure_model_change_and_delete(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)
            (path / "metadata.db").touch()
            file = path / "book.epub"
            file.write_bytes(b"original")

            class Lib:
                def __init__(self, path):
                    pass

                def list_books(self):
                    return [{"id": 1, "title": "Book", "author": "Author"}]

                def get_format_file_path(self, *args):
                    return str(file) if file.exists() else None

            with (
                patch.object(k, "CalibreLibrary", Lib),
                patch.object(
                    k,
                    "passages",
                    return_value=iter(
                        [
                            {
                                "section": "c.xhtml",
                                "word_start": 0,
                                "text": "original passage",
                            }
                        ]
                    ),
                ),
            ):
                k.sync_library(directory, Engine())
            file.write_bytes(b"changed")
            with (
                patch.object(k, "CalibreLibrary", Lib),
                patch.object(k, "passages", side_effect=RuntimeError("interrupted")),
            ):
                with self.assertRaises(RuntimeError):
                    k.sync_library(directory, Engine())
                self.assertEqual(
                    k.candidates(directory, Engine(), "passage", [1, 0]), ([], 1)
                )
            with k.connect(directory) as db:
                self.assertEqual(
                    db.execute("select text from passages").fetchone()[0],
                    "original passage",
                )
            file.write_bytes(b"original")
            with patch.object(k, "CalibreLibrary", Lib):
                engine = Engine()
                engine.identity = "new-model"
                self.assertEqual(
                    k.candidates(directory, engine, "passage", [1, 0]), ([], 1)
                )
                file.unlink()
                k.sync_library(directory, Engine())
            with k.connect(directory) as db:
                self.assertEqual(
                    db.execute("select count(*) from passages").fetchone()[0], 0
                )
                self.assertEqual(
                    db.execute("select count(*) from lexical").fetchone()[0], 0
                )

    def test_vectors_and_lexical_ranking(self):
        for v in ([], [0, 0], [float("nan")]):
            with self.assertRaises(ValueError):
                k.normalized(v)
        items = [
            {"text": "exact", "_cosine": 0.1, "_lexical": 1},
            {"text": "concept", "_cosine": 0.9, "_lexical": None},
        ]
        self.assertEqual(k.rank(items, "exact", "lexical", 1)[0]["text"], "exact")
        self.assertEqual(k.rank(items, "exact", "semantic", 1)[0]["text"], "concept")
        self.assertNotIn("_cosine", k.rank(items, "exact", "hybrid", 1)[0])
