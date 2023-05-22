"""App module for showing the experiment list and opening an experiment."""

import os
from typing import Optional, Tuple, Union

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import (
    QHBoxLayout, QPushButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
)

import qiwis

from .. import cmdtools

class ExplorerFrame(QWidget):  # pylint: disable=too-few-public-methods
    """Frame for showing the experiment list and opening an experiment."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.expStructure = QTreeWidget(self)
        self.expStructure.header().setVisible(False)
        self.reloadButton = QPushButton("Reload", self)
        self.openButton = QPushButton("Open", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.reloadButton)
        layout.addWidget(self.expStructure)
        layout.addWidget(self.openButton)


class ExplorerApp(qiwis.BaseApp):  # pylint: disable=too-few-public-methods
    """App for showing the experiment list and opening an experiment."""

    def __init__(self, name: str, masterPath: str = ".", parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.repositoryPath = os.path.join(masterPath, "repository")
        self.explorerFrame = ExplorerFrame()
        self.loadExpStructure()
        # connect signals to slots
        self.explorerFrame.reloadButton.clicked.connect(self.loadExpStructure)

    def loadExpStructure(self):
        """Loads the experiment file structure in self.explorerFrame.expStructure.

        It assumes that all experiment files are in self.repositoryPath.        
        """
        self.explorerFrame.expStructure.clear()
        self._addExpFile(self.repositoryPath, self.explorerFrame.expStructure)

    def _addExpFile(self, path: str, parent: Union[QTreeWidget, QTreeWidgetItem]):
        """Searches the sub elements and add them into self.explorerFrame.expStructure.
        
        This uses the DFS algorithm.
        1. Fetch the command result, which is a list of sub elements.
        2. If a directory, call _addExpFile() recursively.
        3. Otherwise, add it to self.explorerFrame.expStructure.
        """
        expList = cmdtools.run_command(f"artiq_client ls {path}").stdout
        expList = expList.split("\n")[:-1]  # The last one is always an empty string.
        for expFile in expList:
            if expFile.startswith("_"):
                continue
            expFileItem = QTreeWidgetItem(parent)
            if expFile.endswith("/"):
                expFileItem.setText(0, expFile[:-1])
                self._addExpFile(os.path.join(path, expFile), expFileItem)
            else:
                expFileItem.setText(0, expFile)
                
    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
