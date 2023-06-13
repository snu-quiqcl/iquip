"""Unit tests for explorer module."""

import unittest
from unittest import mock
import importlib

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem
from PyQt5.QtTest import QTest

from iquip.apps import explorer

class ExplorerFrameTest(unittest.TestCase):
    """Unit tests for ExplorerFrame class."""

    def setUp(self):
        self.qapp = QApplication([])
        patcher = mock.patch("iquip.apps.explorer._FileFinderThread")
        self.MockedFileFinderThread = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        del self.qapp

    @mock.patch("iquip.apps.explorer.ExplorerApp.lazyLoadFile")
    def test_file_tree_item_expanded(self, mockedLazyLoadFile):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        QTreeWidgetItem(directoryItem)  # Add an empty item to an unloaded directory.
        directoryItem.setExpanded(True)
        mockedLazyLoadFile.assert_called_once()  # pylint: disable=no-member

    @mock.patch("iquip.apps.explorer.ExplorerApp.loadFileTree")
    def test_reload_button_clicked(self, mockedLoadFileTree):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        QTest.mouseClick(app.explorerFrame.reloadButton, Qt.LeftButton)
        # Once when the app is created, once explicitly.
        self.assertEqual(app.loadFileTree.call_count, 2)  # pylint: disable=no-member

    def test_open_button_clicked(self):
        explorer.ExplorerApp.openExperiment = mock.MagicMock()
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        QTest.mouseClick(app.explorerFrame.openButton, Qt.LeftButton)
        app.openExperiment.assert_called_once()  # pylint: disable=no-member


class FileFinderThreadTest(unittest.TestCase):
    """Unit tests for _FileFinderThread class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp
        importlib.reload(explorer)  # Restore explorer module.

    def test_init_thread(self):
        widget = QTreeWidgetItem()
        callback = mock.MagicMock()
        parent = QObject()
        thread = explorer._FileFinderThread(path="path", widget=widget, \
                                            callback=callback, parent=parent)
        self.assertEqual(thread.path, "path")
        self.assertEqual(thread.widget, widget)

    def test_run(self):
        explorer._FileFinderThread.fetched = mock.MagicMock()
        explorer.cmdtools.run_command = mock.MagicMock()
        explorer.cmdtools.run_command.return_value.stdout = "path1\npath2\n"
        widget = QTreeWidgetItem()
        parent = QObject()
        thread = explorer._FileFinderThread(path="path", widget=widget, \
                                            callback=mock.MagicMock(), parent=parent)
        thread.run()
        thread.wait()
        thread.fetched.emit.assert_called_once_with(["path1", "path2"], widget)


class ExplorerAppTest(unittest.TestCase):
    """Unit tests for ExplorerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        explorer._FileFinderThread = mock.MagicMock()

    def tearDown(self):
        del self.qapp
        importlib.reload(explorer)  # Restore explorer module.

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
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        QTreeWidgetItem(directoryItem)  # Add an empty item to an unloaded directory.
        app.lazyLoadFile(directoryItem)
        self.assertEqual(directoryItem.childCount(), 0)
        # Once when the app is created, once explicitly.
        self.assertEqual(explorer._FileFinderThread.call_count, 2)

    def test_lazy_load_file_already_loaded(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        fileItem = QTreeWidgetItem(directoryItem)  # Add a file item to a loaded directory.
        fileItem.setText(0, "file")
        app.lazyLoadFile(directoryItem)
        self.assertEqual(directoryItem.childCount(), 1)  # Should not be different from before.
        explorer._FileFinderThread.assert_called_once()  # Once when the app is created.

    def test_lazy_load_file_not_directory(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        fileItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        fileItem.setText(0, "file")
        app.lazyLoadFile(fileItem)
        explorer._FileFinderThread.assert_called_once()  # Once when the app is created.

    def test_add_file(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        parent = QTreeWidgetItem(app.explorerFrame.fileTree)
        experimentList = ["directory/", "_hidden_directory/", \
                          "experiment_file.py", "_hidden_file.py", "file.dummy"]
        app._addFile(experimentList, parent)
        self.assertEqual(parent.childCount(), 2)
        directoryItem = parent.child(0)
        self.assertEqual(directoryItem.text(0), "directory")
        self.assertEqual(directoryItem.childCount(), 1)
        fileItem = parent.child(1)
        self.assertEqual(fileItem.text(0), "experiment_file.py")

    def test_open_experiment(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        item = QTreeWidgetItem(app.explorerFrame.fileTree)
        app.explorerFrame.fileTree.setCurrentItem(item)
        app.fullPath = mock.MagicMock()
        app.openExperiment()
        app.fullPath.assert_called_with(item)

    def test_full_path(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        fileItem = QTreeWidgetItem(directoryItem)
        fileItem.setText(0, "file")
        self.assertEqual(app.fullPath(directoryItem), "masterPath/repository/directory")
        self.assertEqual(app.fullPath(fileItem), "masterPath/repository/directory/file")

    def test_frames(self):
        app = explorer.ExplorerApp(name="name", masterPath="masterPath", parent=QObject())
        self.assertEqual(app.frames(), (app.explorerFrame,))


if __name__ == "__main__":
    unittest.main()
