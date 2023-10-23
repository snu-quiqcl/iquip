"""App module for showing the simple results and opening a result visualizer."""

import io
import json
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import h5py
import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QLabel, QListWidget, QListWidgetItem, QPushButton, QTreeWidget, QTreeWidgetItem,
    QVBoxLayout, QWidget
)

import qiwis

logger = logging.getLogger(__name__)


class ResultExplorerFrame(QWidget):
    """Frame for showing the RID list and the H5 format result of the selected RID.
    
    Attributes:
        ridList: The list widget for showing the submitted RIDs.
        resultInfoTree: The tree widget for showing the H5 format result of the selected RID.
        reloadButton: The button for reloading the ridList.
        openButton: The button for opening the selected result visualizer.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.ridList = QListWidget(self)
        self.resultInfoTree = QTreeWidget(self)
        self.resultInfoTree.setColumnCount(2)
        self.resultInfoTree.header().setVisible(False)
        self.reloadButton = QPushButton("Reload", self)
        self.openButton = QPushButton("Visualize", self)
        self.openButton.setEnabled(False)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.ridList)
        layout.addWidget(self.resultInfoTree)
        layout.addWidget(self.reloadButton)
        layout.addWidget(self.openButton)
        self.setLayout(layout)


class _RidListThread(QThread):
    """QThread for obtaining the RID list from the proxy server.
    
    Signals:
        fetched(ridList): The RID list is fetched.

    Attributes:
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(list)

    def __init__(
        self,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            ip, port: See the attributes section.
        """
        super().__init__(parent=parent)
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Fetches the RID list from the proxy server.

        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/result/", timeout=10)
            response.raise_for_status()
            ridList = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the RID list.")
            return
        self.fetched.emit(ridList)


class _H5FileThread(QThread):
    """QThread for obtaining the H5 format result file from the proxy server.
    
    Signals:
        fetched(results):
          The H5 format result file is fetched.
          The "results" is a dictionary with the following keys.
            expid: The experiment identifier containing submitted information.
            datasets: A dictionary with datasets.
              Each key is a dataset name, and its value is a numpy array.
            submission_time: The submission date-time in ISO format string.
            start_time: The start date-time in ISO format string.
            run_time: The run date-time in ISO format string.
            visualize: True if the visualize option is checked, otherwise False.

    Attributes:
        ip: The proxy server IP address.
        port: The proxy server PORT number.
        rid: The run identifier value of the target executed experiment.
    """

    fetched = pyqtSignal(dict)

    def __init__(
        self,
        rid: str,
        ip: str,
        port: int,
        callback: Callable[[Dict[str, Any]], None],
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            rid, ip, port: See the attributes section.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.rid = rid
        self.ip = ip
        self.port = port
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.

        Fetches the H5 format result file and extracts results.

        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get(
                f"http://{self.ip}:{self.port}/result/{self.rid}/h5/",
                timeout=10
            )
            response.raise_for_status()
            file_contents = response.content
            results = {}
            with h5py.File(io.BytesIO(file_contents), "r") as f:
                # expid
                expid_str = f["expid"][()].decode("utf-8")  # pylint: disable=no-member
                results["expid"] = json.loads(expid_str)
                # datasets
                results["datasets"] = {}
                for dataset_name in f["datasets"].keys():
                    results["datasets"][dataset_name] = f["datasets"][dataset_name][()]
                # time
                for dataset_name in ("submission_time", "start_time", "run_time"):
                    results[dataset_name] = f[dataset_name][0].decode("utf-8")
                # visualize
                results["visualize"] = f["visualize"][0]
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the H5 format result file.")
            return
        except OSError:
            logger.exception("Failed to open the H5 format result file.")
            return
        except KeyError:
            logger.exception("Invalid H5 format result file.")
            return
        self.fetched.emit(results)


class ResultExplorerApp(qiwis.BaseApp):
    """App for showing the RID list and the H5 format result of the selected RID.
    
    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        explorerFrame: The frame that shows the RID list and
          the H5 format result of the selected RID.
        ridListThread: The most recently executed _RidListThread instance.
        h5FileThread: The most recently executed _H5FileThread instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.ridListThread: Optional[_RidListThread] = None
        self.h5FileThread: Optional[_H5FileThread] = None
        self.explorerFrame = ResultExplorerFrame()
        self.loadRidList()
        # connect signals to slots
        self.explorerFrame.ridList.itemDoubleClicked.connect(self.fetchResults)
        self.explorerFrame.reloadButton.clicked.connect(self.loadRidList)

    @pyqtSlot()
    def loadRidList(self):
        """Loads the RID list in self.explorerFrame.ridList."""
        self.ridListThread = _RidListThread(
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.ridListThread.fetched.connect(self._updateRidList, type=Qt.QueuedConnection)
        self.ridListThread.finished.connect(self.ridListThread.deleteLater)
        self.ridListThread.start()

    def _updateRidList(self, ridList: List[str]):
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

    @pyqtSlot(QListWidgetItem)
    def fetchResults(self, ridItem: QListWidgetItem):
        """Fetches the results of the double-clicked RID.

        After fetching througth _H5FileThread, shows them in self.explorerFrame.
        
        Args:
            ridItem: The doubled-clicked RID item in self.explorerFrame.ridList.
        """
        self.explorerFrame.resultInfoTree.clear()
        widget = self.explorerFrame.ridList.itemWidget(ridItem)
        rid = widget.text()
        self.h5FileThread = _H5FileThread(
            rid,
            self.proxy_ip,
            self.proxy_port,
            self.showResults,
            self
        )
        self.h5FileThread.finished.connect(self.h5FileThread.deleteLater)
        self.h5FileThread.start()

    def showResults(self, resultDict: Dict[str, Any]):
        """Shows the results in self.explorerFrame.resultInfoTree.

        Args:
            resultDict: The dictionary with results of the selected RID.
        """
        self._addResults(resultDict, self.explorerFrame.resultInfoTree)
        visualize = resultDict.get("visualize", False)
        self.explorerFrame.openButton.setEnabled(visualize)

    def _addResults(self, resultDict: Dict[str, Any], widget: Union[QTreeWidget, QTreeWidgetItem]):
        """Adds the results into the children of the widget.
        
        Args:
            resultDict: The dictionary with results.
              If a value is also a dictionary, it will be added below recursively.
            widget: The parent widget to which the results is added.
        """
        for name, result in resultDict.items():
            item = QTreeWidgetItem(widget)
            item.setText(0, name)
            if isinstance(result, dict):
                self._addResults(result, item)
            else:
                item.setText(1, str(result))

    def frames(self) -> Tuple[ResultExplorerFrame]:
        """Overridden."""
        return (self.explorerFrame,)
