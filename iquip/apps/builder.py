"""App module for editting the build arguments and submitting the experiment."""

import json
from typing import Any, Callable, Dict, Optional, Tuple, Union

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
        argInfo: The dictionary with the argument options.
        nameLabel: The label for showing the argument name.
        layout: The QHBoxLayout with the nameLabel.
    """

    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            name, argInfo: See the attributes section in _BaseEntry.
        """
        super().__init__(parent=parent)
        self.name = name
        self.argInfo = argInfo
        # widgets
        self.nameLabel = QLabel(name, self)
        # layout
        self.layout = QHBoxLayout(self)
        self.layout.addWidget(self.nameLabel)

    def value(self) -> Any:
        """Returns the entered or selected value.
        
        This must be overridden in the subclass.
        """
        raise NotImplementedError


class _BooleanEntry(_BaseEntry):
    """Entry class for a boolean value.
    
    Attributes:
        argInfo: Each key and its value are:
            (optional) default: The boolean value. 
              If not exist, the checkBox is set to False.
        checkBox: The checkbox showing the boolean value.
    """

    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(name, argInfo, parent=parent)
        # widgets
        self.checkBox = QCheckBox(self)
        self.checkBox.setChecked(self.argInfo.get("default", False))
        # layout
        self.layout.addWidget(self.checkBox)

    def value(self) -> bool:
        """Overridden.
        
        Returns the status of the checkBox.
        """
        return self.checkBox.isChecked()


class _EnumerationEntry(_BaseEntry):
    """Entry class for an enumeration value.
    
    Attributes:
        argInfo: Each key and its value are:
            choices: The pre-defined candidates.
            (optional) default: The string value.
              If not exist, the comboBox is set to the first candidate.
        comboBox: The combobox showing the enumeration value.
    """

    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(name, argInfo, parent=parent)
        choices = self.argInfo["choices"]
        # TODO(BECATRUE): Handling an empty choices will be implemented in the issue #55.
        if not choices:
            pass
        # widgets
        self.comboBox = QComboBox(self)
        self.comboBox.addItems(choices)
        self.comboBox.setCurrentText(self.argInfo.get("default", choices[0]))
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
        argInfo: Each key and its value are:
            (optional) default: The number value.
              If not exist, the spinBox is set to the min value.
            unit: The unit of the value.
            scale: The scale factor that is multiplied to the number value.
            step: The step between values changed by the up and down button.
            min: The minimum value. (default=0.0)
            max: The maximum value. (default=99.99)
            ndecimals: The number of displayed decimals.
            type: The type of the value.
              If "int", value() returns an integer value.
              Otherwise, it is regarded as a float value.
        spinBox: The spinbox showing the number value.
    
    TODO(BECATRUE): The operations of unit and scale will be concretized in Basic Runner project.
    TODO(BECATRUE): Handling the case where the default doesn't exist and the min is None
      will be implemented in Basic Runner project.
    """

    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(name, argInfo, parent=parent)
        scale, minValue, maxValue = map(self.argInfo.get, ("scale", "min", "max"))
        # widgets
        self.spinBox = QDoubleSpinBox(self)
        self.spinBox.setSuffix(self.argInfo["unit"])
        self.spinBox.setSingleStep(self.argInfo["step"] / scale)
        if minValue is not None:
            self.spinBox.setMinimum(minValue / scale)
        if maxValue is not None:
            self.spinBox.setMaximum(maxValue / scale)
        self.spinBox.setDecimals(self.argInfo["ndecimals"])
        self.spinBox.setValue(self.argInfo.get("default", minValue) / scale)
        # layout
        self.layout.addWidget(self.spinBox)

    def value(self) -> Union[int, float]:
        """Overridden.
        
        Returns the value of the comboBox.
        """
        typeCls = int if self.argInfo["type"] == "int" else float
        return typeCls(self.spinBox.value() * self.argInfo["scale"])


class _StringEntry(_BaseEntry):
    """Entry class for a string value.
    
    Attributes:
        argInfo: Each key and its value are:
            default: The string value.
              If not exist, the lineEdit is set to an empty string.
        lineEdit: The lineedit showing the string value.
    """

    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(name, argInfo, parent=parent)
        # widgets
        self.lineEdit = QLineEdit(self)
        self.lineEdit.setText(self.argInfo.get("default", ""))
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
        argsListWidget: The list widget with the build arguments.
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
        for argName, (argInfo, *_) in experimentInfo.arginfo.items():
            # TODO(BECATRUE): The other types such as 'Scannable'
            # will be implemented in Basic Runner project.
            entryCls = {
                "BooleanValue": _BooleanEntry,
                "StringValue": _StringEntry,
                "EnumerationValue": _EnumerationEntry,
                "NumberValue": _NumberEntry
            }[argInfo.pop("ty")]
            widget = entryCls(argName, argInfo)
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
