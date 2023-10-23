"""Module for common threads in apps."""

import logging
from typing import Optional

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from iquip.protocols import ExperimentInfo

logger = logging.getLogger(__name__)


class ExperimentInfoThread(QThread):
    """QThread for obtaining the experiment information from the proxy server.
    
    Signals:
        fetched(experimentPath, experimentClsName, experimentInfo):
          The experiment infomation is fetched.
    
    Attributes:
        experimentPath: The path of the experiment file.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(str, str, ExperimentInfo)

    def __init__(
        self,
        experimentPath: str,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            experimentPath, ip, port: See the attributes section.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.experimentPath = experimentPath
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Fetches the experiment information from the proxy server.
        
        If the path is a directory, 500 Server error occurs.
        If the path is a non-experiment file, the server returns an empty dictionary.

        The experiment information is an instance of protocols.ExperimentInfo.
        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/experiment/info/",
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
