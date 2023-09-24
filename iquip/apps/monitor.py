"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

import functools
import logging
from typing import Dict, Optional, Tuple, Union

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QDoubleSpinBox, QGridLayout, QHBoxLayout, QLabel, QPushButton, QSlider, QVBoxLayout, QWidget
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
