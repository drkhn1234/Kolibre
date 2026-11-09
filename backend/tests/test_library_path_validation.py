"""Calibre library path inputs must never traverse outside the catalog root."""
import os
import unittest
from app import config


class LibraryPathValidationTests(unittest.TestCase):
    def test_reject_traversal_and_absolute_locations(self):
        bad_names = (
            "..", ".", "", "../private_sister", "a/../private_sister",
            "/etc/passwd", "/tmp/secret", "a\\..\\secret", "a/b", "a\\b", "bad\x00name",
        )
        for name in bad_names:
            with self.subTest(name=repr(name)):
                with self.assertRaises(ValueError):
                    config.library_path(name)

    def test_accept_single_component_unicode_and_normal_names(self):
        for name in ("shared", "private_2_abcd", "Physics books", "Kütüphane"):
            with self.subTest(name=name):
                self.assertEqual(config.library_path(name), os.path.join(config.LIBRARIES_DIR, name))


if __name__ == "__main__":
    unittest.main()
