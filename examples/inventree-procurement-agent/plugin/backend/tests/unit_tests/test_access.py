"""Offline checks for the task read policy."""

from __future__ import annotations

import sys
import unittest
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from inventree_procurement_plugin.access import read_status  # noqa: E402


@dataclass
class FakeUser:
    is_authenticated: bool
    pk: int | None


class ReadAccessTests(unittest.TestCase):
    def test_anonymous_and_missing_identity_are_rejected(self) -> None:
        self.assertEqual(read_status(None), 401)
        self.assertEqual(read_status(FakeUser(False, None)), 401)
        self.assertEqual(read_status(FakeUser(True, None)), 401)

    def test_owner_can_read_other_user_is_hidden(self) -> None:
        self.assertEqual(read_status(FakeUser(True, 17), owner_id=17), 200)
        self.assertEqual(read_status(FakeUser(True, 17), owner_id=18), 404)
