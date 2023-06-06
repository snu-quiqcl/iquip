"""App module for showing the experiment list and opening an experiment."""

import posixpath
from typing import Callable, List, Optional, Tuple, Union

from PyQt5.QtCore import QObject, QThread, pyqtSlot, pyqtSignal
from PyQt5.QtWidgets import (
    QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

import qiwis

from iquip import cmdtools

class ExplorerFrame(QWidget):
    """Frame for showing the experiment list and opening an experiment."""

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


class FileFinderThread(QThread):
    """QThread for finding the file list using a command line.

    Signals:
        finished(experimentList, parent): Fetching the file list is finished.

    Attributes:
        path: The path of the directory to search for experiment files.
        parent: The widget corresponding to the path.
    """

    finished = pyqtSignal(list, object)

    def __init__(
        self,
        path: str,
        parent: Union[QTreeWidget, QTreeWidgetItem],
        callback: Callable[[List[str], Union[QTreeWidget, QTreeWidgetItem]], None]
    ):
        """
        Args:
            callback: The callback method called after this thread is finished.
        """
        super().__init__()
        self.path = path
        self.parent = parent
        self.finished.connect(callback)

    def run(self):
        """Fetches the file list using a command line.

        Searches for only files in path, not in deeper path and adds them into parent.
        After finished, the finished signal is emitted.
        """
        experimentList = cmdtools.run_command(f"artiq_client ls {self.path}").stdout
        experimentList = experimentList.split("\n")[:-1]  # The last one is always an empty string.
        self.finished.emit(experimentList, self.parent)


class ExplorerApp(qiwis.BaseApp):
    """App for showing the experiment list and opening an experiment."""

    def __init__(self, name: str, masterPath: str = ".", parent: Optional[QObject] = None):
        """Extended.

        Args:
            masterPath: The path where artiq_master command is running.
        """
        super().__init__(name, parent=parent)
        self.repositoryPath = posixpath.join(masterPath, "repository")
        self.explorerFrame = ExplorerFrame()
        self.loadFileTree()
        # connect signals to slots
        self.explorerFrame.fileTree.itemExpanded.connect(self.lazyLoadFile)
        self.explorerFrame.reloadButton.clicked.connect(self.loadFileTree)
        self.explorerFrame.openButton.clicked.connect(self.openExperiment)

    @pyqtSlot()
    def loadFileTree(self):
        """Loads the experiment file structure in self.explorerFrame.fileTree.

        It assumes that all experiment files are in self.repositoryPath.
        """
        self.explorerFrame.fileTree.clear()
        self.thread = FileFinderThread(
            self.repositoryPath,
            self.explorerFrame.fileTree,
            self._addFile
        )
        self.thread.start()

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
        self.thread = FileFinderThread(
            experimentPath,
            experimentFileItem,
            self._addFile
        )
        self.thread.start()

    def _addFile(self, experimentList: List[str], parent: Union[QTreeWidget, QTreeWidgetItem]):
        """Adds the files into the children of the parent.

        A file or directory which starts with "_" will be ignored, e.g. __pycache__/.

        Args:
            experimentList: The list of files under the parent path.
            parent: See FileFinderThread class.
        """
        for experimentFile in experimentList:
            if experimentFile.startswith("_"):
                continue
            if experimentFile.endswith("/"):
                experimentFileItem = QTreeWidgetItem(parent)
                experimentFileItem.setText(0, experimentFile[:-1])
                # Make an empty item for indicating that it is a directory.
                QTreeWidgetItem(experimentFileItem)
            elif experimentFile.endswith(".py"):
                experimentFileItem = QTreeWidgetItem(parent)
                experimentFileItem.setText(0, experimentFile)

    @pyqtSlot()
    def openExperiment(self):
        """Opens the experiment builder of the selected experiment.

        Once the openButton is clicked, this is called.
        If the selected element is a directory, it will be ignored.

        TODO(BECATRUE): Open the experiment builder. It will be implemented in Basic Runner project.
        """
        experimentFileItem = self.explorerFrame.fileTree.currentItem()
        if experimentFileItem.childCount():
            return
        experimentPath = self.fullPath(experimentFileItem)  # pylint: disable=unused-variable

    def fullPath(self, experimentFileItem: QTreeWidgetItem) -> str:
        """Finds the full path of the file item and returns it.

        Args:
            experimentFileItem: The file item to get its full path.
        """
        path = [experimentFileItem.text(0)]
        while experimentFileItem.parent():
            experimentFileItem = experimentFileItem.parent()
            path.append(experimentFileItem.text(0))
        path.append(self.repositoryPath)
        path = posixpath.join(*reversed(path))
        return path

    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
