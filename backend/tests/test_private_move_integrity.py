"""Recovery must preserve a valid copy when only the source row survived."""
import tempfile
import unittest
from pathlib import Path

from app.calibre.library import CalibreLibrary
from app.services.private_move_recovery import source_safe_for_rollback


class PrivateMoveIntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.source = CalibreLibrary(str(root / "source"), crea=True)
        self.target = CalibreLibrary(str(root / "target"), crea=True)
        self.ids = []
        self.files = []
        for lib in (self.source, self.target):
            book_id = lib.insert_book("Synthetic", "Test Author")
            lib.update_book(book_id, {"path": "Test Author/Synthetic"})
            directory = Path(lib.path) / "Test Author/Synthetic"
            directory.mkdir(parents=True)
            path = directory / "synthetic.epub"
            path.write_bytes(b"the only valid synthetic copy")
            # Deliberately stale size: EPUB metadata rewrites can change bytes
            # without refreshing data.uncompressed_size. Hash equality matters.
            lib.add_format(book_id, "EPUB", 1, "synthetic")
            self.ids.append(book_id)
            self.files.append(path)

    def safe(self):
        return source_safe_for_rollback(self.source, self.ids[0], self.target, self.ids[1])

    def test_identical_real_files_allow_rollback_despite_stale_catalog_sizes(self):
        self.assertTrue(self.safe())

    def test_missing_source_is_not_proved_by_its_surviving_catalog_row(self):
        self.files[0].unlink()
        self.assertIsNotNone(self.source.get_book(self.ids[0]))
        self.assertFalse(self.safe())

    def test_truncated_source_requires_review(self):
        self.files[0].write_bytes(b"truncated")
        self.assertFalse(self.safe())

    def test_same_size_corruption_requires_review(self):
        self.files[0].write_bytes(b"x" * self.files[0].stat().st_size)
        self.assertFalse(self.safe())

    def test_missing_target_cannot_be_used_as_integrity_evidence(self):
        self.files[1].unlink()
        self.assertFalse(self.safe())
