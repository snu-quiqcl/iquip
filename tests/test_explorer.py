"""Unit tests for explorer module."""

import unittest
from unittest import mock
import posixpath

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem

import qiwis
from iquip.apps import explorer

class ExplorerAppTest(unittest.TestCase):
    """Unit tests for ExplorerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        explorer._FileFinderThread = mock.MagicMock()

    def tearDown(self):
        del self.qapp

    def test_init_app(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        self.assertEqual(app.repositoryPath, "masterPath/repository")

    def test_init_app_default(self):
        app = explorer.ExplorerApp(name="name")
        self.assertEqual(app.repositoryPath, "./repository")

    def test_load_file_tree(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        QTreeWidgetItem(app.explorerFrame.fileTree)  # Add a dummy item to the file tree.
        app.loadFileTree()
        self.assertEqual(app.explorerFrame.fileTree.topLevelItemCount(), 0)
        # Once when the app is created, once explicitly.
        self.assertEqual(explorer._FileFinderThread.call_count, 2)

    def test_lazy_load_file(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        directoryItem = QTreeWidgetItem()
        directoryItem.setText(0, "directory")
        QTreeWidgetItem(directoryItem)  # Add an empty item to an unloaded directory.
        app.lazyLoadFile(directoryItem)
        self.assertEqual(directoryItem.childCount(), 0)
        # Once when the app is created, once explicitly.
        self.assertEqual(explorer._FileFinderThread.call_count, 2)

    def test_lazy_load_file_already_loaded(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        directoryItem = QTreeWidgetItem()
        directoryItem.setText(0, "directory")
        fileItem = QTreeWidgetItem(directoryItem)  # Add a file item to a loaded directory.
        fileItem.setText(0, "file")
        app.lazyLoadFile(directoryItem)
        self.assertEqual(directoryItem.childCount(), 1)  # Should not be different from before.
        explorer._FileFinderThread.assert_called_once()  # Once when the app is created.

    def test_lazy_load_file_not_directory(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        fileItem = QTreeWidgetItem()
        fileItem.setText(0, "file")
        app.lazyLoadFile(fileItem)
        explorer._FileFinderThread.assert_called_once()  # Once when the app is created.


if __name__ == "__main__":
    unittest.main()
