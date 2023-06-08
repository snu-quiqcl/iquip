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


class _FileFinderThread(QThread):
    """QThread for finding the file list using a command line.

    Signals:
        fetched(experimentList, widget): The file list is fetched.

    Attributes:
        path: The path of the directory to search for experiment files.
        widget: The widget corresponding to the path.
    """

    fetched = pyqtSignal(list, object)

    def __init__(
        self,
        path: str,
        widget: Union[QTreeWidget, QTreeWidgetItem],
        callback: Callable[[List[str], Union[QTreeWidget, QTreeWidgetItem]], None],
        parent: Optional[QObject] = None
    ):
        """Extended.

        Args:
            path, widget: See the attributes section in _FileFinderThread.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.path = path
        self.widget = widget
        self.fetched.connect(callback)

    def run(self):
        """Overridden.
        
        Fetches the file list using a command line.

        Searches for only files in path, not in deeper path and adds them into the widget.
        After finished, the fetched signal is emitted.
        """
        experimentList = cmdtools.run_command(f"artiq_client ls {self.path}").stdout
        experimentList = experimentList.split("\n")[:-1]  # The last one is always an empty string.
        self.fetched.emit(experimentList, self.widget)


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
        self.thread = _FileFinderThread(
            self.repositoryPath,
            self.explorerFrame.fileTree,
            self._addFile,
            self
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
        self.thread = _FileFinderThread(
            experimentPath,
            experimentFileItem,
            self._addFile,
            self
        )
        self.thread.start()

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
    def openExperiment(self):
        """Opens the experiment builder of the selected experiment.

        Once the openButton is clicked, this is called.
        If the selected element is a directory, it will be ignored.

        TODO(BECATRUE): Open the experiment builder. It will be implemented in Basic Runner project.
        """
        experimentFileItem = self.explorerFrame.fileTree.currentItem()
        experimentPath = self.fullPath(experimentFileItem)  # pylint: disable=unused-variable

    def fullPath(self, experimentFileItem: QTreeWidgetItem) -> str:
        """Finds the full path of the file item and returns it.

        Args:
            experimentFileItem: The file item to get its full path.
        """
        paths = [experimentFileItem.text(0)]
        while experimentFileItem.parent():
            experimentFileItem = experimentFileItem.parent()
            paths.append(experimentFileItem.text(0))
        paths.append(self.repositoryPath)
        return posixpath.join(*reversed(paths))

    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
