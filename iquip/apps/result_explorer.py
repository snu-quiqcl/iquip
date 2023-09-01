"""App module for showing the simple results and opening a result visualizer."""

from typing import Optional

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

import qiwis

class ResultExplorerFrame(QWidget):
    """Frame for showing the RID list and a specific h5 result."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.ridList = QListWidget(self)
        self.resultList = QListWidget(self)
        self.openButton = QPushButton("Visualize", self)
        # layout
        layout = QVBoxLayout
        layout.addWidget(self.ridList)
        layout.addWidget(self.resultList)
        layout.addWidget(self.openButton)
        self.setLayout(layout)
        

class ResultExplorerApp(qiwis.BaseApp):
    """App for showing the RID list and a specific h5 result."""

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
