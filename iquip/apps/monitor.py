"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

import functools
import logging
from typing import Dict, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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
        self.button = QPushButton("OFF")
        self.button.setCheckable(True)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(QLabel(name, self))
        infoLayout.addWidget(QLabel(device, self))
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
        self.button = QPushButton("Not Overriding", self)
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
            target, level, ip, port: See the attributes section.
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
