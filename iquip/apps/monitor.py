"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

import logging
from typing import Dict, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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
        self.ttlWidgets = {}
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
        override: The override value to set.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
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

        Since it just sends a POST query, it cannot be guaranteed that
        the override will be applied immediately.
        """
        params = {"value": self.override}
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/ttl/override/",
                params=params
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to set the override of all TTL channels.")
            return


class DeviceMonitorApp(qiwis.BaseApp):
    """App for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC.

    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
    """

    def __init__(self, name: str, ttlInfo: Dict[str, int], parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            ttlInfo: See ttlInfo in TTLControllerFrame.__init__().
        """
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.ttlControllerFrame = TTLControllerFrame(ttlInfo)

    def frames(self) -> Tuple[TTLControllerFrame]:
        """Overridden."""
        return (self.ttlControllerFrame,)
