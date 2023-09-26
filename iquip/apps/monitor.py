"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

import functools
import logging
from typing import Any, Dict, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QDoubleSpinBox, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QPushButton, QSlider, QVBoxLayout, QWidget
)

import qiwis

logger = logging.getLogger(__name__)


class TTLControllerWidget(QWidget):
    """Single TTL channel controller widget.
    
    Attributes:
        button: Button for setting the level.

    Signals:
        levelChanged(level): Current level value is changed to level.
    """

    levelChanged = pyqtSignal(bool)

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
        self.button = QPushButton("OFF?")
        self.button.setCheckable(True)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(nameLabel)
        infoLayout.addWidget(deviceLabel)
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(self.button)
        # signal connection
        self.button.clicked.connect(self.levelChanged)
        self.levelChanged.connect(self._setButtonText)

    @pyqtSlot(bool)
    def _setButtonText(self, level: bool):
        """Sets the button text.

        Args:
            level: Whether the button is now checked or not.
        """
        if level:
            self.button.setText("ON")
        else:
            self.button.setText("OFF")


class TTLControllerFrame(QWidget):
    """Frame for monitoring and controlling TTL channels.

    Attributes:
        ttlWidgets: Dictionary with TTL controller widgets.
          Each key is a TTL channel name, and its value is the corresponding TTLControllerWidget.
        button: Button for setting the override.

    Signals:
        overrideChanged(override): Current override value is changed to override.
    """

    overrideChanged = pyqtSignal(bool)

    def __init__(
        self,
        ttlInfo: Dict[str, str],
        numColumns: int = 4,
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            ttlInfo: Dictionary with TTL channels info.
              Each key is a TTL channel name, and its value is the device name.
            numColumns: Number of columns in TTL widgets container layout.
        """
        super().__init__(parent=parent)
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
        self.button = QPushButton("Not Overriding?", self)
        self.button.setCheckable(True)
        # layout
        layout = QVBoxLayout(self)
        layout.addLayout(ttlWidgetLayout)
        layout.addWidget(self.button)
        # signal connection
        self.button.clicked.connect(self.overrideChanged)
        self.overrideChanged.connect(self._setButtonText)

    @pyqtSlot(bool)
    def _setButtonText(self, override: bool):
        """Sets the button text.
        
        Args:
            override: Whether the button is now checked or not.
        """
        if override:
            self.button.setText("Overriding")
        else:
            self.button.setText("Not Overriding")


class _TTLOverrideThread(QThread):
    """QThread for setting the override of all TTL channels through the proxy server.
    
    Attributes:
        override: Override value to set.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(self, override: bool, ip: str, port: int, parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            override, ip, port: See the attributes section.
        """
        super().__init__(parent=parent)
        self.override = override
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Sets the override of all TTL channels through the proxy server.

        It cannot be guaranteed that the override will be applied immediately.
        """
        params = {"value": self.override}
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/ttl/override/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the override of all TTL channels.")


class _TTLLevelThread(QThread):
    """QThread for setting the level of the target TTL channel through the proxy server.
    
    Attributes:
        device: Target TTL device name.
        level: Level value to set.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(
        self,
        device: str,
        level: bool,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            channel, level, ip, port: See the attributes section.
        """
        super().__init__(parent=parent)
        self.device = device
        self.level = level
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Sets the level of the target TTL channel through the proxy server.

        It cannot be guaranteed that the level will be applied immediately.
        """
        params = {"device": self.device, "value": self.level}
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/ttl/level/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the level of the target TTL channel.")


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
        numColumns: int = 4,
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            dacInfo: Dictionary with DAC channels info.
              Each key is a DAC channel name, and its value is a dictionary with DAC info.
              This dictionary is given as keyword arguments to DACControllerWidget.__init__().
            numColumns: Number of columns in DAC widgets container layout.
        """
        super().__init__(parent=parent)
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

    Returns:
        The dictionary with three keys; frequency, amplitude, and phase.
          Its value is the corresponding info dictionary with the following keys:
          ndecimals, min, max, unit, and step.
    """
    # frequency info
    if frequency_info is None:
        frequency_info = {}
    frequency_info["ndecimals"] = frequency_info.get("ndecimals", 2)
    frequency_info["min"] = frequency_info.get("min", 0)
    frequency_info["max"] = frequency_info.get("max", 4e8)
    unit = frequency_info.get("unit", "Hz")
    if unit not in ["Hz", "kHz", "MHz"]:
        logger.warning("The unit of frequency, %s is invalid.", unit)
        unit = "Hz"
    frequency_info["unit"] = unit
    frequency_info["step"] = frequency_info.get("step", 1)
    # amplitude info
    if amplitude_info is None:
        amplitude_info = {}
    amplitude_info["ndecimals"] = amplitude_info.get("ndecimals", 2)
    amplitude_info["min"] = 0
    amplitude_info["max"] = 1
    amplitude_info["unit"] = ""
    amplitude_info["step"] = amplitude_info.get("step", 0.01)
    # phase info
    if phase_info is None:
        phase_info = {}
    phase_info["ndecimals"] = phase_info.get("ndecimals", 2)
    phase_info["min"] = 0
    phase_info["max"] = 1
    phase_info["unit"] = ""
    phase_info["step"] = phase_info.get("step", 0.01)
    return {"frequency": frequency_info, "amplitude": amplitude_info, "phase": phase_info}


class DDSControllerWidget(QWidget):
    """Single DDS channel controller widget."""

    def __init__(
        self,
        name: str,
        device: str,
        channel: int,
        frequencyInfo: Optional[Dict[str, Any]] = None,
        amplitudeInfo: Optional[Dict[str, Any]] = None,
        phaseInfo: Optional[Dict[str, Any]] = None,
        parent: Optional[QWidget] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            name: DDS channel name.
            device: DDS device name.
            channel: DDS channel number.
            frequencyInfo: Dictionary with frequency info. Each key and its value are:
              ndecimals: Number of decimals that can be set. (default=2)
              min, max: Min/Maximum frequency that can be set. (default=0, 4e8)
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
        profileBox = QGroupBox("Profile", self)
        profileLayout = QHBoxLayout(profileBox)
        for name_ in ("frequency", "amplitude", "phase"):
            info = profileInfo[name_]
            spinbox = self.spinBoxWithInfo(info)
            profileLayout.addWidget(QLabel(f"{name_}:", self), alignment=Qt.AlignRight)
            profileLayout.addWidget(spinbox)
        profileButton = QPushButton("Set")
        profileLayout.addWidget(profileButton, alignment=Qt.AlignRight)
        # attenuator widgets
        attenuatorBox = QGroupBox("Attenuator", self)
        attenuatorLayout = QHBoxLayout(attenuatorBox)
        attenuatorInfo = {"ndecimals": 1, "min": 0, "max": 31.5, "step": 0.5, "unit": "dB"}
        attenuatorSpinbox = self.spinBoxWithInfo(attenuatorInfo)
        attenuatorSpinbox.setPrefix("-")
        attenuatorButton = QPushButton("Set")
        attenuatorLayout.addWidget(QLabel("attenuator:", self), alignment=Qt.AlignRight)
        attenuatorLayout.addWidget(attenuatorSpinbox)
        attenuatorLayout.addWidget(attenuatorButton, alignment=Qt.AlignRight)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(nameLabel)
        infoLayout.addWidget(deviceLabel)
        infoLayout.addWidget(channelLabel)
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(profileBox)
        layout.addWidget(attenuatorBox)

    def spinBoxWithInfo(self, info: Optional[Dict[str, Any]]) -> QDoubleSpinBox:
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


class DeviceMonitorApp(qiwis.BaseApp):
    """App for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC.

    Attributes:
        proxy_id: Proxy server IP address.
        proxy_port: Proxy server PORT number.
        ttlControllerFrame: Frame that monitoring and controlling TTL channels.
        dacControllerFrame: Frame that monitoring and controlling DAC channels.
        ttlOverrideThread: Most recently executed _TTLOverrideThread instance.
        ttlLevelThread: Most recently executed _TTLLevelThread instance.
        dacVoltageThread: Most recently executed _DACVoltageThread instance.
    """

    def __init__(
        self,
        name: str,
        ttlInfo: Dict[str, int],
        dacInfo: Dict[str, Dict[str, Union[float, str]]],
        parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            ttlInfo: See ttlInfo in TTLControllerFrame.__init__().
            dacInfo: See dacInfo in DACControllerFrame.__init__().
        """
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.ttlOverrideThread: Optional[_TTLOverrideThread] = None
        self.ttlLevelThread: Optional[_TTLLevelThread] = None
        self.dacVoltageThread: Optional[_DACVoltageThread] = None
        self.ttlControllerFrame = TTLControllerFrame(ttlInfo)
        self.dacControllerFrame = DACControllerFrame(dacInfo)
        # signal connection
        self.ttlControllerFrame.overrideChanged.connect(self._setTTLOverride)
        for name_, device in ttlInfo.items():
            self.ttlControllerFrame.ttlWidgets[name_].levelChanged.connect(
                functools.partial(self._setTTLLevel, device)
            )
        for name_, info in dacInfo.items():
            device, channel = map(info.get, ("device", "channel"))
            self.dacControllerFrame.dacWidgets[name_].voltageSet.connect(
                functools.partial(self._setDACVoltage, device, channel)
            )

    @pyqtSlot(bool)
    def _setTTLOverride(self, override: bool):
        """Sets the override of all TTL channels through _TTLOverrideThread.
        
        Args:
            override: See _TTLOverrideThread attributes section.
        """
        self.ttlOverrideThread = _TTLOverrideThread(override, self.proxy_ip, self.proxy_port)
        self.ttlOverrideThread.start()

    @pyqtSlot(str, bool)
    def _setTTLLevel(self, device: str, level: bool):
        """Sets the level of the target TTL channel through _TTLLevelThread.
        
        Args:
            device, level: See _TTLLevelThread attributes section.
        """
        self.ttlLevelThread = _TTLLevelThread(device, level, self.proxy_ip, self.proxy_port)
        self.ttlLevelThread.start()

    @pyqtSlot(str, int, float)
    def _setDACVoltage(self, device: str, channel: int, voltage: float):
        """Sets the voltage of the target DAC channel through _DACVoltageThread.
        
        Args:
            device, channel, voltage: See _DACVoltageThread attributes section.
        """
        self.dacVoltageThread = _DACVoltageThread(
            device, channel, voltage, self.proxy_ip, self.proxy_port
        )
        self.dacVoltageThread.start()

    def frames(self) -> Tuple[TTLControllerFrame, DACControllerFrame]:
        """Overridden."""
        return (self.ttlControllerFrame, self.dacControllerFrame)
