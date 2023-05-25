"""App module for showing the experiment list and opening an experiment."""

import posixpath
import os
from typing import Optional, Tuple, Union

from PyQt5.QtCore import QObject, pyqtSlot
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


class ExplorerApp(qiwis.BaseApp):  # pylint: disable=too-few-public-methods
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
        self.explorerFrame.reloadButton.clicked.connect(self.loadFileTree)
        self.explorerFrame.openButton.clicked.connect(self.openExperiment)

    @pyqtSlot()
    def loadFileTree(self):
        """Loads the experiment file structure in self.explorerFrame.fileTree.

        It assumes that all experiment files are in self.repositoryPath.
        """
        self.explorerFrame.fileTree.clear()
        self._addFile(self.repositoryPath, self.explorerFrame.fileTree)

    def _addFile(self, path: str, parent: Union[QTreeWidget, QTreeWidgetItem]):
        """Searches the sub elements and add them into self.explorerFrame.fileTree.

        This uses the DFS algorithm.
        1. Fetch the command result, which is a list of sub elements.
        2. If a directory, call _addFile() recursively.
        3. Otherwise, add it to self.explorerFrame.fileTree.
        """
        experimentList = cmdtools.run_command(f"artiq_client ls {path}").stdout
        experimentList = experimentList.split("\n")[:-1]  # The last one is always an empty string.
        for experimentFile in experimentList:
            if experimentFile.endswith("/") and not experimentFile.startswith("_"):
                experimentFileItem = QTreeWidgetItem(parent)
                experimentFileItem.setText(0, experimentFile[:-1])
                self._addFile(posixpath.join(path, experimentFile), experimentFileItem)
            elif experimentFile.endswith(".py"):
                experimentFileItem = QTreeWidgetItem(parent)
                experimentFileItem.setText(0, experimentFile)

    @pyqtSlot()
    def openExperiment(self):
        """Opens the experiment builder of the selected experiment.

        Once the openButton is clicked, this is called.
        If the selected element is a directory, it will be ignored.

        TODO(BECATRUE): Open the experiment builder.
        """
        experimentFileItem = self.explorerFrame.fileTree.currentItem()
        if experimentFileItem.childCount():
            return
        experimentPath = experimentFileItem.text(0)
        while experimentFileItem.parent():
            experimentFileItem = experimentFileItem.parent()
            experimentPath = posixpath.join(experimentFileItem.text(0), experimentPath)
        experimentPath = posixpath.join(self.repositoryPath, experimentPath)


    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
