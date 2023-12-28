"""Module for common threads in apps."""

import logging
from typing import Dict, Optional

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal

from iquip.protocols import ExperimentInfo

logger = logging.getLogger(__name__)


class ExperimentInfoThread(QThread):
    """QThread for obtaining the experiment information from the proxy server.
    
    Signals:
        fetched(experimentInfos): Experiments infomation of the given experiment path is fetched.
          The experimentInfos is a dictionary with the experiments class name.
          Each value is the ExperimentInfo instance of the experiment class.
    
    Attributes:
        experimentPath: The path of the experiment file.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(dict)

    def __init__(
        self,
        experimentPath: str,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            See the attributes section.
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
            experimentInfos: Dict[str, ExperimentInfo] = {}
            for cls, info in data.items():
                experimentInfos[cls] = ExperimentInfo(**info)
            self.fetched.emit(experimentInfos)
        else:
            logger.info("The selected item is not an experiment file.")
