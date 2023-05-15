"""
App module for showing the experiment list and opening an experiment.
"""

from typing import Optional

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QLabel, QWidget

class ExplorerFrame(QWidget):
    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.testLabel = QLabel("explorer", self)
