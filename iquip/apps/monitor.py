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
        levelButton: Button for setting the level.

    Signals:
        levelChanged(level): Current level value is changed to level.
    """

    levelChanged = pyqtSignal(bool)

    def __init__(self, name: str, channel: int, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            name: TTL channel name.
            channel: TTL channel number.
        """
        super().__init__(parent=parent)
        # widgets
        self.levelButton = QPushButton("OFF")
        self.levelButton.setCheckable(True)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(QLabel(name, self))
        infoLayout.addWidget(QLabel(f"CH {channel}", self))
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(self.levelButton)
        # signal connection
        self.levelButton.clicked.connect(self.levelChanged)
        self.levelChanged.connect(self._setLevelButtonText)

    @pyqtSlot(bool)
    def _setLevelButtonText(self, level: bool):
        """Sets the levelButton text.

        Args:
            level: Whether the levelButton is now checked or not.
        """
        if level:
            self.levelButton.setText("ON")
        else:
            self.levelButton.setText("OFF")


class TTLControllerFrame(QWidget):
    """Frame for monitoring and controlling TTL channels.

    Attributes:
        ttlWidgets: Dictionary with TTL controller widgets.
          Each key is a TTL channel name, and its value is the corresponding TTLControllerWidget.
        overrideButton: Button for setting the override.

    Signals:
        overrideChanged(override): Current override value is changed to override.
    """

    overrideChanged = pyqtSignal(bool)

    def __init__(
        self,
        ttlInfo: Dict[str, int],
        numColumns: int = 4,
        parent: Optional[QWidget] = None
    ):
        """Extended.
        
        Args:
            ttlInfo: Dictionary with TTL channels info.
              Each key is a TTL channel name, and its value is the channel number.
            numColumns: Number of columns in TTL widgets container layout.
        """
        super().__init__(parent=parent)
        if numColumns <= 0:
            logger.error("The number of columns must be positive.")
            return
        self.ttlWidgets: Dict[str, TTLControllerWidget] = {}
        # widgets
        ttlWidgetLayout = QGridLayout()
        for idx, (name, channel) in enumerate(ttlInfo.items()):
            ttlWidget = TTLControllerWidget(name, channel, self)
            row, column = idx // numColumns, idx % numColumns
            self.ttlWidgets[name] = ttlWidget
            ttlWidgetLayout.addWidget(ttlWidget, row, column)
        self.overrideButton = QPushButton("Not Overriding", self)
        self.overrideButton.setCheckable(True)
        # layout
        layout = QVBoxLayout(self)
        layout.addLayout(ttlWidgetLayout)
        layout.addWidget(self.overrideButton)
        # signal connection
        self.overrideButton.clicked.connect(self.overrideChanged)
        self.overrideChanged.connect(self._setOverrideButtonText)

    @pyqtSlot(bool)
    def _setOverrideButtonText(self, override: bool):
        """Sets the levelButton text.
        
        Args:
            override: Whether the overrideButton is now checked or not.
        """
        if override:
            self.overrideButton.setText("Overriding")
        else:
            self.overrideButton.setText("Not Overriding")


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
        channel: Target TTL channel number.
        level: Level value to set.
        ip: Proxy server IP address.
        port: Proxy server PORT number.
    """

    def __init__(
        self,
        channel: int,
        level: bool,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            target, level, ip, port: See the attributes section.
        """
        super().__init__(parent=parent)
        self.channel = channel
        self.level = level
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Sets the level of the target TTL channel through the proxy server.

        It cannot be guaranteed that the level will be applied immediately.
        """
        params = {"channel": self.channel, "value": self.level}
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
        ndecimals: int = 2,
        minVoltage: float = -10,
        maxVoltage: float = 10,
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
        self.slider.setRange(minVoltage * self._unit, maxVoltage * self._unit)
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
              About this dictionary, see DACControllerWidget.__init__().
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


class DeviceMonitorApp(qiwis.BaseApp):
    """App for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC.

    Attributes:
        proxy_id: Proxy server IP address.
        proxy_port: Proxy server PORT number.
        ttlControllerFrame: Frame that monitoring and controlling TTL channels.
        ttlOverrideThread: Most recently executed _TTLOverrideThread instance.
        ttlLevelThread: Most recently executed _TTLLevelThread instance.
    """

    def __init__(self, name: str, ttlInfo: Dict[str, int], parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            ttlInfo: See ttlInfo in TTLControllerFrame.__init__().
        """
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.ttlOverrideThread: Optional[_TTLOverrideThread] = None
        self.ttlLevelThread: Optional[_TTLLevelThread] = None
        self.ttlControllerFrame = TTLControllerFrame(ttlInfo)
        # signal connection
        self.ttlControllerFrame.overrideChanged.connect(self._setOverride)
        for name_, channel in ttlInfo.items():
            self.ttlControllerFrame.ttlWidgets[name_].levelChanged.connect(
                functools.partial(self._setLevel, channel)
            )

    @pyqtSlot(bool)
    def _setOverride(self, override: bool):
        """Sets the override of all TTL channels through _TTLOverrideThread.
        
        Args:
            override: See _TTLOverrideThread attributes section.
        """
        self.ttlOverrideThread = _TTLOverrideThread(override, self.proxy_ip, self.proxy_port)
        self.ttlOverrideThread.start()

    @pyqtSlot(int, bool)
    def _setLevel(self, channel: int, level: bool):
        """Sets the level of the target TTL channel through _TTLLevelThread.
        
        Args:
            channel, level: See _TTLLevelThread attributes section.
        """
        self.ttlLevelThread = _TTLLevelThread(channel, level, self.proxy_ip, self.proxy_port)
        self.ttlLevelThread.start()

    def frames(self) -> Tuple[TTLControllerFrame]:
        """Overridden."""
        return (self.ttlControllerFrame,)
