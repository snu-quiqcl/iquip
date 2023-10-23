"""Unit tests for explorer module."""

import unittest
from collections import namedtuple
from unittest import mock

import requests
import qiwis
from PyQt5.QtCore import QObject, Qt
from PyQt5.QtWidgets import QApplication, QTreeWidgetItem
from PyQt5.QtTest import QTest

from iquip import protocols
from iquip.apps import explorer

_CONSTANTS_DICT = {"proxy_ip": "127.0.0.1", "proxy_port": 8000}

CONSTANTS = namedtuple("ConstantNamespace", _CONSTANTS_DICT.keys())(**_CONSTANTS_DICT)

class FileFinderThreadTest(unittest.TestCase):
    """Unit tests for _FileFinderThread class."""

    # pylint: disable=duplicate-code
    def setUp(self):
        self.qapp = QApplication([])
        constants_patcher = mock.patch("iquip.apps.explorer.ExplorerApp._constants", CONSTANTS)
        requests_get_patcher = mock.patch("requests.get")
        constants_patcher.start()
        self.mocked_get = requests_get_patcher.start()
        self.mocked_response = self.mocked_get.return_value
        self.addCleanup(constants_patcher.stop)
        self.addCleanup(requests_get_patcher.stop)

    def tearDown(self):
        del self.qapp

    def test_init_thread(self):
        widget = QTreeWidgetItem()
        callback = mock.MagicMock()
        parent = QObject()
        with mock.patch("iquip.apps.explorer._FileFinderThread.fetched") as mocked_fetched:
            thread = explorer._FileFinderThread(
                path="path",
                widget=widget,
                ip=CONSTANTS.proxy_ip,
                port=CONSTANTS.proxy_port,
                callback=callback,
                parent=parent
            )
        self.assertEqual(thread.path, "path")
        self.assertEqual(thread.widget, widget)
        mocked_fetched.connect.assert_called_once_with(callback, type=Qt.QueuedConnection)

    def test_run(self):
        self.mocked_response.json.return_value = ["path1", "path2"]
        widget = QTreeWidgetItem()
        parent = QObject()
        with mock.patch("iquip.apps.explorer._FileFinderThread.fetched") as mocked_fetched:
            thread = explorer._FileFinderThread(
                path="path",
                widget=widget,
                ip=CONSTANTS.proxy_ip,
                port=CONSTANTS.proxy_port,
                callback=mock.MagicMock(),
                parent=parent
            )
            thread.run()
            thread.wait()
        self.mocked_get.assert_called_once_with("http://127.0.0.1:8000/ls/",
                                                params={"directory": "path"},
                                                timeout=10)
        mocked_fetched.emit.assert_called_once_with(["path1", "path2"], widget)

    def test_run_exception(self):
        """Tests when a requests.exceptions.RequestException occurs."""
        self.mocked_response.raise_for_status.side_effect = requests.exceptions.RequestException()
        widget = QTreeWidgetItem()
        parent = QObject()
        with mock.patch("iquip.apps.explorer._FileFinderThread.fetched") as mocked_fetched:
            thread = explorer._FileFinderThread(
                path="path",
                widget=widget,
                ip=CONSTANTS.proxy_ip,
                port=CONSTANTS.proxy_port,
                callback=mock.MagicMock(),
                parent=parent
            )
            thread.run()
            thread.wait()
        self.mocked_get.assert_called_once_with("http://127.0.0.1:8000/ls/",
                                                params={"directory": "path"},
                                                timeout=10)
        mocked_fetched.emit.assert_not_called()


class ExplorerAppTest(unittest.TestCase):
    """Unit tests for ExplorerApp class."""

    def setUp(self):
        self.qapp = QApplication([])
        constants_patcher = mock.patch("iquip.apps.explorer.ExplorerApp._constants", CONSTANTS)
        file_finder_thread_patcher = mock.patch("iquip.apps.explorer._FileFinderThread")
        constants_patcher.start()
        self.mocked_file_finder_thread_cls = file_finder_thread_patcher.start()
        self.addCleanup(constants_patcher.stop)
        self.addCleanup(file_finder_thread_patcher.stop)

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

    def test_open_button_clicked(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        item = QTreeWidgetItem(app.explorerFrame.fileTree)
        app.explorerFrame.fileTree.setCurrentItem(item)
        with mock.patch.object(app, "fetchExperimentInfo") as mocked_fetch_experiment_info:
            app.openButtonClicked()
        mocked_fetch_experiment_info.assert_called_once_with(item)

    def test_open_button_clicked_not_selected(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        QTreeWidgetItem(app.explorerFrame.fileTree)  # Add an item, but not selected
        with mock.patch.object(app, "fetchExperimentInfo") as mocked_fetch_experiment_info:
            app.openButtonClicked()
        mocked_fetch_experiment_info.assert_not_called()

    @mock.patch("iquip.apps.explorer.ExperimentInfoThread")
    def test_fetch_experiment_info(self, mocked_experiment_info_thread_cls):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        item = QTreeWidgetItem(app.explorerFrame.fileTree)
        with mock.patch.multiple(
            app, fullPath=mock.DEFAULT, openBuilder=mock.DEFAULT
        ) as mocked:
            app.fetchExperimentInfo(item)
        mocked["fullPath"].assert_called_with(item)
        mocked_experiment_info_thread_cls.assert_called_with(
            mocked["fullPath"].return_value,
            CONSTANTS.proxy_ip,
            CONSTANTS.proxy_port,
            mocked["openBuilder"],
            app
        )

    @mock.patch("iquip.apps.explorer.ExperimentInfoThread")
    def test_fetch_experiment_info_for_directory(self, mocked_experiment_info_thread_cls):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        item = QTreeWidgetItem(app.explorerFrame.fileTree)
        QTreeWidgetItem(item)  # Add a child item to make "item" a directory.
        with mock.patch.multiple(
            app, fullPath=mock.DEFAULT, openBuilder=mock.DEFAULT
        ) as mocked:
            app.fetchExperimentInfo(item)
        mocked["fullPath"].assert_not_called()
        mocked_experiment_info_thread_cls.assert_not_called()

    def test_open_builder(self):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        experimentInfo = protocols.ExperimentInfo("name", {"arg0": "value0"})
        with mock.patch.object(app, "qiwiscall") as mocked_qiwiscall:
            app.openBuilder("experimentPath", "experimentClsName", experimentInfo)
        mocked_qiwiscall.createApp.assert_called_with(
            name="builder_experimentPath",
            info=qiwis.AppInfo(
                module="iquip.apps.builder",
                cls="BuilderApp",
                pos="center",
                args={
                    "experimentPath": "experimentPath",
                    "experimentClsName": "experimentClsName",
                    "experimentInfo": experimentInfo
                }
            )
        )

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


class ExplorerFunctionalTest(unittest.TestCase):
    """Functional tests for explorer GUI."""

    def setUp(self):
        self.qapp = QApplication([])
        constants_patcher = mock.patch("iquip.apps.explorer.ExplorerApp._constants", CONSTANTS)
        file_finder_thread_patcher = mock.patch("iquip.apps.explorer._FileFinderThread")
        constants_patcher.start()
        self.mocked_file_finder_thread_cls = file_finder_thread_patcher.start()
        self.addCleanup(constants_patcher.stop)
        self.addCleanup(file_finder_thread_patcher.stop)

    def tearDown(self):
        del self.qapp

    @mock.patch("iquip.apps.explorer.ExplorerApp.lazyLoadFile")
    def test_file_tree_item_expanded(self, mocked_lazy_load_file):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        directoryItem = QTreeWidgetItem(app.explorerFrame.fileTree)
        directoryItem.setText(0, "directory")
        QTreeWidgetItem(directoryItem)  # Add an empty item to an unloaded directory.
        directoryItem.setExpanded(True)
        mocked_lazy_load_file.assert_called_once()

    @mock.patch("iquip.apps.explorer.ExplorerApp.loadFileTree")
    def test_reload_button_clicked(self, mocked_load_file_tree):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        QTest.mouseClick(app.explorerFrame.reloadButton, Qt.LeftButton)
        # Once when the app is created, once explicitly.
        self.assertEqual(mocked_load_file_tree.call_count, 2)

    @mock.patch("iquip.apps.explorer.ExplorerApp.openButtonClicked")
    def test_open_button_clicked(self, mocked_open_button_clicked):
        app = explorer.ExplorerApp(name="name", parent=QObject())
        QTest.mouseClick(app.explorerFrame.openButton, Qt.LeftButton)
        mocked_open_button_clicked.assert_called_once()


if __name__ == "__main__":
    unittest.main()
