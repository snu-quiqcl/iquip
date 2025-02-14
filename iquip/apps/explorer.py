"""App module for showing the experiment list and opening an experiment."""

import posixpath
import logging
from typing import Dict, Iterable, List, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import (
    QComboBox, QDialog, QHBoxLayout, QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget,
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
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.

        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.path = path
        self.widget = widget
        self.ip = ip
        self.port = port

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


class BuilderInfoDialog(QDialog):
    """Dialog for setting builder info.
    
    There are two types of info.
        clsName: Target experiment class name.
        tag: Additive tag for multiple builder apps.
    """

    def __init__(self, clsNames: Iterable[str], parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            See thread.ExperimentInfoThread.fetched signal.
        """
        super().__init__(parent=parent)
        # widgets
        self.comboBox = QComboBox(self)
        self.comboBox.addItems(clsNames)
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setPlaceholderText("Tag")
        self.okButton = QPushButton("OK", self)
        self.okButton.clicked.connect(self.accept)
        self.cancelButton = QPushButton("Cancel", self)
        self.cancelButton.clicked.connect(self.reject)
        # layout
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.okButton)
        buttonLayout.addWidget(self.cancelButton)
        layout = QVBoxLayout(self)
        layout.addWidget(self.comboBox)
        layout.addWidget(self.lineEdit)
        layout.addLayout(buttonLayout)

    def getBuilderInfo(self) -> Tuple[str, str]:
        """Returns the configured builder info.

        Returns:
            (clsName, tag): See BuilderInfoDialog.
        """
        return self.comboBox.currentText(), self.lineEdit.text()


class ExplorerApp(qiwis.BaseApp):
    """App for showing the experiment list and opening an experiment.

    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        selectedExperimentPath: The currently selected experiment path.
        explorerFrame: The frame that shows the file tree.
        fileFinderThread: The most recently executed _FileFinderThread instance.
        experimentInfoThread: The most recently executed ExperimentInfoThread instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.selectedExperimentPath: Optional[str] = None
        self.fileFinderThread: Optional[_FileFinderThread] = None
        self.experimentInfoThread: Optional[ExperimentInfoThread] = None
        self.explorerFrame = ExplorerFrame()
        self.loadFileTree()
        # connect signals to slots
        self.explorerFrame.fileTree.itemExpanded.connect(self.lazyLoadFile)
        self.explorerFrame.fileTree.itemDoubleClicked.connect(self.fetchExperimentInfo)
        self.explorerFrame.reloadButton.clicked.connect(self.loadFileTree)
        self.explorerFrame.openButton.clicked.connect(self.openButtonClicked)

    @pyqtSlot()
    def loadFileTree(self):
        """Loads the experiment file structure in self.explorerFrame.fileTree."""
        self.explorerFrame.fileTree.clear()
        self.fileFinderThread = _FileFinderThread(
            ".",
            self.explorerFrame.fileTree,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.fileFinderThread.fetched.connect(self._addFile, type=Qt.QueuedConnection)
        self.fileFinderThread.finished.connect(self.fileFinderThread.deleteLater)
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
            self
        )
        self.fileFinderThread.fetched.connect(self._addFile, type=Qt.QueuedConnection)
        self.fileFinderThread.finished.connect(self.fileFinderThread.deleteLater)
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

    @pyqtSlot()
    def openButtonClicked(self):
        """Called when the openButton is clicked.
        
        If no item is selected, nothing happens.
        """
        item = self.explorerFrame.fileTree.currentItem()
        if item is not None:  # item is selected
            self.fetchExperimentInfo(item)


    @pyqtSlot(QTreeWidgetItem)
    def fetchExperimentInfo(self, item: QTreeWidgetItem):
        """Fetches the given experiment info.
         
        After fetched, self.selectExperimentCls() is called to select an experiment class.

        Once an experiment item is double-clicked or the openButton is clicked, this is called.
        If the given item is a directory, nothing happens.
        """
        if item.childCount():  # item is a directory
            return
        self.selectedExperimentPath = self.fullPath(item)
        self.experimentInfoThread = ExperimentInfoThread(
            self.selectedExperimentPath,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.experimentInfoThread.fetched.connect(self.openBuilderInfoDialog,
                                                  type=Qt.QueuedConnection)
        self.experimentInfoThread.finished.connect(self.experimentInfoThread.deleteLater)
        self.experimentInfoThread.start()

    @pyqtSlot(dict)
    def openBuilderInfoDialog(self, experimentInfos: Dict[str, ExperimentInfo]):
        """Opens a dialog for setting builder info.
        
        If the dialog is confirmed, self.openBuilder() is called with the configured builder info.
        Otherwise, nothing happens.

        Args:
            See thread.ExperimentInfoThread.fetched signal.
        """
        dialog = BuilderInfoDialog(experimentInfos)
        if dialog.exec_():
            clsName, tag = dialog.getBuilderInfo()
            self.openBuilder(clsName, tag, experimentInfos[clsName])


    def openBuilder(self, clsName: str, tag: str, experimentInfo: ExperimentInfo):
        """Opens the experiment builder with its information.
        
        The experiment is guaranteed to be the correct experiment file.

        Args:
            clsName, tag: See BuilderInfoDialog.
            experimentInfo: The experiment information. See protocols.ExperimentInfo.
        """
        if tag:
            tag = f" ({tag})"
        self.qiwiscall.createApp(
            name=f"builder{tag} - {self.selectedExperimentPath}:{clsName}",
            info=qiwis.AppInfo(
                module="iquip.apps.builder",
                cls="BuilderApp",
                pos="center",
                args={
                    "experimentPath": self.selectedExperimentPath,
                    "experimentClsName": clsName,
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

    def frames(self) -> Tuple[Tuple[str, ExplorerFrame]]:
        """Overridden."""
        return (("", self.explorerFrame),)
