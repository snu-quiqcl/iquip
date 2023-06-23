"""App module for editting the build arguments and submitting the experiment."""

import json
from abc import ABCMeta, abstractmethod
from typing import Any, Callable, Dict, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QCheckBox, QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QWidget
)

import qiwis
from iquip.protocols import ExperimentInfo

class _Entry(metaclass=ABCMeta):
    """Abstract class for an argument entry.

    In each subclass, value() must be implemented to return the selected value.

    Attributes:
        name: The argument name.
    """

    def __init__(self, name: str):
        """Extended.
        
        Args:
            name: See the attributes section in _Entry.
        """
        self.name = name

    @abstractmethod
    def value(self) -> Any:
        pass


class _BooleanEntry(_Entry, QCheckBox):
    """Entry class for a boolean value.

    If there is no default value, it is set to False.
    """

    def __init__(self, name: str, parent: Optional[QWidget] = None, **kwargs: Any):
        """Extended."""
        _Entry.__init__(name=name)
        QCheckBox.__init__(parent=parent)
        default = kwargs["default", False]
        self.initEntry(default)

    def initEntry(self, default: bool):
        """Initialize the entry.
        
        Attributes:
            default: The default value.
        """
        self.setCheckState(default)

    def value(self) -> bool:
        """Overridden."""
        return self.checkState()


class BuilderFrame(QWidget):
    """Frame for showing the build arguments and requesting to submit it.
    
    Attributes:
        submitButton: The button for submitting the experiment.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.argsListWidget = QListWidget(self)
        self.submitButton = QPushButton("Submit", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.argsListWidget)
        layout.addWidget(self.submitButton)


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

    There are four types of build arguments.
      BooleanValue: Set to True or False.
      EnumerateValue: Set to one of the pre-defined candidates.
      NumberValue: Set to a number with a specific unit and scale.
      StringValue: Set to a string.
    
    Attributes:
        builderFrame: The frame that shows the build arguments and requests to submit it.
        experimentPath: The path of the experiment file.
        experimentClsName: The class name of the experiment.
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
            experimentPath, experimentClsName: See the attributes section in BuilderApp.
            experimentInfo: The experiment information, a dictionary of protocols.ExperimentInfo.
        """
        super().__init__(name, parent=parent)
        self.experimentPath = experimentPath
        self.experimentClsName = experimentClsName
        self.builderFrame = BuilderFrame()
        self.initArgsEntry(ExperimentInfo(**experimentInfo))
        # connect signals to slots
        self.builderFrame.submitButton.clicked.connect(self.submit)

    def initArgsEntry(self, experimentInfo: ExperimentInfo):
        """Initialize the build arguments entry.
        
        Args:
            experimentInfo: The experiment information.
        """

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
