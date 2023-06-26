"""App module for editting the build arguments and submitting the experiment."""

import json
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QPushButton, QVBoxLayout, QWidget
)

import qiwis
from iquip.protocols import ExperimentInfo

class BuilderFrame(QWidget):
    """Frame for showing the build arguments and requesting to submit it.
    
    Attributes:
        submitButton: The button for submitting the experiment.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.submitButton = QPushButton("Submit", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.submitButton)


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
        except requests.exceptions.RequestException as err:
            print(err)
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
            print("The selected item is a non-experiment file.")


class ExperimentSubmitThread(QThread):
    """QThread for submitting the experiment with its build arguments.
    
    Signals:
        submitted(rid): The experiment is submitted. The rid is a run identifier.
    
    Attributes:
        experimentPath: The path of the experiment file.
        experimentArgs: The arguments of the experiment.
    """

    submitted = pyqtSignal(int)

    def __init__(
        self,
        experimentPath: str,
        experimentArgs: Dict[str, Any],
        callback: Callable[[int], None],
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            experimentPath, experimentArgs: See the attributes section in ExperimentSubmitThread.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.experimentPath = experimentPath
        self.experimentArgs = experimentArgs
        self.submitted.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.
        
        Submits the experiment to the proxy server.

        Whenever the experiment is submitted well regardless of whether it runs successfully or not,
        the server returns the run identifier.
        After submitted, the submitted signal is emitted.
        """
        try:
            params = {
                "file": self.experimentPath,
                "args": json.dumps(self.experimentArgs)
            }
        except TypeError:
            print("Failed to convert the build arguments to a JSON string.")
            return
        try:
            response = requests.get("http://127.0.0.1:8000/experiment/submit/",
                                    params=params,
                                    timeout=10)
            response.raise_for_status()
            rid = response.json()
        except requests.exceptions.RequestException as err:
            print(err)
            return
        self.submitted.emit(rid)


class BuilderApp(qiwis.BaseApp):
    """App for editting the build arguments and submitting the experiment.
    
    Attributes:
        builderFrame: The frame that shows the build arguments and requests to submit it.
    """

    def __init__(
        self,
        name: str,
        experimentPath: str,
        experimentClsName: str,
        experimentInfo: Dict[str, Any],
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            experimentPath: The path of the experiment file.
            experimentClsName: The class name of the experiment.
            experimentInfo: The experiment information, a dictionary of protocols.ExperimentInfo.
        """
        super().__init__(name, parent=parent)
        self.experimentPath = experimentPath
        self.experimentClsName = experimentClsName
        self.experimentInfo = ExperimentInfo(**experimentInfo)
        self.builderFrame = BuilderFrame()
        # connect signals to slots
        self.builderFrame.submitButton.clicked.connect(self.submit)

    @pyqtSlot()
    def submit(self):
        """Submits the experiment with the build arguments.
        
        Once the submitButton is clicked, this is called.

        TODO(BECATRUE): Apply the editted arguments. It will be implemented in Basic Runner project.
        """
        experimentArgs = {
            argName: argInfo[0]["default"]
            for argName, argInfo in self.experimentInfo.arginfo.items()
        }
        self.thread = ExperimentSubmitThread(
            self.experimentPath,
            experimentArgs,
            self.onSubmitted,
            self
        )
        self.thread.start()

    def onSubmitted(self, rid: int):
        """Prints the rid after submitted.

        This is the callback function of ExperimentSubmitThread.

        Args:
            rid: The run identifier of the submitted experiment.
        
        TODO(BECATRUE): It will be developed in Log Viewer project.
        """
        print(f"RID: {rid}")

    def frames(self) -> Tuple[BuilderFrame]:
        """Overridden."""
        return (self.builderFrame,)
