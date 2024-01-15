"""App module for editting the build arguments and submitting the experiment."""

import json
import logging
from typing import Any, Dict, Optional, Tuple, Union
from collections import OrderedDict

import requests
from PyQt5.QtCore import QDateTime, QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox, QGridLayout, QHBoxLayout,
    QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton, QStackedWidget,
    QVBoxLayout, QWidget
)

import qiwis
from iquip.protocols import ExperimentInfo
from iquip.apps.thread import ExperimentInfoThread

logger = logging.getLogger(__name__)


def compute_scale(unit: str) -> Optional[float]:
    """Computes the scale of the given unit string based on ARTIQ units.
    
    Args:
        unit: The unit string e.g., "ns", "kHz".

    Returns:
        The scale of the given unit. For example, the scale of "ms" is 0.001.
        If the unit is not defined in ARTIQ, it returns None.
    """
    base_prefixes = "pnum_kMG"
    # See details at
    # https://github.com/m-labs/artiq/blob/master/artiq/language/units.py
    unit_specs = {
        "s": "pnum",
        "Hz": "mkMG",
        "dB": "",
        "V": "umk",
        "A": "um",
        "W": "num"
    }
    if unit in unit_specs:
        return 1
    if unit == "":
        return None
    prefix, base_unit = unit[0], unit[1:]
    if prefix not in base_prefixes or prefix == "_":
        return None
    if base_unit not in unit_specs:
        return None
    if prefix not in unit_specs[base_unit]:
        return None
    exponent = base_prefixes.index(prefix) - 4
    return 1000. ** exponent


logger = logging.getLogger(__name__)


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
        # widgets
        self.comboBox = QComboBox(self)
        self.comboBox.addItems(choices)
        if choices:
            self.comboBox.setCurrentText(self.argInfo.get("default", choices[0]))
        # layout
        self.layout.addWidget(self.comboBox)

    def value(self) -> str:
        """Overridden.
        
        Returns the value of the comboBox.
        """
        if self.argInfo["choices"]:
            return self.comboBox.currentText()
        raise ValueError(f"_EnumerationEntry {self.name} with the empty choice")


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
            If min > max, then they are swapped.
          ndecimals: The number of displayed decimals.
          type: The type of the value.
            If "int", value() returns an integer value.
            Otherwise, it is regarded as a float value.
        spinBox: The spinbox showing the number value.
        warningLabel: The label showing a warning.
          If the given scale is not typical for the unit, it shows a warning.
    """

    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(name, argInfo, parent=parent)
        unit, scale, minValue, maxValue = map(argInfo.get, ("unit", "scale", "min", "max"))
        # widgets
        self.spinBox = QDoubleSpinBox(self)
        self.spinBox.valueChanged.connect(self.updateToolTip)
        self.spinBox.setSuffix(unit)
        self.spinBox.setSingleStep(argInfo["step"] / scale)
        if minValue is None:
            minValue = 0.0
        if maxValue is None:
            maxValue = 99.99
        # TODO(BECATRUE): A WARNING log will be added after implementing the logger app.
        if minValue is not None and maxValue is not None and minValue > maxValue:
            minValue, maxValue = maxValue, minValue
        self.spinBox.setMinimum(minValue / scale)
        self.spinBox.setMaximum(maxValue / scale)
        self.spinBox.setDecimals(argInfo["ndecimals"])
        self.spinBox.setValue(argInfo.get("default", minValue) / scale)
        self.warningLabel = QLabel(self)
        scale_by_unit = compute_scale(unit)
        if scale_by_unit is not None and scale != scale_by_unit:
            self.warningLabel.setText("Not a typical scale for the unit.")
        # layout
        self.layout.addWidget(self.spinBox)
        self.layout.addWidget(self.warningLabel)

    def value(self) -> Union[int, float]:
        """Overridden.
        
        Returns the value of the comboBox.
        """
        typeCls = int if self.argInfo["type"] == "int" else float
        return typeCls(self.spinBox.value() * self.argInfo["scale"])

    @pyqtSlot()
    def updateToolTip(self):
        """Updates the tooltip to show the actual value.
        
        Once the value of the spinBox is changed, this is called.
        """
        self.setToolTip(str(self.value()))


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


class _DateTimeEntry(_BaseEntry):
    """Entry class for a date and time value.
    
    Attributes:
        checkBox: The checkbox for the availability of the dateTimeEdit.
        dateTimeEdit: The dateTimeEdit for the date and time value.
    """

    def __init__(self, name: str, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(name, {}, parent=parent)
        # widgets
        self.checkBox = QCheckBox(self)
        self.checkBox.setChecked(False)
        self.checkBox.stateChanged.connect(self.updateDateTimeEditState)
        currentDateTime = QDateTime.currentDateTime()
        self.dateTimeEdit = QDateTimeEdit(currentDateTime, self)
        self.dateTimeEdit.setCalendarPopup(True)
        self.dateTimeEdit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.dateTimeEdit.setEnabled(False)
        self.dateTimeEdit.setMinimumDateTime(currentDateTime)
        # layout
        self.layout.addWidget(self.checkBox)
        self.layout.addWidget(self.dateTimeEdit)

    @pyqtSlot()
    def updateDateTimeEditState(self):
        """Enables or disables the dateTimeEdit according to the state of the checkBox.
        
        Once the state of the checkBox is changed, this is called.
        """
        self.dateTimeEdit.setEnabled(self.checkBox.isChecked())

    def value(self) -> Optional[str]:
        """Overridden.
        
        Returns the value of the dateTimeEdit in ISO format if the checkBox is enabled.
        Otherwise returns None.
        """
        if self.checkBox.isChecked():
            return self.dateTimeEdit.dateTime().toString(Qt.ISODate)
        return None


class _ScanEntry(QWidget):
    """Entry class for a scannable object.
    
    Attributes:
        name: The name of the scannable object.
        state: The dictionary that describes argument information of each scan type.
        stackWidget: The QstackWidget that contains widget of each scan type.
        layout: The layout of _ScanEntry widget.
        widgets: The dictionary that contains widget of each scan type inside stackWidget.
        radioButtons: The dictionary that contains buttons of each scan type for stackWidget.
    """
    def __init__(
        self,
        name: str,
        argInfo: Dict[str, Any],
        parent: Optional[QWidget] = None
        ):
        """Extended.

        Args:
            name: See the attributes section.
            argInfo: Each key and its value are:
              default: The dictionary that describes arguments of a scannable object.
              unit: The unit of the number value.
              scale: The scale factor that is multiplied to the number value.
              global_step: The step between values changed by the up and down button.
              global_min: The minimum value. (default=float("-inf"))
              global_max: The maximum value. (default=float("inf"))
                If min > max, then they are swapped.
              ndecimals: The number of displayed decimals.
        """
        super().__init__(parent=parent)
        self.name = name
        procdesc = self.get_procdesc(argInfo)
        self.state = self.get_state(argInfo)
        self.stack = QStackedWidget(self)
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel(name, self), 0, 0)
        self.layout.addWidget(self.stack, 1, 1)

        self.widgets = OrderedDict()
        self.widgets["NoScan"] = _NoScan(procdesc, self.state["NoScan"])
        self.widgets["RangeScan"] = _RangeScan(procdesc, self.state["RangeScan"])
        self.widgets["CenterScan"] = _CenterScan(procdesc, self.state["CenterScan"])
        self.widgets["ExplicitScan"] = _ExplicitScan(self.state["ExplicitScan"])
        for widget in self.widgets.values():
            self.stack.addWidget(widget)

        self.radioButtons = OrderedDict()
        self.radioButtons["NoScan"] = QRadioButton("No scan")
        self.radioButtons["RangeScan"] = QRadioButton("Range")
        self.radioButtons["CenterScan"] = QRadioButton("Center")
        self.radioButtons["ExplicitScan"] = QRadioButton("Explicit")
        scan_type = QButtonGroup(self)
        buttonLayout = QGridLayout()
        for n, b in enumerate(self.radioButtons.values()):
            buttonLayout.addWidget(b, 0, n)
            scan_type.addButton(b)
            b.toggled.connect(self.scan_type_toggled)
        self.layout.addLayout(buttonLayout, 0, 1)
        selected = self.state["selected"]
        self.radioButtons[selected].setChecked(True)

    def get_state(self, argInfo):
        """Gets a state dictionary that describes key parameters of a scannable object.

        Creates a default state dictionary and updates it using the argInfo.

        Args:
            argInfo: A dictionary that contains argument information of each scannable type.
        """
        scale = argInfo["scale"]
        state = {
            "selected": "NoScan",
            "NoScan": {"value": 0.0, "repetitions": 1},
            "RangeScan": {"start": 0.0, "stop": 100.0*scale, "npoints": 10,
                          "randomize": False, "seed": None},
            "CenterScan": {"center": 0.*scale, "span": 100.*scale,
                           "step": 10.*scale, "randomize": False,
                           "seed": None},
            "ExplicitScan": {"sequence": []}
        }
        if "default" in argInfo:
            defaults = argInfo["default"]
            if not isinstance(defaults, list):
                defaults = [defaults]
            state["selected"] = defaults[0]["ty"]
            for default in reversed(defaults):
                ty = default["ty"]
                if ty == "NoScan":
                    state[ty]["value"] = default["value"]
                    state[ty]["repetitions"] = default["repetitions"]
                elif ty == "RangeScan":
                    state[ty]["start"] = default["start"]
                    state[ty]["stop"] = default["stop"]
                    state[ty]["npoints"] = default["npoints"]
                    state[ty]["randomize"] = default["randomize"]
                    state[ty]["seed"] = default["seed"]
                elif ty == "CenterScan":
                    for key in "center span step randomize seed".split():
                        state[ty][key] = default[key]
                elif ty == "ExplicitScan":
                    state[ty]["sequence"] = default["sequence"]
                else:
                    logger.warning("unknown default type: %s", ty)
        return state

    def get_procdesc(self, argInfo):
        """Gets a prodesc dictionary that describes common parameters of the scannable object.

        Args:
            argInfo: A dictionary that contains argument information of the scannable object.
        """
        procdesc = {
            "unit": argInfo["unit"],
            "scale": argInfo["scale"],
            "global_step": argInfo["global_step"],
            "ndecimals": argInfo["ndecimals"],
            "global_min": argInfo["global_min"],
            "global_max":  argInfo["global_max"]
        }
        return procdesc

    def scan_type_toggled(self):
        """Switches current scan widget at stacked layout in _ScanEntry.
        
        Once the checked button at radiobutton group changed, this is called.
        """
        for ty, button in self.radioButtons.items():
            if button.isChecked():
                self.stack.setCurrentWidget(self.widgets[ty])
                self.state["selected"] = ty
                break


class _NoScan(QWidget):
    """An widget for a NoScan type in Scannable Entry.

    Attributes:
        layout: The layout of _NoScan widget.
        procdesc: The dummy attribute that will be discard at the next PR.
        state: The dummy attribute that will be discard at next PR.
    """
    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
        ):
        """Extended.

        Args:
            procdesc: Each key and its value are:
              unit: The unit of the number value.
              scale: The scale factor that is multiplied to the number value.
              global_step: The step between values changed by the up and down button.
              global_min: The minimum value. (default=float("-inf"))
              global_max: The maximum value. (default=float("inf"))
                If min > max, then they are swapped.
              ndecimals: The number of displayed decimals.
            state:
              value: The repeated number value in scannable sequence.
              repetitions: A number to repeat the value in scnnable sequence.
        """
        super().__init__(parent=parent)
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel("NoScan:", self), 0, 0)
        self.procdesc = procdesc
        self.state = state


class _RangeScan(QWidget):
    """An widget for a RangeScan type in Scannable Entry.

    Attributes:
        layout: The layout of _RangeScan widget.
        procdesc: The dummy attribute that will be discard at the next PR.
        state: The dummy attribute that will be discard at next PR.
    """
    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
        ):
        """Extended.

        Args:
            procdesc: Each key and its value are:
              unit: The unit of the number value.
              scale: The scale factor that is multiplied to the number value.
              global_step: The step between values changed by the up and down button.
              global_min: The minimum value. (default=float("-inf"))
              global_max: The maximum value. (default=float("inf"))
              If min > max, then they are swapped.
              ndecimals: The number of displayed decimals.
            state:
              start: The start point of the scanning sequence.
              stop: The end point of the scanning sequence.
              npoints: The number of points to be genereated inside the scanning sequence.
              randomize: A boolean value that determines 
                whether or not to shuffle the scanning sequence.
        """
        super().__init__(parent=parent)
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel("RangeScan:", self), 0, 0)
        self.procdesc = procdesc
        self.state = state


class _CenterScan(QWidget):
    """Widget for a CenterScan type in Scannable Entry.
    
    Attributes:
        layout: The layout of _CenterScan widget.
        procdesc: The dummy attribute that will be discard at the next PR.
        state: The dummy attribute that will be discard at next PR.
    """
    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
        ):
        """Extended.

        Args:
            procdesc: Each key and its value are:
              unit: The unit of the number value.
              scale: The scale factor that is multiplied to the number value.
              global_step: The step between values changed by the up and down button.
              global_min: The minimum value. (default=float("-inf"))
              global_max: The maximum value. (default=float("inf"))
              If min > max, then they are swapped.
              ndecimals: The number of displayed decimals.
            state:
              span: The length of the scanning sequence.
              step: The size of step between each number at the scanning sequence.
              center: The center point of the scanning sequence.
              randomize: A boolean value that determines 
                whether or not to shuffle the scanning sequence.
        """
        super().__init__(parent=parent)
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel("CenterScan:", self), 0, 0)
        self.procdesc = procdesc
        self.state = state


class _ExplicitScan(QWidget):
    """Widget for a ExplicitScan type in Scannable Entry.
    
    Attributes:
        layout: The layout of _ExplicitScan widget.
        state: The dummy attribute that will be discard at next PR.
    """
    def __init__(
        self,
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
        ):
        """Extended.

        Args:
            procdesc: Each key and its value are:
              unit: The unit of the number value.
              scale: The scale factor that is multiplied to the number value.
              global_step: The step between values changed by the up and down button.
              global_min: The minimum value. (default=float("-inf"))
              global_max: The maximum value. (default=float("inf"))
                If min > max, then they are swapped.
              ndecimals: The number of displayed decimals.
            state:
              sequence: The sequnce that describes the scanning sequence.
        """
        super().__init__(parent=parent)
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel("ExplicitScan:", self), 0, 0)
        self.state = state


class BuilderFrame(QWidget):
    """Frame for showing the build arguments and requesting to submit it.
    
    Attributes:
        experimentNameLabel: The label for showing the experiment name.
        experimentClsNameLabel: The label for showing the class name of the experiment.
        argsListWidget: The list widget with the build arguments.
        scanListWidget: The list widget with the scannable arguments.
        reloadArgsButton: The button for reloading the build arguments.
        schedOptsListWidget: The list widget with the schedule options.
        submitButton: The button for submitting the experiment.
    """

    def __init__(
        self,
        experimentName: str,
        experimentClsName: str,
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            experimentName: The experiment name, the name field of protocols.ExperimentInfo.
            experimentClsName: The class name of the experiment.
        """
        super().__init__(parent=parent)
        # widgets
        self.experimentNameLabel = QLabel(f"Name: {experimentName}", self)
        self.experimentClsNameLabel = QLabel(f"Class: {experimentClsName}", self)
        self.argsListWidget = QListWidget(self)
        self.scanListWidget = QListWidget(self)
        self.reloadArgsButton = QPushButton("Reload", self)
        self.schedOptsListWidget = QListWidget(self)
        self.submitButton = QPushButton("Submit", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.experimentNameLabel)
        layout.addWidget(self.experimentClsNameLabel)
        layout.addWidget(self.argsListWidget)
        layout.addWidget(self.scanListWidget)
        layout.addWidget(self.reloadArgsButton)
        layout.addWidget(self.schedOptsListWidget)
        layout.addWidget(self.submitButton)


class _ExperimentSubmitThread(QThread):
    """QThread for submitting the experiment with its build arguments.
    
    Signals:
        submitted(rid): The experiment is submitted. The rid is a run identifier.
    
    Attributes:
        experimentPath: The path of the experiment file.
        experimentClsName: The class name of the experiment.
        experimentArgs: The arguments of the experiment.
        schedOpts: The scheduler options; pipeline, priority, and timed.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    submitted = pyqtSignal(int)

    def __init__(
        self,
        experimentPath: str,
        experimentClsName: str,
        experimentArgs: Dict[str, Any],
        schedOpts: Dict[str, Any],
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.experimentPath = experimentPath
        self.experimentClsName = experimentClsName
        self.experimentArgs = experimentArgs
        self.schedOpts = schedOpts
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Submits the experiment to the proxy server.

        Whenever the experiment is submitted well regardless of whether it runs successfully or not,
        the server returns the run identifier.
        """
        try:
            params = {
                "file": self.experimentPath,
                "cls": self.experimentClsName,
                "args": json.dumps(self.experimentArgs)
            }
        except TypeError:
            logger.exception("Failed to convert the build arguments to a JSON string.")
            return
        params.update(self.schedOpts)
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/experiment/submit/",
                                    params=params,
                                    timeout=10)
            response.raise_for_status()
            rid = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to submit the experiment.")
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
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        builderFrame: The frame that shows the build arguments and requests to submit it.
        experimentPath: The path of the experiment file.
        experimentClsName: The class name of the experiment.
        experimentSubmitThread: The most recently executed _ExperimentSubmitThread instance.
        experimentInfoThread: The most recently executed ExperimentInfoThread instance.
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
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.experimentPath = experimentPath
        self.experimentClsName = experimentClsName
        self.experimentSubmitThread: Optional[_ExperimentSubmitThread] = None
        self.experimentInfoThread: Optional[ExperimentInfoThread] = None
        self.builderFrame = BuilderFrame(experimentInfo["name"], experimentClsName)
        self.initArgsEntry(ExperimentInfo(**experimentInfo))
        self.initSchedOptsEntry()
        # connect signals to slots
        self.builderFrame.reloadArgsButton.clicked.connect(self.reloadArgs)
        self.builderFrame.submitButton.clicked.connect(self.submit)

    def initArgsEntry(self, experimentInfo: ExperimentInfo):
        """Initializes the build arguments entry.
        
        Args:
            experimentInfo: The experiment information.
        """
        for argName, (argInfo, *_) in experimentInfo.arginfo.items():
            argType = argInfo.pop("ty")
            entryCls = {
                "BooleanValue": _BooleanEntry,
                "StringValue": _StringEntry,
                "EnumerationValue": _EnumerationEntry,
                "NumberValue": _NumberEntry,
                "Scannable": _ScanEntry
            }[argType]
            widget = entryCls(argName, argInfo)
            listWidget = (self.builderFrame.scanListWidget if argType == "Scannable"
                          else self.builderFrame.argsListWidget)
            item = QListWidgetItem(listWidget)
            item.setSizeHint(widget.sizeHint())
            listWidget.addItem(item)
            listWidget.setItemWidget(item, widget)

    def initSchedOptsEntry(self):
        """Initializes the scheduler options entry.
        
        There are three options; pipeline, priority, and timed.
        """
        pipelineInfo = {
            "default": "main"
        }
        priorityInfo = {
            "default": 1,
            "unit": "",
            "scale": 1,
            "step": 1,
            "min": 1,
            "max": 10,
            "ndecimals": 0,
            "type": "int"
        }
        visualizeInfo = {
            "default": False
        }
        for widget in (
            _StringEntry("pipeline", pipelineInfo),
            _NumberEntry("priority", priorityInfo),
            _DateTimeEntry("timed"),
            _BooleanEntry("visualize", visualizeInfo)
        ):
            item = QListWidgetItem(self.builderFrame.schedOptsListWidget)
            item.setSizeHint(widget.sizeHint())
            self.builderFrame.schedOptsListWidget.addItem(item)
            self.builderFrame.schedOptsListWidget.setItemWidget(item, widget)

    @pyqtSlot()
    def reloadArgs(self):
        """Reloads the build arguments.
        
        Once the reloadArgsButton is clicked, this is called.
        """
        self.experimentInfoThread = ExperimentInfoThread(
            self.experimentPath,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.experimentInfoThread.fetched.connect(self.onReloaded, type=Qt.QueuedConnection)
        self.experimentInfoThread.finished.connect(self.experimentInfoThread.deleteLater)
        self.experimentInfoThread.start()

    @pyqtSlot(dict)
    def onReloaded(self, experimentInfos: Dict[str, ExperimentInfo]):
        """Clears the original arguments entry and re-initializes them.
        
        Args:
            See thread.ExperimentInfoThread.fetched signal.
        """
        experimentInfo = experimentInfos[self.experimentClsName]
        for _ in range(self.builderFrame.argsListWidget.count()):
            item = self.builderFrame.argsListWidget.takeItem(0)
            del item
        self.initArgsEntry(experimentInfo)

    def argumentsFromListWidget(self, listWidget: QListWidget) -> Dict[str, Any]:
        """Gets arguments from the given list widget and returns them.
        
        Args:
            listWidget: The QListWidget containing _BaseEntry instances.

        Returns:
            A dictionary of arguments.
            Each key is the argument name and its value is the argument value.
        """
        args = {}
        for row in range(listWidget.count()):
            item = listWidget.item(row)
            widget = listWidget.itemWidget(item)
            args[widget.name] = widget.value()
        return args

    @pyqtSlot()
    def submit(self):
        """Submits the experiment with the build arguments.
        
        Once the submitButton is clicked, this is called.
        """
        try:
            experimentArgs = self.argumentsFromListWidget(self.builderFrame.argsListWidget)
            schedOpts = self.argumentsFromListWidget(self.builderFrame.schedOptsListWidget)
        except ValueError:
            logger.exception("The submission is rejected because of an invalid argument.")
            return
        self.experimentSubmitThread = _ExperimentSubmitThread(
            self.experimentPath,
            self.experimentClsName,
            experimentArgs,
            schedOpts,
            self.proxy_ip,
            self.proxy_port,
            self
        )
        self.experimentSubmitThread.submitted.connect(self.onSubmitted, type=Qt.QueuedConnection)
        self.experimentSubmitThread.finished.connect(self.experimentSubmitThread.deleteLater)
        self.experimentSubmitThread.start()

    def onSubmitted(self, rid: int):
        """Sends the rid to the logger after submitted.

        This is the slot for _ExperimentSubmitThread.submitted.

        Args:
            rid: The run identifier of the submitted experiment.
        """
        logger.info("RID: %d", rid)

    def frames(self) -> Tuple[Tuple[str, BuilderFrame]]:
        """Overridden."""
        return (("", self.builderFrame),)
