# pylint: disable=too-many-lines
"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

import functools
import json
import logging
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QCheckBox, QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout,
    QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
)
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

import qiwis

logger = logging.getLogger(__name__)

class TTLControllerWidget(QWidget):
    """Single TTL channel controller widget.
    
    Attributes:
        label: Label for showing the output value.
        levelButton: Button for setting the level.
        overrideButton: Button for setting the override.

    Signals:
        outputChanged(output): Current output value is changed.
        levelChanged(level): Current level is changed.
        levelChangeRequested(level): Requested to change the level.
        overrideChanged(override): Current override value is changed.
        overrideChangeRequested(override): Requested to change the override value.
    """

    outputChanged = pyqtSignal(bool)
    levelChanged = pyqtSignal(bool)
    levelChangeRequested = pyqtSignal(bool)
    overrideChanged = pyqtSignal(bool)
    overrideChangeRequested = pyqtSignal(bool)

    def __init__(self, name: str, device: str, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            name: TTL channel name.
            device: TTL device name.
        """
        super().__init__(parent=parent)
        # widgets
        nameLabel = QLabel(name, self)
        nameLabel.setAlignment(Qt.AlignLeft)
        deviceLabel = QLabel(device, self)
        deviceLabel.setAlignment(Qt.AlignRight)
        self.label = QLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setFont(QFont("Arial", 20))
        self.levelButton = QPushButton(self)
        self.levelButton.setEnabled(False)
        self.levelButton.setCheckable(True)
        self.overrideButton = QPushButton(self)
        self.overrideButton.setEnabled(False)
        self.overrideButton.setCheckable(True)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(nameLabel)
        infoLayout.addWidget(deviceLabel)
        buttonLayout = QHBoxLayout()
        buttonLayout.addWidget(self.levelButton)
        buttonLayout.addWidget(self.overrideButton)
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(self.label)
        layout.addLayout(buttonLayout)
        # signal connection
        self.outputChanged.connect(self._setLabelText)
        self.levelChanged.connect(functools.partial(self.levelButton.setEnabled, True))
        self.levelChanged.connect(self._setLevelButtonText)
        self.levelButton.clicked.connect(functools.partial(self.levelButton.setEnabled, False))
        self.levelButton.clicked.connect(self.levelChangeRequested)
        self.overrideChanged.connect(functools.partial(self.overrideButton.setEnabled, True))
        self.overrideChanged.connect(self._setOverrideButtonText)
        self.overrideButton.clicked.connect(
            functools.partial(self.overrideButton.setEnabled, False))
        self.overrideButton.clicked.connect(self.overrideChangeRequested)

    @pyqtSlot(bool)
    def _setLabelText(self, output: bool):
        """Sets the label text.
        
        Args:
            output: Whether the current output value is on or off.
        """
        if output:
            self.label.setText("HIGH")
        else:
            self.label.setText("LOW")

    @pyqtSlot(bool)
    def _setLevelButtonText(self, level: bool):
        """Sets the level button text.

        Args:
            level: Whether the current level is on or off.
        """
        if level:
            self.levelButton.setText("ON")
        else:
            self.levelButton.setText("OFF")
        self.levelButton.setChecked(level)

    @pyqtSlot(bool)
    def _setOverrideButtonText(self, override: bool):
        """Sets the override button text.

        Args:
            override: Whether the current override is on or off.
        """
        if override:
            self.overrideButton.setText("Overriding")
        else:
            self.overrideButton.setText("Not Overriding")
        self.overrideButton.setChecked(override)


class TTLControllerFrame(QWidget):
    """Frame for monitoring and controlling TTL channels.

    Attributes:
        ttlWidgets: Dictionary with TTL controller widgets.
          Each key is a TTL channel name, and its value is the corresponding TTLControllerWidget.
        overrideOnButton: Button for turning on the override of all TTL devices.
        overrideOffButton: Button for turning off the override of all TTL devices.

    Signals:
        overrideChangeRequested(override): Requested to change the override value.
    """

    overrideChangeRequested = pyqtSignal(bool)

    def __init__(self, ttlInfo: Dict[str, str], parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            ttlInfo: Dictionary with TTL channels info.
              One key is "numColumns", and its value is the number of columns with default 4.
              Each of other keys is a TTL channel name, and its value is the device name.
            numColumns: Number of columns in TTL widgets container layout.
        """
        super().__init__(parent=parent)
        numColumns = ttlInfo.pop("numColumns", 4)
        if numColumns <= 0:
            logger.error("The number of columns must be positive.")
            return
        self.ttlWidgets: Dict[str, TTLControllerWidget] = {}
        # widgets
        ttlWidgetLayout = QGridLayout()
        for idx, (name, device) in enumerate(ttlInfo.items()):
            ttlWidget = TTLControllerWidget(name, device, self)
            row, column = idx // numColumns, idx % numColumns
            self.ttlWidgets[name] = ttlWidget
            ttlWidgetLayout.addWidget(ttlWidget, row, column)
        overrideButtonBox = QGroupBox("Override", self)
        self.overrideOnButton = QPushButton("ON", self)
        self.overrideOffButton = QPushButton("OFF", self)
        # layout
        overrideButtonLayout = QHBoxLayout(overrideButtonBox)
        overrideButtonLayout.addWidget(self.overrideOnButton)
        overrideButtonLayout.addWidget(self.overrideOffButton)
        layout = QVBoxLayout(self)
        layout.addLayout(ttlWidgetLayout)
        layout.addWidget(overrideButtonBox)
        # signal connection
        self.overrideOnButton.clicked.connect(lambda: self.overrideChangeRequested.emit(True))
        self.overrideOffButton.clicked.connect(lambda: self.overrideChangeRequested.emit(False))


class _TTLStatusThread(QThread):
    """QThread for fetching the TTL status from the proxy server.
    
    Signals:
        fetched(modifications): The modifications of TTL status is fetched.
          The "modifications" is a dictionary with three keys; "probe", "level", and "override".
          Its value is a dictionary whose key is a TTL name and value is the modified value.

    Attributes:
        url: Web socket url.
        devices: List of TTL names.
    """

    fetched = pyqtSignal(dict)

    def __init__(self, ip: str, port: int, devices: List[str], parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            ip: proxy server IP address.
            port: proxy server PORT number.
            devices: See attribute section.
        """
        super().__init__(parent=parent)
        self.url = f"ws://{ip}:{port}/ttl/status/modification/"
        self.devices = devices

    def run(self):
        """Overridden.
        
        Fetches the modifications of TTL status from the proxy server.

        Whenever fetched, the fetched signal is emitted.
        """
        try:
            with connect(self.url) as websocket:
                websocket.send(json.dumps(self.devices))
                for response in websocket:
                    status = json.loads(response)
                    self.fetched.emit(status)
        except WebSocketException:
            logger.exception("Failed to fetch the modifications of TTL status.")


class _TTLOverrideThread(QThread):
    """QThread for setting the override of the target TTL channels through the proxy server.
    
    Attributes:
        url: POST request url.
        data: POST request body.
    """

    def __init__(
        self,
        devices: List[str],
        overrides: List[bool],
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            devices: List of target TTL device names.
            overrides: List of override values to be set.
            ip: Proxy server IP address.
            port: Proxy server PORT number.
        """
        super().__init__(parent=parent)
        self.url = f"http://{ip}:{port}/ttl/override/"
        self.data = {"devices": devices, "values": overrides}

    def run(self):
        """Overridden.
        
        Sets the override of the target TTL channels through the proxy server.

        It cannot be guaranteed that the overrides will be applied immediately.
        """
        try:
            response = requests.post(self.url, data=json.dumps(self.data), timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the override of the target TTL channels.")


class _TTLLevelThread(QThread):
    """QThread for setting the level of the target TTL channels through the proxy server.
    
    Attributes:
        url: POST request url.
        data: POST request body.
    """

    def __init__(
        self,
        devices: List[str],
        levels: List[bool],
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            devices: List of target TTL device names.
            levels: List of level values to be set.
            ip: Proxy server IP address.
            port: Proxy server PORT number.
        """
        super().__init__(parent=parent)
        self.url = f"http://{ip}:{port}/ttl/level/"
        self.data = {"devices": devices, "values": levels}

    def run(self):
        """Overridden.
        
        Sets the level of the target TTL channels through the proxy server.

        It cannot be guaranteed that the levels will be applied immediately.
        """
        try:
            response = requests.post(self.url, data=json.dumps(self.data), timeout=10)
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the level of the target TTL channels.")


class DACControllerWidget(QWidget):
    """Single DAC channel controller widget.
    
    Attributes:
        slider: Slider for setting the voltage.
        spinbox: Spin box for setting and showing the voltage in slider.
        button: Button for applying the voltage in practice.

    Signals:
        voltageSet(voltage): Current voltage value is set to voltage.
    """

    voltageSet = pyqtSignal(float)

    def __init__(
        self,
        name: str,
        device: str,
        channel: int,
        ndecimals: int = 4,
        minVoltage: float = -10,
        maxVoltage: float = 9.9997,
        parent: Optional[QWidget] = None
    ):  # pylint: disable=too-many-arguments, too-many-locals
        """Extended.
        
        Args:
            name: DAC channel name.
            device: DAC device name.
            channel: DAC channel number.
            ndecimals: Number of decimals that can be set.
            minVoltage, maxVoltage: Min/Maxinum voltage that can be set.
        """
        super().__init__(parent=parent)
        self._unit = 10 ** ndecimals
        # widgets
        nameLabel = QLabel(name, self)
        nameLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        deviceLabel = QLabel(device, self)
        deviceLabel.setAlignment(Qt.AlignCenter)
        channelLabel = QLabel(f"CH {channel}", self)
        channelLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.slider = QSlider(Qt.Horizontal, self)
        self.slider.setRange(int(minVoltage * self._unit), int(maxVoltage * self._unit))
        self.slider.setTickInterval(self._unit)
        self.slider.setTickPosition(QSlider.TicksAbove)
        minVoltageLabel = QLabel(f"Min: {minVoltage}V", self)
        minVoltageLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        maxVoltageLabel = QLabel(f"Max: {maxVoltage}V", self)
        maxVoltageLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.spinbox = QDoubleSpinBox(self)
        self.spinbox.setAlignment(Qt.AlignVCenter)
        self.spinbox.setSuffix("V")
        self.spinbox.setMinimum(minVoltage)
        self.spinbox.setMaximum(maxVoltage)
        self.spinbox.setDecimals(ndecimals)
        self.button = QPushButton("Set")
        self._sliderChanged(self.slider.value())
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(nameLabel)
        infoLayout.addWidget(deviceLabel)
        infoLayout.addWidget(channelLabel)
        sliderInfoLayout = QHBoxLayout()
        sliderInfoLayout.addWidget(minVoltageLabel)
        sliderInfoLayout.addWidget(self.spinbox)
        sliderInfoLayout.addWidget(maxVoltageLabel)
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(self.slider)
        layout.addLayout(sliderInfoLayout)
        layout.addWidget(self.button)
        # signal connection
        self.slider.valueChanged.connect(self._sliderChanged)
        self.spinbox.valueChanged.connect(self._spinboxChanged)
        self.button.clicked.connect(self._buttonClicked)

    @pyqtSlot(int)
    def _sliderChanged(self, value: int):
        """The slider value is changed.
        
        Args:
            value: Current slider value.
        """
        self.spinbox.setValue(value / self._unit)

    @pyqtSlot(float)
    def _spinboxChanged(self, value: float):
        """The spinbox value is changed.
        
        Args:
            value: Current spinbox value.
        """
        self.slider.setValue(int(value * self._unit))

    @pyqtSlot()
    def _buttonClicked(self):
        """The button is clicked."""
        self.voltageSet.emit(self.slider.value() / self._unit)


class DACControllerFrame(QWidget):
    """Frame for monitoring and controlling DAC channels.
    
    Attributes:
        dacWidgets: Dictionary with DAC controller widgets.
          Each key is a DAC channel name, and its value is the corresponding DACControllerWidget.
    """

    def __init__(
        self,
        dacInfo: Dict[str, Dict[str, Union[float, str]]],
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            dacInfo: Dictionary with DAC channels info.
              One key is "numColumns", and its value is the number of columns with default 4.
              Each of other keys is a DAC channel name, and its value is a dictionary with DAC info.
              This dictionary is given as keyword arguments to DACControllerWidget.__init__().
            numColumns: Number of columns in DAC widgets container layout.
        """
        super().__init__(parent=parent)
        numColumns = dacInfo.pop("numColumns", 4)
        if numColumns <= 0:
            logger.error("The number of columns must be positive.")
            return
        self.dacWidgets: Dict[str, DACControllerWidget] = {}
        # widgets
        dacWidgetLayout = QGridLayout()
        for idx, (name, info) in enumerate(dacInfo.items()):
            dacWidget = DACControllerWidget(name, **info)
            row, column = idx // numColumns, idx % numColumns
            self.dacWidgets[name] = dacWidget
            dacWidgetLayout.addWidget(dacWidget, row, column)
        # layout
        layout = QVBoxLayout(self)
        layout.addLayout(dacWidgetLayout)


class _DACVoltageThread(QThread):
    """QThread for setting the voltage of the target DAC channel through the proxy server.
    
    Attributes:
        device: Target DAC device name.
        channel: Target DAC channel number.
        voltage: Voltage value to set.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(
        self,
        device: str,
        channel: int,
        voltage: float,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            device, channel, voltage, ip, port: See the attributes section.
        """
        super().__init__(parent=parent)
        self.device = device
        self.channel = channel
        self.voltage = voltage
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Sets the voltage of the target DAC channel through the proxy server.

        It cannot be guaranteed that the voltage will be applied immediately.
        """
        params = {"device": self.device, "channel": self.channel, "value": self.voltage}
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/dac/voltage/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            rid = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the voltage of the target DAC channel.")
            return
        logger.info(
            "Set the voltage of DAC %s CH %d to %fV. RID: %d",
            self.device, self.channel, self.voltage, rid
        )


def profile_info(
    frequency_info: Optional[Dict[str, Any]] = None,
    amplitude_info: Optional[Dict[str, Any]] = None,
    phase_info: Optional[Dict[str, Any]] = None
) -> Dict[str, Dict[str, Any]]:
    """Returns the profile info.

    It completes the profile info by adding default values.

    Args:
        See DDSControllerWidget.__init__().
        Note that this function may change the argument dictionaries.

    Returns:
        The dictionary with three keys; frequency, amplitude, and phase.
          Its value is the corresponding info dictionary with the following keys:
          ndecimals, min, max, unit, and step.
    """
    # frequency info
    if frequency_info is None:
        frequency_info = {}
    frequency_info.setdefault("ndecimals", 2)
    frequency_info.setdefault("min", 1e6)
    frequency_info.setdefault("max", 4e8)
    unit = frequency_info.setdefault("unit", "Hz")
    if unit not in ["Hz", "kHz", "MHz"]:
        frequency_info["unit"] = "Hz"
        logger.warning("Invalid frequency unit: %s (set to Hz).", unit)
    frequency_info.setdefault("step", 1)
    # amplitude info
    if amplitude_info is None:
        amplitude_info = {}
    amplitude_info.setdefault("ndecimals", 2)
    amplitude_info["min"] = 0
    amplitude_info["max"] = 1
    amplitude_info["unit"] = ""
    amplitude_info.setdefault("step", 0.01)
    # phase info
    if phase_info is None:
        phase_info = {}
    phase_info.setdefault("ndecimals", 2)
    phase_info["min"] = 0
    phase_info["max"] = 1
    phase_info["unit"] = ""
    phase_info.setdefault("step", 0.01)
    return {"frequency": frequency_info, "amplitude": amplitude_info, "phase": phase_info}


class DDSControllerWidget(QWidget):
    """Single DDS channel controller widget.
    
    Attributes:
        profileWidgets: Dictionary with frequency, amplitude, phase spin box,
          and switching check box.
        attenuationSpinbox: Spin box for setting the attenuation.
        switchButton: Button for turning on and off the TTL switch that controls the output of DDS.

    Signals:
        profileSet(frequency, amplitude, phase, switching):
          The default profile setting is set to frequency in Hz, amplitude, and phase.
          If switching is True, the current DDS profile is set to the default profile.
        attenuationSet(attenuation): Current attenuation setting is set to attenuation.
        switchClicked(on): If on is True, the switchButton is currently checked.
    """

    profileSet = pyqtSignal(float, float, float, bool)
    attenuationSet = pyqtSignal(float)
    switchClicked = pyqtSignal(bool)

    def __init__(
        self,
        name: str,
        device: str,
        channel: int,
        frequencyInfo: Optional[Dict[str, Any]] = None,
        amplitudeInfo: Optional[Dict[str, Any]] = None,
        phaseInfo: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None
    ):  # pylint: disable=too-many-arguments, too-many-locals
        """Extended.
        
        Args:
            name: DDS channel name.
            device: DDS device name.
            channel: DDS channel number.
            frequencyInfo: Dictionary with frequency info. Each key and its value are:
              ndecimals: Number of decimals that can be set. (default=2)
              min, max: Min/Maximum frequency that can be set. (default=1e6, 4e8)
              step: Step increased/decreased through spinbox arrows. (default=1)
              unit: Unit of frequency. It should be one of "Hz", "kHz", and "MHz". (default="Hz")
            amplitudeInfo: Dictionary with amplitude info. Each key and its value are:
              ndecimals: Number of decimals that can be set. (default=2)
              step: Step increased/decreased through spinbox arrows. (default=0.01)
            phaseInfo: Dictionary with phase info. Each key and its value are:
              ndecimals: Number of decimals that can be set. (default=2)
              step: Step increased/decreased through spinbox arrows. (default=0.01)
        """
        super().__init__(parent=parent)
        profileInfo = profile_info(frequencyInfo, amplitudeInfo, phaseInfo)
        # info widgets
        nameLabel = QLabel(name, self)
        nameLabel.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        deviceLabel = QLabel(device, self)
        deviceLabel.setAlignment(Qt.AlignCenter)
        channelLabel = QLabel(f"CH {channel}", self)
        channelLabel.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # profile widgets
        self.profileWidgets: Dict[str, Union[QDoubleSpinBox, QCheckBox]] = {}
        profileGroupbox = QGroupBox("Profile", self)
        profileLayout = QVBoxLayout(profileGroupbox)
        profileInfoLayout = QHBoxLayout()
        for name_ in ("frequency", "amplitude", "phase"):
            info = profileInfo[name_]
            spinbox = self.spinBoxWithInfo(info)
            self.profileWidgets[name_] = spinbox
            profileInfoLayout.addWidget(QLabel(f"{name_}:", self), alignment=Qt.AlignRight)
            profileInfoLayout.addWidget(spinbox)
        profileSetLayout = QHBoxLayout()
        switchingCheckbox = QCheckBox("Switch to this profile", self)
        switchingCheckbox.setChecked(True)
        self.profileWidgets["switching"] = switchingCheckbox
        profileSetLayout.addWidget(switchingCheckbox)
        profileButton = QPushButton("Set", self)
        profileSetLayout.addWidget(profileButton, alignment=Qt.AlignRight)
        profileLayout.addLayout(profileInfoLayout)
        profileLayout.addLayout(profileSetLayout)
        # attenuation widgets
        attenuationBox = QGroupBox("Attenuation", self)
        attenuationLayout = QHBoxLayout(attenuationBox)
        attenuationInfo = {"ndecimals": 1, "min": 0, "max": 31.5, "step": 0.5, "unit": "dB"}
        self.attenuationSpinbox = self.spinBoxWithInfo(attenuationInfo)
        self.attenuationSpinbox.setPrefix("-")
        attenuationButton = QPushButton("Set", self)
        attenuationLayout.addWidget(QLabel("attenuation:", self), alignment=Qt.AlignRight)
        attenuationLayout.addWidget(self.attenuationSpinbox)
        attenuationLayout.addWidget(attenuationButton, alignment=Qt.AlignRight)
        # switch button
        self.switchButton = QPushButton("OFF?", self)
        self.switchButton.setCheckable(True)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(nameLabel)
        infoLayout.addWidget(deviceLabel)
        infoLayout.addWidget(channelLabel)
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(profileGroupbox)
        layout.addWidget(attenuationBox)
        layout.addWidget(self.switchButton)
        # signal connection
        profileButton.clicked.connect(self._profileButtonClicked)
        attenuationButton.clicked.connect(self._attenuationButtonClicked)
        self.switchButton.clicked.connect(self._setSwitchButtonText)

    def spinBoxWithInfo(self, info: Mapping[str, Any]) -> QDoubleSpinBox:
        """Returns a spinbox with the given info.
        
        Args:
            See *Info arguments in self.__init__().
        """
        spinbox = QDoubleSpinBox(self)
        spinbox.setSuffix(info["unit"])
        spinbox.setMinimum(info["min"])
        spinbox.setMaximum(info["max"])
        spinbox.setDecimals(info["ndecimals"])
        spinbox.setSingleStep(info["step"])
        return spinbox

    @pyqtSlot()
    def _profileButtonClicked(self):
        """The profileButton is clicked.
        
        The profileSet signal is emitted with the current frequency, amplitude, phase,
        and switching.
        """
        frequencySpinbox = self.profileWidgets["frequency"]
        unit = {
            "Hz": 1,
            "kHz": 1e3,
            "MHz": 1e6
        }[frequencySpinbox.suffix()]
        frequency = frequencySpinbox.value() * unit
        amplitude = self.profileWidgets["amplitude"].value()
        phase = self.profileWidgets["phase"].value()
        switching = self.profileWidgets["switching"].isChecked()
        self.profileSet.emit(frequency, amplitude, phase, switching)

    @pyqtSlot()
    def _attenuationButtonClicked(self):
        """The attenuationButton is clicked.
        
        The attenuationSet signal is emitted with the current attenuation.
        """
        attenuation = self.attenuationSpinbox.value()
        self.attenuationSet.emit(attenuation)

    @pyqtSlot(bool)
    def _setSwitchButtonText(self, on: bool):
        """Sets the switchButton text.

        Args:
            on: Whether the switchButton is now checked or not.
        """
        if on:
            self.switchButton.setText("ON")
        else:
            self.switchButton.setText("OFF")
        self.switchClicked.emit(on)


class DDSControllerFrame(QWidget):
    """Frame for monitoring and controlling DDS channels.
    
    Attributes:
        ddsWidgets: Dictionary with DDS controller widgets.
          Each key is a DDS channel name, and its value is the corresponding DDSControllerWidget.
    """

    def __init__(
        self,
        ddsInfo: Dict[str, Dict[str, Any]],
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            ddsInfo: Dictionary with DDS channels info.
              One key is "numColumns", and its value is the number of columns with default 4.
              Each of other keys is a DDS channel name, and its value is a dictionary with DDS info.
              This dictionary is given as keyword arguments to DDSControllerWidget.__init__().
            numColumns: Number of columns in DDS widgets container layout.
        """
        super().__init__(parent=parent)
        numColumns = ddsInfo.pop("numColumns", 4)
        if numColumns <= 0:
            logger.error("The number of columns must be positive.")
            return
        self.ddsWidgets: Dict[str, DDSControllerWidget] = {}
        # widgets
        ddsWidgetLayout = QGridLayout()
        for idx, (name, info) in enumerate(ddsInfo.items()):
            ddsWidget = DDSControllerWidget(name, **info)
            row, column = idx // numColumns, idx % numColumns
            self.ddsWidgets[name] = ddsWidget
            ddsWidgetLayout.addWidget(ddsWidget, row, column)
        # layout
        layout = QVBoxLayout(self)
        layout.addLayout(ddsWidgetLayout)


class _DDSProfileThread(QThread):  # pylint: disable=too-many-instance-attributes
    """QThread for setting the default profile of the target DDS channel.
    
    Attributes:
        device: Target DDS device name.
        channel: Target DDS channel number.
        frequency, amplitude, phase, switching: See DDSControllerWidget.profileSet signal.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(
        self,
        device: str,
        channel: int,
        frequency: float,
        amplitude: float,
        phase: float,
        switching: bool,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.device = device
        self.channel = channel
        self.frequency = frequency
        self.amplitude = amplitude
        self.phase = phase
        self.switching = switching
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Sets the default profile of the target DDS channel.

        It cannot be guaranteed that the profile will be applied immediately.
        """
        params = {
            "device": self.device,
            "channel": self.channel,
            "frequency": self.frequency,
            "amplitude": self.amplitude,
            "phase": self.phase,
            "switching": self.switching
        }
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/dds/profile/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            rid = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the default profile of the target DDS channel.")
            return
        logger.info(
            "Set the default profile of DDS %s CH %d to %fHz, amplitude %f, and phase %f. RID: %d",
            self.device, self.channel, self.frequency, self.amplitude, self.phase, rid
        )
        if self.switching:
            logger.info("The current profile will be switched to the default profile.")


class _DDSAttenuationThread(QThread):
    """QThread for setting the attenuation of the target DDS channel.
    
    Attributes:
        device: Target DDS device name.
        channel: Target DDS channel number.
        attenuation: See DDSControllerWidget.attenuationSet signal.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(
        self,
        device: str,
        channel: int,
        attenuation: float,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.device = device
        self.channel = channel
        self.attenuation = attenuation
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Sets the attenuation of the target DDS channel.

        It cannot be guaranteed that the attenuation will be applied immediately.
        """
        params = {
            "device": self.device,
            "channel": self.channel,
            "value": self.attenuation
        }
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/dds/att/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            rid = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the attenuation of the target DDS channel.")
            return
        logger.info(
            "Set the attenuation of DDS %s CH %d to -%fdB. RID: %d",
            self.device, self.channel, self.attenuation, rid
        )


class _DDSSwitchThread(QThread):
    """QThread for turning on or off the TTL switch, which controls the target DDS channel output.
    
    Attributes:
        device: Target DDS device name.
        channel: Target DDS channel number.
        on: See DDSControllerWidget.switchClicked signal.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(
        self,
        device: str,
        channel: int,
        on: bool,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.device = device
        self.channel = channel
        self.on = on
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Turns on or off the TTL switch, which controls the target DDS channel output.

        It cannot be guaranteed that the switch will be turned on or off immediately.
        """
        params = {
            "device": self.device,
            "channel": self.channel,
            "on": self.on
        }
        on_str = "on" if self.on else "off"
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/dds/switch/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
            rid = response.json()
        except requests.exceptions.RequestException:
            logger.exception("Failed to turn %s the TTL switch of the target DDS channel.", on_str)
            return
        logger.info(
            "Turn %s the TTL switch of DDS %s CH %d. RID: %d",
            on_str, self.device, self.channel, rid
        )


class DeviceMonitorApp(qiwis.BaseApp):  # pylint: disable=too-many-instance-attributes
    """App for monitoring and controlling ARTIQ hardwares e.g., TTL, DAC, and DDS.

    Attributes:
        ttlToName: Dictionary with TTL device name and its channel name.
        proxy_id: Proxy server IP address.
        proxy_port: Proxy server PORT number.
        ttlControllerFrame: Frame that monitoring and controlling TTL channels.
        dacControllerFrame: Frame that monitoring and controlling DAC channels.
        ddsControllerFrame: Frame that monitoring and controlling DDS channels.
        ttlStatusThread: Most recently executed _TTLStatusThread instance.
        ttlOverrideThread: Most recently executed _TTLOverrideThread instance.
        ttlLevelThread: Most recently executed _TTLLevelThread instance.
        dacVoltageThread: Most recently executed _DACVoltageThread instance.
        ddsProfileThread: Most recently executed _DDSProfileThread instance.
        ddsAttenuationThread: Most recently executed _DDSAttenuationThread instance.
        ddsSwitchThread: Most recently executed _DDSSwitchThread instance.
    """

    def __init__(
        self,
        name: str,
        ttlInfo: Dict[str, int],
        dacInfo: Dict[str, Dict[str, Union[float, str]]],
        ddsInfo: Dict[str, Dict[str, Any]],
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            ttlInfo: See ttlInfo in TTLControllerFrame.__init__().
            dacInfo: See dacInfo in DACControllerFrame.__init__().
            ddsInfo: See ddsInfo in DDSControllerFrame.__init__().
        """
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.ttlStatusThread: _TTLStatusThread
        self.ttlOverrideThread: _TTLOverrideThread
        self.ttlLevelThread: _TTLLevelThread
        self.dacVoltageThread: _DACVoltageThread
        self.ddsProfileThread: _DDSProfileThread
        self.ddsAttenuationThread: _DDSAttenuationThread
        self.ddsSwitchThread: _DDSSwitchThread
        self.ttlControllerFrame = TTLControllerFrame(ttlInfo)
        self.dacControllerFrame = DACControllerFrame(dacInfo)
        self.ddsControllerFrame = DDSControllerFrame(ddsInfo)
        self.ttlToName = {v: k for k, v in ttlInfo.items() if k != "numColumns"}
        # signal connection
        self.ttlControllerFrame.overrideChangeRequested.connect(
            functools.partial(self._setTTLOverride, list(self.ttlToName))
        )
        for name_, device in ttlInfo.items():
            self.ttlControllerFrame.ttlWidgets[name_].levelChangeRequested.connect(
                functools.partial(self._setTTLLevel, [device])
            )
            self.ttlControllerFrame.ttlWidgets[name_].overrideChangeRequested.connect(
                functools.partial(self._setTTLOverride, [device])
            )
        for name_, info in dacInfo.items():
            device, channel = map(info.get, ("device", "channel"))
            self.dacControllerFrame.dacWidgets[name_].voltageSet.connect(
                functools.partial(self._setDACVoltage, device, channel)
            )
        for name_, info in ddsInfo.items():
            device, channel = map(info.get, ("device", "channel"))
            widget = self.ddsControllerFrame.ddsWidgets[name_]
            widget.profileSet.connect(functools.partial(self._setDDSProfile, device, channel))
            widget.attenuationSet.connect(
                functools.partial(self._setDDSAttenuation, device, channel)
            )
            widget.switchClicked.connect(functools.partial(self._setDDSSwitch, device, channel))
        self._startTTLStatusThread()

    @pyqtSlot(list, list)
    def _setTTLOverride(self, devices: List[str], overrides: List[bool]):
        """Sets the override of the target TTL channels through _TTLLevelThread.
        
        Args:
            See _TTLOverrideThread arguments section.
        """
        self.ttlOverrideThread = _TTLOverrideThread(devices, overrides,
                                                    self.proxy_ip, self.proxy_port)
        self.ttlOverrideThread.finished.connect(self.ttlOverrideThread.deleteLater)
        self.ttlOverrideThread.start()

    @pyqtSlot(list, list)
    def _setTTLLevel(self, devices: List[str], levels: List[bool]):
        """Sets the level of the target TTL channels through _TTLLevelThread.
        
        Args:
            See _TTLLevelThread arguments section.
        """
        self.ttlLevelThread = _TTLLevelThread(devices, levels, self.proxy_ip, self.proxy_port)
        self.ttlLevelThread.finished.connect(self.ttlLevelThread.deleteLater)
        self.ttlLevelThread.start()

    @pyqtSlot(str, int, float)
    def _setDACVoltage(self, device: str, channel: int, voltage: float):
        """Sets the voltage of the target DAC channel through _DACVoltageThread.
        
        Args:
            See _DACVoltageThread attributes section.
        """
        self.dacVoltageThread = _DACVoltageThread(
            device, channel, voltage, self.proxy_ip, self.proxy_port
        )
        self.dacVoltageThread.finished.connect(self.dacVoltageThread.deleteLater)
        self.dacVoltageThread.start()

    @pyqtSlot(str, int, float, float, float, bool)
    def _setDDSProfile(
        self,
        device: str,
        channel: int,
        frequency: float,
        amplitude: float,
        phase: float,
        switching: bool
    ):  # pylint: disable=too-many-arguments
        """Sets the default profile of the target DDS channel through _DDSProfileThread.
        
        Args:
            See _DDSProfileThread attributes section.
        """
        self.ddsProfileThread = _DDSProfileThread(
            device, channel, frequency, amplitude, phase, switching, self.proxy_ip, self.proxy_port
        )
        self.ddsProfileThread.finished.connect(self.ddsProfileThread.deleteLater)
        self.ddsProfileThread.start()

    @pyqtSlot(str, int, float)
    def _setDDSAttenuation(self, device: str, channel: int, attenuation: float):
        """Sets the attenuation of the target DDS channel through _DDSAttenuationThread.
        
        Args:
            See _DDSAttenuationThread attributes section.
        """
        self.ddsAttenuationThread = _DDSAttenuationThread(
            device, channel, attenuation, self.proxy_ip, self.proxy_port
        )
        self.ddsAttenuationThread.finished.connect(self.ddsAttenuationThread.deleteLater)
        self.ddsAttenuationThread.start()

    @pyqtSlot(str, int, bool)
    def _setDDSSwitch(self, device: str, channel: int, on: bool):
        """Turns on or off the TTL switch, which controls the target DDS channel output
        through _DDSSwitchThread.
        
        Args:
            See _DDSSwitchThread attributes section.
        """
        self.ddsSwitchThread = _DDSSwitchThread(
            device, channel, on, self.proxy_ip, self.proxy_port
        )
        self.ddsSwitchThread.finished.connect(self.ddsSwitchThread.deleteLater)
        self.ddsSwitchThread.start()

    @pyqtSlot(dict)
    def _updateTTLStatus(self, modifications: Dict[str, Dict[str, bool]]):
        """Updates the TTL status.
        
        Args:
            See _TTLStatusThread signals section.
        """
        for device, output in modifications["probe"].items():
            name = self.ttlToName[device]
            self.ttlControllerFrame.ttlWidgets[name].outputChanged.emit(output)
        for device, level in modifications["level"].items():
            name = self.ttlToName[device]
            self.ttlControllerFrame.ttlWidgets[name].levelChanged.emit(level)
        for device, override in modifications["override"].items():
            name = self.ttlToName[device]
            self.ttlControllerFrame.ttlWidgets[name].overrideChanged.emit(override)

    def _startTTLStatusThread(self):
        """Creates and starts a new _TTLStatusThread instance."""
        devices = list(self.ttlToName)
        self.ttlStatusThread = _TTLStatusThread(self.proxy_ip, self.proxy_port, devices)
        self.ttlStatusThread.fetched.connect(self._updateTTLStatus)
        self.ttlStatusThread.finished.connect(self.ttlStatusThread.deleteLater)
        self.ttlStatusThread.start()

    def frames(
        self
    ) -> Tuple[Tuple[str, Union[TTLControllerFrame, DACControllerFrame, DDSControllerFrame]], ...]:
        """Overridden."""
        return (("ttl", self.ttlControllerFrame),
                ("dac", self.dacControllerFrame),
                ("dds", self.ddsControllerFrame))
