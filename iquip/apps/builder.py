"""App module for editting the build arguments and submitting the experiment."""

import json
import logging
from enum import IntEnum, unique
from typing import Any, Dict, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QDateTime, QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QAbstractButton, QButtonGroup, QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox, QGridLayout,
    QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QPushButton, QRadioButton,
    QSpinBox, QStackedWidget, QVBoxLayout, QWidget
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


# TODO(AIJUH): Add other scan type classes.
class _ScanEntry(_BaseEntry):
    """Entry class for a scannable object.
    
    Attributes:
        state: Each key and its value are:
          "selected": The name of the selected scannable type.
          "NoScan", "RangeScan", "CenterScan", and "ExplicitScan": The dictionary that contains 
            argument info of the corresponding scannable type.
        stackedWidget: The QStackedWidget that contains widgets of each scannable type.
        scanButtonGroup: The QButtonGroup that groups QRadiobuttons for selecting scan widgets.
        scanWidgets: The dictionary that contains each scan widget.
    """

    @unique
    # pylint: disable=invalid-name
    class ScanType(IntEnum):
        """Enum class for mapping id to each scannable type."""
        NoScan = 0
        RangeScan = 1
        CenterScan = 2
        ExplicitScan = 3

    # pylint: disable=too-many-locals
    def __init__(self, name: str, argInfo: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended.

        Args:
            name: See the attributes section.
            argInfo: Each key and its value are:
              default: The dictionary that describes arguments of the default scannable object.
              unit: The unit of the number value.
              scale: The scale factor that is multiplied to the number value.
              global_step: The step between values changed by the up and down button.
              global_min: The minimum value. (default=0.0)
              global_max: The maximum value. (default=99.99)
                If min > max, then they are swapped.
              ndecimals: The number of displayed decimals.
        """
        super().__init__(name, argInfo, parent=parent)
        self.state = self.initState()
        procdesc = self.initProcdesc()
        self.stackedWidget = QStackedWidget(self)
        buttonLayout = QHBoxLayout()
        self.scanButtonGroup = QButtonGroup(self)
        scanDict = {
            "NoScan": (_NoScan, "No scan"), 
            "RangeScan": (_RangeScan, "Range"),
            "CenterScan": (_CenterScan, "Center"), 
            "ExplicitScan": (_ExplicitScan, "Explicit")
        }
        self.scanWidgets = {}
        for scanType in _ScanEntry.ScanType:
            ty = scanType.name
            buttonId = scanType.value
            scanCls, buttonName = scanDict[ty]
            scanWidget = scanCls(procdesc, self.state[ty])
            self.stackedWidget.addWidget(scanWidget)
            self.scanWidgets[ty] = scanWidget
            button = QRadioButton(buttonName, self)
            buttonLayout.addWidget(button)
            self.scanButtonGroup.addButton(button, buttonId)
        self.scanButtonGroup.buttonClicked.connect(self.scanTypeClicked)
        selected = self.state["selected"]
        self.stackedWidget.setCurrentWidget(self.scanWidgets[selected])
        selectedScanType = _ScanEntry.ScanType[selected]
        selectedButton = self.scanButtonGroup.button(selectedScanType.value)
        selectedButton.setChecked(True)
        # layout
        scanLayout = QVBoxLayout()
        scanLayout.addLayout(buttonLayout)
        scanLayout.addWidget(self.stackedWidget)
        self.layout.addLayout(scanLayout)

    def initState(self) -> Dict[str, Any]:
        """Gets a dictionary that describes default parameters of all scannable types."""
        scale = self.argInfo["scale"]
        state = {
            "selected": "NoScan",
            "NoScan": {"value": 0.0, "repetitions": 1},
            "RangeScan": {"start": 0.0, "stop": 100.0 * scale, "npoints": 10,
                          "randomize": False, "seed": None},
            "CenterScan": {"center": 0. * scale, "step": 10. * scale,
                           "span": 100. * scale, "randomize": False,
                           "seed": None},
            "ExplicitScan": {"sequence": []}
        }
        if "default" in self.argInfo:
            defaults = self.argInfo["default"]
            if not isinstance(defaults, list):
                defaults = [defaults]
            state["selected"] = defaults[0]["ty"]
            for default in defaults:
                ty = default["ty"]
                if ty not in ("NoScan", "RangeScan", "CenterScan", "ExplicitScan"):
                    logger.warning("Unknown scan type: %s", ty)
                else:
                    state[ty] = default
        return state

    def initProcdesc(self) -> Dict[str, Any]:
        """Gets a procdesc dictionary that describes common parameters of the scannable object."""
        procdesc = {
            "unit": self.argInfo["unit"],
            "scale": self.argInfo["scale"],
            "global_step": self.argInfo["global_step"],
            "global_min": self.argInfo["global_min"],
            "global_max": self.argInfo["global_max"],
            "ndecimals": self.argInfo["ndecimals"]
        }
        return procdesc

    def value(self) -> Dict[str, Any]:
        """Overridden.
        
        Returns the dictionary of the selected scannable arguments.
        """
        selectedScanWidget = self.stackedWidget.currentWidget()
        return selectedScanWidget.scanArguments()

    @pyqtSlot(QAbstractButton)
    def scanTypeClicked(self, selectedButton: QAbstractButton):
        """Switches current scan widget in the stacked layout.
        
        Once a scan type button in the button group is clicked, this is called.

        Attributes:
            selectedButton: The clicked QRadioButton.
        """
        selectedScanType = _ScanEntry.ScanType(self.scanButtonGroup.id(selectedButton))
        self.stackedWidget.setCurrentWidget(self.scanWidgets[selectedScanType.name])


class _BaseScan(QWidget):
    """Base class for all scannable widgets.

    Attributes:
        scale: See argInfo in _ScanEntry.__init__().
        layout: The outermost layout.
        procdesc: Each key and its value are:
          unit, scale, global_step, global_min, global_max, ndecimals: 
            See argInfo in _ScanEntry.__init__().
    """

    def __init__(self, procdesc: Dict[str, Any], parent: Optional[QWidget] = None):
        """Extended.

        Args:
            procdesc: See the attributes section.
        """
        super().__init__(parent=parent)
        self.scale = procdesc["scale"]
        self.layout = QGridLayout(self)
        self.procdesc = procdesc

    def applyProperties(self, widget: QDoubleSpinBox):
        """Adds properties to the spin box widget.

        Attributes:
            widget: A QDoubleSpinWidget that has properties to set.
        """
        ndecimals, minVal, maxVal, step, unit = map(self.procdesc.get, ("ndecimals",
                                                                        "global_min", "global_max",
                                                                        "global_step", "unit"))
        widget.setDecimals(ndecimals)
        if minVal is None:
            minVal = 0.0
        if maxVal is None:
            maxVal = 99.99
        widget.setMinimum(minVal / self.scale)
        widget.setMaximum(maxVal / self.scale)
        widget.setSuffix(unit)
        widget.setSingleStep(step / self.scale)

    def scanArguments(self) -> Dict[str, Any]:
        """Returns the arguments of the scannable object.
        
        This must be overridden in the subclass.
        """
        raise NotImplementedError


class _NoScan(_BaseScan):
    """Widget for no scan in _ScanEntry.

    Attributes:
        valueSpinBox: QDoubleSpinBox for value argument inside state.
        repetitionsSpinBox: QSpinBox for repetitions argument inside state.
    """

    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
    ):
        """Extended.

        Args:
            state: Each key and its value are:
              value: The repeated value in the NoScan sequence.
              repetitions: The number to repeat the value in the NoScan sequence.
        """
        super().__init__(procdesc, parent=parent)
        self.valueSpinBox = QDoubleSpinBox(self)
        self.applyProperties(self.valueSpinBox)
        self.valueSpinBox.setValue(state["value"] / self.scale)
        self.repetitionsSpinBox = QSpinBox(self)
        self.repetitionsSpinBox.setMinimum(1)
        self.repetitionsSpinBox.setMaximum((1 << 31) - 1)
        self.repetitionsSpinBox.setValue(state["repetitions"])
        # layout
        self.layout.addWidget(QLabel("Value:", self), 0, 0)
        self.layout.addWidget(self.valueSpinBox, 0, 1)
        self.layout.addWidget(QLabel("Repetitions:"), 1, 0)
        self.layout.addWidget(self.repetitionsSpinBox, 1, 1)

    def scanArguments(self) -> Dict[str, Any]:
        """Overridden."""
        return {
            "ty": "NoScan",
            "value": self.valueSpinBox.value(),
            "repetitions": self.repetitionsSpinBox.value()
        }


class _RangeScan(_BaseScan):
    """Widget for range scan in _ScanEntry.

    Attributes:
        startSpinBox: QDoubleSpinBox for start argument inside state.
        stopSpinBox: QDoubleSpinBox for stop argument inside state.
        npointsSpinBox: QSpinBox for npoints argument inside state.
        randomizeCheckBox: QCheckBox for randomize argument inside state.
    """

    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
    ):
        """Extended.

        Args:
            state: Each key and its value are:
              start: The start point for the RangeScan sequence.
              stop: The end point for the RangeScan sequence.
              npoints: The number of points in the RangeScan sequence.
              randomize: The boolean value that decides whether to shuffle the RangeScan sequence.
        """
        super().__init__(procdesc, parent=parent)
        self.startSpinBox = QDoubleSpinBox(self)
        self.applyProperties(self.startSpinBox)
        self.startSpinBox.setValue(state["start"] / self.scale)
        self.npointsSpinBox = QSpinBox(self)
        self.npointsSpinBox.setMinimum(1)
        self.npointsSpinBox.setMaximum((1 << 31) - 1)
        self.npointsSpinBox.setValue(state["npoints"])
        self.stopSpinBox = QDoubleSpinBox(self)
        self.applyProperties(self.stopSpinBox)
        self.stopSpinBox.setValue(state["stop"] / self.scale)
        self.randomizeCheckBox = QCheckBox("Randomize", self)
        self.randomizeCheckBox.setChecked(state["randomize"])
        # layout
        self.layout.addWidget(QLabel("start:", self), 0, 0)
        self.layout.addWidget(self.startSpinBox, 0, 1)
        self.layout.addWidget(QLabel("npoints:", self), 1, 0)
        self.layout.addWidget(self.npointsSpinBox, 1, 1)
        self.layout.addWidget(QLabel("stop:", self), 2, 0)
        self.layout.addWidget(self.stopSpinBox, 2, 1)
        self.layout.addWidget(self.randomizeCheckBox, 3, 1)

    def scanArguments(self) -> Dict[str, Any]:
        """Overridden."""
        return {
            "ty": "RangeScan",
            "start": self.startSpinBox.value(),
            "stop": self.stopSpinBox.value(),
            "npoints": self.npointsSpinBox.value(),
            "randomize": self.randomizeCheckBox.isChecked(),
            "seed": None
        }


class _CenterScan(_BaseScan):
    """Widget for center scan in _ScanEntry.

    Attributes:
        centerSpinBox: QDoubleSpinBox for center argument inside state.
        spanSpinBox: QDoubleSpinBox for span argument inside state.
        stepSpinBox: QDoubleSpinBox for step argument inside state.
        randomizeCheckBox: QCheckBox for randomize argument inside state.
    """

    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
    ):
        """Extended.

        Args:
            state: Each key and its value are:
              center: The center point for the CenterScan sequence.
              span: The length of the CenterScan sequence.
              step: The size of step between each number in the CenterScan sequence.
              randomize: The boolean value that decides whether to shuffle the CenterScan sequence.
        """
        super().__init__(procdesc, parent=parent)
        self.centerSpinBox = QDoubleSpinBox(self)
        self.applyProperties(self.centerSpinBox)
        self.centerSpinBox.setValue(state["center"] / self.scale)
        self.spanSpinBox = QDoubleSpinBox(self)
        self.applyProperties(self.spanSpinBox)
        self.spanSpinBox.setValue(state["span"] / self.scale)
        self.stepSpinBox = QDoubleSpinBox(self)
        self.applyProperties(self.stepSpinBox)
        self.stepSpinBox.setValue(state["step"] / self.scale)
        self.randomizeCheckBox = QCheckBox("Randomize", self)
        self.randomizeCheckBox.setChecked(state["randomize"])
        # layout
        self.layout.addWidget(QLabel("center:", self), 0, 0)
        self.layout.addWidget(self.centerSpinBox, 0, 1)
        self.layout.addWidget(QLabel("span:", self), 1, 0)
        self.layout.addWidget(self.spanSpinBox, 1, 1)
        self.layout.addWidget(QLabel("step:", self), 2, 0)
        self.layout.addWidget(self.stepSpinBox, 2, 1)
        self.layout.addWidget(self.randomizeCheckBox, 3, 1)

    def scanArguments(self) -> Dict[str, Any]:
        """Overridden."""
        return {
            "ty": "CenterScan",
            "center": self.centerSpinBox.value(),
            "step": self.stepSpinBox.value(),
            "span": self.spanSpinBox.value(),
            "randomize": self.randomizeCheckBox.isChecked(),
            "seed": None
        }


class _ExplicitScan(_BaseScan):
    """Widget for explicit scan in _ScanEntry.

    Attributes:
        sequenceEdit: QLineEdit for sequence argument inside state.
    """

    def __init__(
        self,
        procdesc: Dict[str, Any],
        state: Dict[str, Any],
        parent: Optional[QWidget] = None
    ):
        """Extended.

        Args:
            state: A key and its value is:
              sequence: The list that represents the ExplicitScan sequence.
        """
        super().__init__(procdesc, parent=parent)
        self.sequenceEdit = QLineEdit(self)
        # layout
        self.layout.addWidget(QLabel("sequence:", self), 0, 0)
        self.layout.addWidget(self.sequenceEdit, 0, 1)
        self.sequenceEdit.setText(" ".join(str(x) for x in state["sequence"]))

    def scanArguments(self) -> Dict[str, Any]:
        """Overridden."""
        sequenceText = self.sequenceEdit.text()
        sequence = [float(x) for x in sequenceText.split()]
        return {
            "ty": "ExplicitScan",
            "sequence": sequence
        }


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
            scanArgs = self.argumentsFromListWidget(self.builderFrame.scanListWidget)
            schedOpts = self.argumentsFromListWidget(self.builderFrame.schedOptsListWidget)
        except ValueError:
            logger.exception("The submission is rejected because of an invalid argument.")
            return
        experimentArgs.update(scanArgs)
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
