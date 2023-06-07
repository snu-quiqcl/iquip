"""Unit tests for explorer module."""

import unittest
from unittest import mock

from PyQt5.QtWidgets import QApplication

import qiwis
from iquip.apps import explorer

class ExplorerAppTest(unittest.TestCase):
    """Unit tests for ExplorerApp class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp


if __name__ == "__main__":
    unittest.main()
