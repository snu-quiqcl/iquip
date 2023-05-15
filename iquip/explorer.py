"""App module for showing the experiment list and opening an experiment."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

import qiwis

class ExplorerFrame(QWidget):
    """Frame for showing the experiment list and opening an experiment."""
    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.testLabel = QLabel("explorer", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.testLabel)


class ExplorerApp(qiwis.BaseApp):
    """App for showing the experiment list and opening an experiment."""
    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.explorerFrame = ExplorerFrame()

    def frames(self) -> Tuple[ExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
