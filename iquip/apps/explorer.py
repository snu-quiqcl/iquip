"""App module for showing the experiment list and opening an experiment."""

import posixpath
import logging
from typing import Callable, List, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import (
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

import qiwis
from iquip.protocols import ExperimentInfo
from iquip.apps.thread import ExperimentInfoThread

logger = logging.getLogger(__name__)


class ExplorerFrame(QWidget):
    """Frame for showing the experiment list and opening an experiment.

    Attributes:
        fileTree: The tree widget for showing the file structure.
        reloadButton: The button for reloading the fileTree.
        openButton: The button for opening the selected experiment file.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.fileTree = QTreeWidget(self)
        self.fileTree.header().setVisible(False)
        self.reloadButton = QPushButton("Reload", self)
        self.openButton = QPushButton("Open", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.reloadButton)
        layout.addWidget(self.fileTree)
        layout.addWidget(self.openButton)
        self.setLayout(layout)


class _FileFinderThread(QThread):
    """QThread for finding the file list from the proxy server.

    Signals:
        fetched(experimentList, widget): The file list is fetched.

    Attributes:
        path: The path of the directory to search for experiment files.
        widget: The widget corresponding to the path.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(list, object)

    def __init__(
        self,
        path: str,
        widget: Union[QTreeWidget, QTreeWidgetItem],
        ip: str,
        port: int,
        callback: Callable[[List[str], Union[QTreeWidget, QTreeWidgetItem]], None],
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.

        Args:
            path, widget, ip, port: See the attributes section.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.path = path
        self.widget = widget
        self.ip = ip
        self.port = port
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.

        Fetches the file list from the proxy server.

        Searches for only files in path, not in deeper path and adds them into the widget.
        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/ls/",
                                    params={"directory": self.path},
                                    timeout=10)
            response.raise_for_status()
            experimentList = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the file list.")
            return
        self.fetched.emit(experimentList, self.widget)


class ExplorerApp(qiwis.BaseApp):
    """App for showing the experiment list and opening an experiment.

    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        explorerFrame: The frame that shows the file tree.
        fileFinderThread: The most recently executed _FileFinderThread instance.
        experimentInfoThread: The most recently executed ExperimentInfoThread instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.fileFinderThread: Optional[_FileFinderThread] = None
        self.experimentInfoThread: Optional[ExperimentInfoThread] = None
        self.explorerFrame = ExplorerFrame()
        self.loadFileTree()
        # connect signals to slots
        self.explorerFrame.fileTree.itemExpanded.connect(self.lazyLoadFile)
        self.explorerFrame.fileTree.itemDoubleClicked.connect(self.fetchExperimentInfo)
        self.explorerFrame.reloadButton.clicked.connect(self.loadFileTree)
        # self.explorerFrame.openButton.clicked.connect(self.fetchExperimentInfo)

    @pyqtSlot()
    def loadFileTree(self):
        """Loads the experiment file structure in self.explorerFrame.fileTree."""
        self.explorerFrame.fileTree.clear()
        self.fileFinderThread = _FileFinderThread(
            ".",
            self.explorerFrame.fileTree,
            self.proxy_ip,
            self.proxy_port,
            self._addFile,
            self
        )
        self.fileFinderThread.start()

    @pyqtSlot(QTreeWidgetItem)
    def lazyLoadFile(self, experimentFileItem: QTreeWidgetItem):
        """Loads the experiment file in the directory.

        This will be called when a directory item is expanded,
        so it makes loading files lazy.

        Args:
            experimentFileItem: The expanded file item.
        """
        if experimentFileItem.childCount() != 1 or experimentFileItem.child(0).columnCount() != 0:
            return
        # Remove the empty item of an unloaded directory.
        experimentFileItem.takeChild(0)
        experimentPath = self.fullPath(experimentFileItem)
        self.fileFinderThread = _FileFinderThread(
            experimentPath,
            experimentFileItem,
            self.proxy_ip,
            self.proxy_port,
            self._addFile,
            self
        )
        self.fileFinderThread.start()

    @pyqtSlot(list, object)
    def _addFile(self, experimentList: List[str], widget: Union[QTreeWidget, QTreeWidgetItem]):
        """Adds the files into the children of the widget.

        A file or directory which starts with "_" will be ignored, e.g. __pycache__/.

        Args:
            experimentList: The list of files under the widget path.
            widget: See _FileFinderThread class.
        """
        for experimentFile in experimentList:
            if experimentFile.startswith("_"):
                continue
            if experimentFile.endswith("/"):
                experimentFileItem = QTreeWidgetItem(widget)
                experimentFileItem.setText(0, experimentFile[:-1])
                # Make an empty item for indicating that it is a directory.
                QTreeWidgetItem(experimentFileItem)
            elif experimentFile.endswith(".py"):
                experimentFileItem = QTreeWidgetItem(widget)
                experimentFileItem.setText(0, experimentFile)

    @pyqtSlot(QTreeWidgetItem)
    def fetchExperimentInfo(self, item: QTreeWidgetItem):
        """Fetches the given experiment info.
         
        After fetched, it opens the builder of the experiment.

        Once an experiment item is double-clicked or the openButton is clicked, this is called.
        If the given item is a directory, it will be ignored.
        """
        if item.childCount():  # item is a directory
            return
        experimentPath = self.fullPath(item)
        self.experimentInfoThread = ExperimentInfoThread(
            experimentPath,
            self.proxy_ip,
            self.proxy_port,
            self.openBuilder,
            self
        )
        self.experimentInfoThread.start()

    @pyqtSlot(str, str, ExperimentInfo)
    def openBuilder(
        self,
        experimentPath: str,
        experimentClsName: str,
        experimentInfo: ExperimentInfo
    ):
        """Opens the experiment builder with its information.
        
        This is the callback function of apps.builder.ExperimentInfoThread.
        The experiment is guaranteed to be the correct experiment file.

        Args:
            experimentPath: The path of the experiment file.
            experimentClsName: The class name of the experiment.
            experimentInfo: The experiment information. See protocols.ExperimentInfo.
        """
        self.qiwiscall.createApp(
            name=f"builder_{experimentPath}",
            info=qiwis.AppInfo(
                module="iquip.apps.builder",
                cls="BuilderApp",
                pos="center",
                args={
                    "experimentPath": experimentPath,
                    "experimentClsName": experimentClsName,
                    "experimentInfo": experimentInfo
                }
            )
        )

    def fullPath(self, experimentFileItem: QTreeWidgetItem) -> str:
        """Finds the full path of the file item and returns it.

        Args:
            experimentFileItem: The file item to get its full path.
        """
        paths = [experimentFileItem.text(0)]
        while experimentFileItem.parent():
            experimentFileItem = experimentFileItem.parent()
            paths.append(experimentFileItem.text(0))
        return posixpath.join(*reversed(paths))

    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
