"""App module for showing the experiment list and opening an experiment."""

import os
from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

import qiwis

from .. import cmdtools

class ExplorerFrame(QWidget):  # pylint: disable=too-few-public-methods
    """Frame for showing the experiment list and opening an experiment."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.testLabel = QLabel("explorer", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.testLabel)


class ExplorerApp(qiwis.BaseApp):  # pylint: disable=too-few-public-methods
    """App for showing the experiment list and opening an experiment."""

    def __init__(self, name: str, masterPath: str = ".", parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.repositoryPath = os.path.join(masterPath, "repository")
        self.explorerFrame = ExplorerFrame()
        self.updateExpStructure()

    def updateExpStructure(self):
        pass

    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
