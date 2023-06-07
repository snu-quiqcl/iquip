"""Unit tests for explorer module."""

import unittest
from unittest import mock
import posixpath

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication

import qiwis
from iquip.apps import explorer

class ExplorerAppTest(unittest.TestCase):
    """Unit tests for ExplorerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        explorer.ExplorerFrame = mock.MagicMock()
        explorer._FileFinderThread = mock.MagicMock()

    def tearDown(self):
        del self.qapp

    def test_init_app(self):
        app = explorer.ExplorerApp("name", "masterPath", QObject())
        self.assertEqual(app.repositoryPath, "masterPath/repository")

    def test_init_app_default(self):
        app = explorer.ExplorerApp("name")
        self.assertEqual(app.repositoryPath, "./repository")


if __name__ == "__main__":
    unittest.main()
