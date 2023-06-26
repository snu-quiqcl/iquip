"""App module for editting the build arguments and submitting the experiment."""

import json
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDoubleSpinBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout, QWidget
)

import qiwis
from iquip.protocols import ExperimentInfo

class _BaseEntry(QWidget):
    """Base class for all argument entries.

    This is a wrapper of each entry.
    In each subclass, value() must be implemented to return the selected value.

    Attributes:
        name: The argument name.
        nameLabel: The label for showing the argument name.
    """

    def __init__(self, name: str, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            name: See the attributes section in _BaseEntry.
        """
        super().__init__(parent=parent)
        self.name = name
        # widgets
        self.nameLabel = QLabel(name, self)
        # layout
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.nameLabel)
        self.setLayout(self.layout)

    def value(self) -> Any:
        """Returns the entered or selected value.
        
        This must be overridden in the subclass.
        """
        raise NotImplementedError


class _BooleanEntry(_BaseEntry):
    """Entry class for a boolean value."""

    def __init__(self, name: str, default: bool = False, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            default: The default value. If it does not exist, it is set to False.
        """
        super().__init__(name, parent=parent)
        # widgets
        self.checkBox = QCheckBox(self)
        self.checkBox.setChecked(default)
        # layout
        self.layout.addWidget(self.checkBox)

    def value(self) -> bool:
        """Overridden.
        
        Returns the status of the checkBox.
        """
        return self.checkBox.isChecked()


class _EnumerationEntry(_BaseEntry):
    """Entry class for an enumeration value."""

    def __init__(
        self,
        name: str,
        choices: List[str],
        default: Optional[str] = None,
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            choices: The pre-defined candidates.
            default: The default value. If it does not exist, it is set to the first candidate.
        """
        super().__init__(name, parent=parent)
        # widgets
        self.comboBox = QComboBox(self)
        for choice in choices:
            self.comboBox.addItem(choice)
        if choices:
            self.comboBox.setCurrentText(choices[0] if default is None else default)
        # layout
        self.layout.addWidget(self.comboBox)

    def value(self) -> str:
        """Overridden.
        
        Returns the value of the comboBox.
        """
        return self.comboBox.currentText()


class _NumberEntry(_BaseEntry):
    """Entry class for a number value.
    
    Attributes:
        scale: The scale factor that actually applies.
        type: The type of the value. If "int", value() returns an integer value.
    """

    def __init__(
        self,
        name: str,
        unit: str,
        scale: float,
        step: float,
        min: float,  # pylint: disable=redefined-builtin
        max: float,  # pylint: disable=redefined-builtin
        ndecimals: int,
        type: str,  # pylint: disable=redefined-builtin
        default: Optional[float] = None,
        parent: Optional[QWidget] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            unit: The unit of the value.
            step: The step between values changed by the up and down button.
            min: The minimum value.
            max: The maximum value.
            ndecimals: The maximum number of decimals.
            default: The default value. If it does not exist, it is set to the min value.
            scale, type: See the attributes section in _NumberEntry.
        """
        super().__init__(name, parent=parent)
        self.scale = scale
        self.type = type
        # widgets
        self.spinBox = QDoubleSpinBox(self)
        self.spinBox.setSuffix(unit)
        self.spinBox.setSingleStep(step / scale)
        self.spinBox.setRange(min / scale, max / scale)
        self.spinBox.setDecimals(ndecimals)
        self.spinBox.setValue((min if default is None else default) / scale)
        # layout
        self.layout.addWidget(self.spinBox)

    def value(self) -> Union[int, float]:
        """Overridden.
        
        Returns the value of the comboBox.
        """
        typeCls = int if self.type == "int" else float
        return typeCls(self.spinBox.value())


class _StringEntry(_BaseEntry):
    """Entry class for a string value."""

    def __init__(self, name: str, default: str = "", parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            default: The default value. If it does not exist, it is set to an empty string.
        """
        super().__init__(name, parent=parent)
        # widgets
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setText(default)
        # layout
        self.layout.addWidget(self.lineEdit)

    def value(self) -> str:
        """Overridden.
        
        Returns the value of the lineEdit.
        """
        return self.lineEdit.text()


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
        self.setLayout(layout)


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
      EnumerationValue: Set to one of the pre-defined candidates.
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
        """Initializes the build arguments entry.
        
        Args:
            experimentInfo: The experiment information.
        """
        for argName, _argInfo in experimentInfo.arginfo.items():
            argInfo = _argInfo[0]  # All the remaining elements are None.
            entryCls = {
                "BooleanValue": _BooleanEntry,
                "StringValue": _StringEntry,
                "EnumerationValue": _EnumerationEntry,
                "NumberValue": _NumberEntry
            }[argInfo.pop("ty")]
            widget = entryCls(argName, **argInfo)
            item = QListWidgetItem(self.builderFrame.argsListWidget)
            item.setSizeHint(widget.sizeHint())
            self.builderFrame.argsListWidget.addItem(item)
            self.builderFrame.argsListWidget.setItemWidget(item, widget)

    @pyqtSlot()
    def submit(self):
        """Submits the experiment with the build arguments.
        
        Once the submitButton is clicked, this is called.
        """
        experimentArgs = {}
        for row in range(self.builderFrame.argsListWidget.count()):
            item = self.builderFrame.argsListWidget.item(row)
            widget = self.builderFrame.argsListWidget.itemWidget(item)
            experimentArgs[widget.name] = widget.value()
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
