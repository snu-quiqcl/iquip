"""App module for editting the build arguments and submitting the experiment."""

import json
import logging
from collections import OrderedDict
import random
from typing import Any, Dict, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QDateTime, QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QCheckBox, QComboBox, QDateTimeEdit, QDoubleSpinBox, QSpinBox, QLabel, QLineEdit,
    QListWidget, QListWidgetItem, QPushButton, QVBoxLayout, QHBoxLayout, QGridLayout,
    QWidget, QStackedWidget, QRadioButton, QButtonGroup
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


class BuilderFrame(QWidget):
    """Frame for showing the build arguments and requesting to submit it.
    
    Attributes:
        experimentNameLabel: The label for showing the experiment name.
        experimentClsNameLabel: The label for showing the class name of the experiment.
        argsStackWidget: The stack widget that contains two list widget.
        argsListWidget: The list widget with the build arguments.
        scanListWidget: The list widget with the scannable arguments.
        reloadArgsButton: The button for reloading the build arguments.
        schedOptsListWidget: The list widget with the schedule options.
        submitButton: The button for submitting the experiment.
        radioButtons: The button dictionary that has scannable or NonScan buttons.
        argType: The button group for selecting whether scannable or NonScan.
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
        self.argsStackWidget = QStackedWidget(self)
        self.argsListWidget = QListWidget(self)
        self.scanListWidget = QListWidget(self)
        self.reloadArgsButton = QPushButton("Reload", self)
        self.schedOptsListWidget = QListWidget(self)
        self.submitButton = QPushButton("Submit", self)
        self.radioButtons = OrderedDict()
        self.radioButtons["NonScan"] = QRadioButton("NonScan")
        self.radioButtons["Scannable"] = QRadioButton("Scannable")
        self.argType = QButtonGroup(self)
        # layout
        self.argsStackWidget.addWidget(self.argsListWidget)
        self.argsStackWidget.addWidget(self.scanListWidget)
        layout = QVBoxLayout(self)
        buttonLayout = QGridLayout()
        layout.addWidget(self.experimentNameLabel)
        layout.addWidget(self.experimentClsNameLabel)
        for n, b in enumerate(self.radioButtons.values()):
            buttonLayout.addWidget(b, 0, n)
            self.argType.addButton(b)
        layout.addLayout(buttonLayout)
        layout.addWidget(self.argsStackWidget)
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
        for button in self.builderFrame.radioButtons.values():
            button.toggled.connect(self.buttonToggled)
        self.builderFrame.radioButtons["NonScan"].setChecked(True)

    def initArgsEntry(self, experimentInfo: ExperimentInfo):
        """Initializes the build arguments entry.
        
        Args:
            experimentInfo: The experiment information.
        """
        nonScanEntry = ["BooleanValue", "StringValue", "EnumerationValue", "NumberValue"]
        for argName, (argInfo, *_) in experimentInfo.arginfo.items():
            # TODO(BECATRUE): The other types such as 'Scannable'
            # will be implemented in Basic Runner project.
            argType = argInfo.pop("ty")
            if argType in nonScanEntry:
                entryCls = {
                    "BooleanValue": _BooleanEntry,
                    "StringValue": _StringEntry,
                    "EnumerationValue": _EnumerationEntry,
                    "NumberValue": _NumberEntry,
                }[argType]
                widget = entryCls(argName, argInfo)
                item = QListWidgetItem(self.builderFrame.argsListWidget)
                item.setSizeHint(widget.sizeHint())
                self.builderFrame.argsListWidget.addItem(item)
                self.builderFrame.argsListWidget.setItemWidget(item, widget)
            elif argType == "Scannable":
                widget = _ScanEntry(argName, argInfo)
                item = QListWidgetItem(self.builderFrame.scanListWidget)
                item.setSizeHint(widget.sizeHint())
                self.builderFrame.scanListWidget.addItem(item)
                self.builderFrame.scanListWidget.setItemWidget(item, widget)
            else:
                # print format should be checked
                logger.warning("Invalid argument type at experiment: %s, argument name: %s",
                               experimentInfo["name"], argName)

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

    @pyqtSlot()
    def buttonToggled(self):
        """Selects scanListWidget or argsListWidget at argument layout.
        
        Once the selected button in radioButtons at BuilderFrame is changed, this is called.
        """
        frame = self.builderFrame
        for ty, button in self.builderFrame.radioButtons.items():
            if button.isChecked():
                if ty == 'NonScan':
                    self.builderFrame.argsStackWidget.setCurrentWidget(frame.argsListWidget)
                else:
                    self.builderFrame.argsStackWidget.setCurrentWidget(frame.scanListWidget)
                break

    def frames(self) -> Tuple[Tuple[str, BuilderFrame]]:
        """Overridden."""
        return (("", self.builderFrame),)

class _RangeScan(QWidget):
    """An widget for a RangeScan type in Scannable Entry.

    Attributes:
        layout: The layout of _RangeScan widget.
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
                start: Start point for range scan.
                stop: End point for range scan.
                npoints: The number of points to be genereated in given range.
                randomize: Boolean value that decides whether to shuffle the order of scans.
        """
        super().__init__(parent=parent)
        scale = procdesc["scale"]
        def apply_properties(widget):
            """Adds properties to the SpinBox widget.

            Attributes:
               widget: A QDOubleSpinWidget that has properties to set. 
            """
            widget.setDecimals(procdesc["ndecimals"])
            if procdesc["global_min"] is not None:
                widget.setMinimum(procdesc["global_min"]/scale)
            else:
                widget.setMinimum(float("-inf"))
            if procdesc["global_max"] is not None:
                widget.setMaximum(procdesc["global_max"]/scale)
            else:
                widget.setMaximum(float("inf"))
            if procdesc["global_step"] is not None:
                widget.setSingleStep(procdesc["global_step"]/scale)
            if procdesc["unit"]:
                widget.setSuffix(" " + procdesc["unit"])
        self.layout = QGridLayout(self)
        start = QDoubleSpinBox(self)
        apply_properties(start)
        start.setValue(state["start"]/scale)
        npoints = QSpinBox(self)
        npoints.setMinimum(1)
        npoints.setMaximum((1 << 31) - 1)
        npoints.setValue(state["npoints"])
        stop = QDoubleSpinBox(self)
        apply_properties(stop)
        stop.setValue(state["stop"]/scale)
        randomize = QCheckBox("Randomize", self)
        randomize.setChecked(state["randomize"])
        #layout
        self.layout.addWidget(QLabel("start:", self), 0, 0)
        self.layout.addWidget(start, 0, 1)
        self.layout.addWidget(QLabel("npoints:", self), 1, 0)
        self.layout.addWidget(npoints, 1, 1)
        self.layout.addWidget(QLabel("stop:", self), 2, 0)
        self.layout.addWidget(stop, 2, 1)
        self.layout.addWidget(randomize, 3, 1)

        def update_start(value):
            """Updates the current start value at _RangeScan argument.
            
            Once the value at start SpinBox changed, this is called.
            """
            state["start"] = value*scale
            if start.value() != value:
                start.setValue(value)

        def update_stop(value):
            """Updates the current stop value at _RangeScan argument.
            
            Once the value at stop SpinBox changed, this is called.
            """
            state["stop"] = value*scale
            if stop.value() != value:
                stop.setValue(value)

        def update_npoints(value):
            """Updates the current npoints number at _RangeScan argument.
            
            Once the number at npoints SpinBox changed, this is called.
            """
            state["npoints"] = value
            if npoints.value() != value:
                npoints.setValue(value)

        def update_randomize():
            """Updates the current randomize boolean value at _RangeScan argument.
            
            Once the checked state of randomize button changed, this is called.
            """
            state["randomize"] = randomize.isChecked()
            randomize.setChecked(state["randomize"])

        start.valueChanged.connect(update_start)
        npoints.valueChanged.connect(update_npoints)
        stop.valueChanged.connect(update_stop)
        randomize.stateChanged.connect(update_randomize)

class _ScanEntry(QWidget):
    """Entry class for a Scannable argument.
    
    Attributes:
        name: The name of the experiment.
        state: The Dictionary that describes arguments of each scan type.
        stack: The stackWidget that contains widget of each scan type.
        widgets: The Dictionary that contains widget of each scan type.
        radioButtons: The Dictionary that contains buttons for selecting specific scan type.
        layout: The layout of _ScanEntry widget.
    """
    def __init__(
        self,
        name: str,
        argInfo: Dict[str, Any],
        parent: Optional[QWidget] = None
        ):
        """Extended.

        Args:
            name: The name of the experiment.
            argInfo: Each key and its value are:
                default: The Dictionary that describes arguments of a specific scanning type.
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
        self.widget = _RangeScan(procdesc, self.state["RangeScan"])
        self.layout = QGridLayout(self)
        self.layout.addWidget(QLabel(name, self), 0, 0)
        self.layout.addWidget(self.widget, 0, 1)

    def get_state(self, argInfo):
        """Gets state dictionary that describes scanning parameter.

        Creates a default state dictionary and reflect the scan argInfo.

        Args:
            argInfo: The dictionary with the argument options.
        """
        scale = argInfo["scale"]
        state = {
            "selected": "RangeScan",
            "RangeScan": {"start": 0.0, "stop": 100.0*scale, "npoints": 10,
                          "randomize": False, "seed": None},
        }
        if "default" in argInfo:
            defaults = argInfo["default"]
            if not isinstance(defaults, list):
                defaults = [defaults]
            state["selected"] = defaults[0]["ty"]
            for default in reversed(defaults):
                ty = default["ty"]
                if ty == "RangeScan":
                    state[ty]["start"] = default["start"]
                    state[ty]["stop"] = default["stop"]
                    state[ty]["npoints"] = default["npoints"]
                    state[ty]["randomize"] = default["randomize"]
                    state[ty]["seed"] = default["seed"]
                else:
                    logger.warning("unknown scannable type: %s", ty)
        return state

    def get_procdesc(self, argInfo):
        """Gets prodesc dictionary that describes global scanning parameter.

        Args:
            argInfo: The dictionary with the argument options.
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

    def get_sequence(self):
        """Gets scanning sequence from _ScanEntry."""
        sequence = None
        if self.state["selected"] == "RangeScan":
            npoints = self.state["RangeScan"]["npoints"]
            start = self.state["RangeScan"]["start"]
            stop = self.state["RangeScan"]["stop"]
            if npoints == 0:
                sequence = []
            if npoints == 1:
                sequence = [self.start]
            else:
                dx = (stop - start)/(npoints - 1)
                sequence = [i*dx + start for i in range(npoints)]
            if self.state["RangeScan"]["randomize"]:
                random.Random(self.state["RangeScan"]["seed"]).shuffle(sequence)
        else:
            logger.warning("unknown scannable type: %s", self.state["selected"] )
        return sequence