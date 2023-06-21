"""Unit tests for explorer module."""

import unittest
from unittest import mock

from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem

from iquip.apps import explorer


class FileFinderThreadTest(unittest.TestCase):
    """Unit tests for _FileFinderThread class."""

    def setUp(self):
        self.qapp = QApplication([])

    def tearDown(self):
        del self.qapp

    def test_init_thread(self):
        widget = QTreeWidgetItem()
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.explorer._FileFinderThread.fetched") as mockedFetched:
            thread = explorer._FileFinderThread(path="path", widget=widget,
                                                callback=callback, parent=parent)
            self.assertEqual(thread.path, "path")
            self.assertEqual(thread.widget, widget)
            mockedFetched.connect.assert_called_once_with(callback, type=Qt.QueuedConnection)

    @mock.patch("requests.get")
    def test_run(self, mocked_get):
        mocked_response = mocked_get.return_value
        mocked_response.json.return_value = ["path1", "path2"]
        widget = QTreeWidgetItem()
        parent = QObject()
        with mock.patch("iquip.apps.explorer._FileFinderThread.fetched") as mockedFetched:
            thread = explorer._FileFinderThread(path="path", widget=widget,
                                                callback=mock.MagicMock(), parent=parent)
            thread.run()
            thread.wait()
            mocked_get.assert_called_once_with("http://127.0.0.1:8000/ls/",
                                               params={"directory": "path"},
                                               timeout=10)
            mockedFetched.emit.assert_called_once_with(["path1", "path2"], widget)


class ExplorerAppTest(unittest.TestCase):
    """Unit tests for ExplorerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        patcher = mock.patch("iquip.apps.explorer._FileFinderThread")
        self.mocked_file_finder_thread_cls = patcher.start()
        self.addCleanup(patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_load_file_tree(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        QTreeWidgetItem(app.explorerFrame.fileTree)  # Add a dummy item to the file tree.
        app.loadFileTree()
        self.assertEqual(app.explorerFrame.fileTree.topLevelItemCount(), 0)
        # Once when the app is created, once explicitly.
        self.assertEqual(self.mocked_file_finder_thread_cls.call_count, 2)

    def test_lazy_load_file(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        QTreeWidgetItem(directoryItem)  # Add an empty item to an unloaded directory.
        app.lazyLoadFile(directoryItem)
        self.assertEqual(directoryItem.childCount(), 0)
        # Once when the app is created, once explicitly.
        self.assertEqual(self.mocked_file_finder_thread_cls.call_count, 2)

    def test_lazy_load_file_already_loaded(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        fileItem = QTreeWidgetItem(directoryItem)  # Add a file item to a loaded directory.
        fileItem.setText(0, "file")
        app.lazyLoadFile(directoryItem)
        self.assertEqual(directoryItem.childCount(), 1)  # Should not be different from before.
        self.mocked_file_finder_thread_cls.assert_called_once()  # Once when the app is created.

    def test_lazy_load_file_not_directory(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        fileItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        fileItem.setText(0, "file")
        app.lazyLoadFile(fileItem)
        self.mocked_file_finder_thread_cls.assert_called_once()  # Once when the app is created.

    def test_add_file(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        parent = QTreeWidgetItem(app.explorerFrame.fileTree)
        experimentList = ["directory/", "_hidden_directory/",
                          "experiment_file.py", "_hidden_file.py", "file.dummy"]
        app._addFile(experimentList, parent)
        self.assertEqual(parent.childCount(), 2)  # "directory/" and "experiment_file.py".
        directoryItem = parent.child(0)
        self.assertEqual(directoryItem.text(0), "directory")
        self.assertEqual(directoryItem.childCount(), 1)  # An empty item for an unloaded directory.
        fileItem = parent.child(1)
        self.assertEqual(fileItem.text(0), "experiment_file.py")
        self.assertEqual(fileItem.childCount(), 0)  # No child item for a file.

    def test_open_experiment(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        item = QTreeWidgetItem(app.explorerFrame.fileTree)
        app.explorerFrame.fileTree.setCurrentItem(item)
        with mock.patch.object(app, "fullPath") as mockedFullPath:
            app.openExperiment()
            mockedFullPath.assert_called_with(item)

    def test_full_path(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        fileItem = QTreeWidgetItem(directoryItem)
        fileItem.setText(0, "file")
        self.assertEqual(app.fullPath(directoryItem), "directory")
        self.assertEqual(app.fullPath(fileItem), "directory/file")

    def test_frames(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        self.assertEqual(app.frames(), (app.explorerFrame,))


if __name__ == "__main__":
    unittest.main()
