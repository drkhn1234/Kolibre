"""Verify that Calibre target insertion and move-token assignment are atomic.

The journal records the intended move before insertion. If the app crashes
before it can save the returned ID, we can still find exactly the new book.
"""
import tempfile
import unittest

from app.calibre.library import CalibreLibrary


class PrivateMoveRecoveryMarkerTests(unittest.TestCase):
    def test_book_can_be_identified_after_crash_before_app_checkpoint(self):
        with tempfile.TemporaryDirectory() as root:
            lib = CalibreLibrary(root, crea=True)
            self.assertIsNone(lib.find_book_by_private_move_token("operation-abc"))
            target_id = lib.insert_book(
                title="Recovery test", author="Test Author",
                private_move_token="operation-abc",
            )
            self.assertEqual(lib.find_book_by_private_move_token("operation-abc"), target_id)
            self.assertEqual(lib.get_book(target_id)["title"], "Recovery test")
            self.assertIsNone(lib.find_book_by_private_move_token("operation-other"))

    def test_identical_titles_do_not_confuse_recovery(self):
        with tempfile.TemporaryDirectory() as root:
            lib = CalibreLibrary(root, crea=True)
            first = lib.insert_book("Same title", "Same author", private_move_token="first")
            second = lib.insert_book("Same title", "Same author", private_move_token="second")
            self.assertNotEqual(first, second)
            self.assertEqual(lib.find_book_by_private_move_token("first"), first)
            self.assertEqual(lib.find_book_by_private_move_token("second"), second)


if __name__ == "__main__":
    unittest.main()
