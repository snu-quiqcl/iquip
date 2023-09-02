"""App module for showing the simple results and opening a result visualizer."""

import logging
from typing import Callable, List, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QLabel, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget

import qiwis

logger = logging.getLogger(__name__)


class ResultExplorerFrame(QWidget):
    """Frame for showing the RID list and the H5 format result of the selected RID.
    
    Attributes:
        ridList: The list widget for showing the submitted RIDs.
        resultInfoList: The list widget for showing the H5 format result of the selected RID.
        reloadButton: The button for reloading the ridList.
        openButton: The button for opening the selected result visualizer.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.ridList = QListWidget(self)
        self.resultInfoList = QListWidget(self)
        self.reloadButton = QPushButton("Reload", self)
        self.openButton = QPushButton("Visualize", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.ridList)
        layout.addWidget(self.resultInfoList)
        layout.addWidget(self.reloadButton)
        layout.addWidget(self.openButton)
        self.setLayout(layout)


class _RidListThread(QThread):
    """QThread for obtaining the RID list from the proxy server.
    
    Signals:
        fetched(ridList): The RID list is fetched.
    """

    fetched = pyqtSignal(list)

    def __init__(self, callback: Callable[[List[str]], None], parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            callback: The callback method called after this thread is finished.
              It will be called with one argument; the fetched RID list.
        """
        super().__init__(parent=parent)
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.
        
        Fetches the RID list from the proxy server.

        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get("http://127.0.0.1:8000/result/", timeout=10)
            response.raise_for_status()
            ridList = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the RID list.")
            return
        self.fetched.emit(ridList)


class ResultExplorerApp(qiwis.BaseApp):
    """App for showing the RID list and the H5 format result of the selected RID.
    
    Attributes:
        explorerFrame: The frame that shows the RID list and
          the H5 format result of the selected RID.
        ridListThread: The most recently executed _RidListThread instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.ridListThread: Optional[_RidListThread] = None
        self.explorerFrame = ResultExplorerFrame()
        self.loadRidList()
        # connect signals to slots
        self.explorerFrame.reloadButton.clicked.connect(self.loadRidList)

    @pyqtSlot()
    def loadRidList(self):
        """Loads the RID list in self.explorerFrame.ridList."""
        self.ridListThread = _RidListThread(self._addRid, self)
        self.ridListThread.start()

    def _addRid(self, ridList: List[str]):
        """Clears the original RID list and adds the RIDs into self.explorerFrame.ridList.
        
        Args:
            ridList: The fetched RID list.
        """
        for _ in range(self.explorerFrame.ridList.count()):
            item = self.explorerFrame.ridList.takeItem(0)
            del item
        for rid in ridList:
            widget = QLabel(str(rid), self.explorerFrame)
            item = QListWidgetItem(self.explorerFrame.ridList)
            self.explorerFrame.ridList.addItem(item)
            self.explorerFrame.ridList.setItemWidget(item, widget)

    def frames(self) -> Tuple[ResultExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
