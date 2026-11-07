"""An operator can shorten native sessions; invalid policies fail closed."""
import os
import unittest
from unittest.mock import patch

from app import auth


class NativeTokenLifetimeTests(unittest.TestCase):
    def test_default_preserves_existing_sessions_and_operator_can_shorten(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(auth._native_token_lifetime_minutes(), 10080)
        with patch.dict(os.environ, {"KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES": "15"}):
            self.assertEqual(auth._native_token_lifetime_minutes(), 15)

    def test_invalid_policy_cannot_remove_expiry_or_silently_fall_back(self):
        for value in ("0", "-1", "10081", "", "forever", "1.5"):
            with self.subTest(value=value), patch.dict(
                os.environ, {"KOLIBRE_ACCESS_TOKEN_EXPIRE_MINUTES": value}
            ):
                with self.assertRaises(ValueError):
                    auth._native_token_lifetime_minutes()
