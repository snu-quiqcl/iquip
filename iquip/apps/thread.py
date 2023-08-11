"""Module for common threads in apps."""

import logging
from typing import Callable, Optional

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal

from iquip.protocols import ExperimentInfo

logger = logging.getLogger(__name__)


class ExperimentInfoThread(QThread):
    """QThread for obtaining the experiment information from the proxy server.
    
    Signals:
        fetched(experimentPath, experimentClsName, experimentInfo):
          The experiment infomation is fetched.
    
    Attributes:
        experimentPath: The path of the experiment file.
    """

    fetched = pyqtSignal(str, str, ExperimentInfo)

    def __init__(
        self,
        experimentPath: str,
        callback: Callable[[str, str, ExperimentInfo], None],
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            experimentPath: See the attributes section in ExperimentInfoThread.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.experimentPath = experimentPath
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.
        
        Fetches the experiment information from the proxy server.
        
        If the path is a directory, 500 Server error occurs.
        If the path is a non-experiment file, the server returns an empty dictionary.

        The experiment information is an instance of protocols.ExperimentInfo.
        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get("http://127.0.0.1:8000/experiment/info/",
                                    params={"file": self.experimentPath},
                                    timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the experiment information.")
            return
        if data:
            experimentClsName = next(iter(data))
            experimentInfo = data[experimentClsName]
            self.fetched.emit(
                self.experimentPath,
                experimentClsName,
                ExperimentInfo(**experimentInfo)
            )
        else:
            logger.info("The selected item is not an experiment file.")
