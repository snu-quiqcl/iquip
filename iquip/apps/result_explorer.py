"""App module for showing the simple results and opening a result visualizer."""

from typing import Callable, List, Optional

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
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


class _ResultListThread(QThread):
    """QThread for obtaining the RID list from the proxy server.
    
    Signals:
        fetched(resultList):
          The RID list is fetched.
    """

    fetched = pyqtSignal(List[str])

    def __init__(self, callback: Callable[[List[str]], None], parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.fetched.connect(callback, type=Qt.QueuedConnection)


class ResultExplorerApp(qiwis.BaseApp):
    """App for showing the RID list and a specific h5 result."""

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
