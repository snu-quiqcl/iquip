"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

from typing import Optional

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from iquip.monitor import Monitor, TTLMonitorWidget

class TTLControllerWidget(QWidget):
    """Single TTL channel controller widget.
    
    Attributes:
        levelButton: Button for setting the level.
    """

    def __init__(self, name: str, channel: int, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            name: TTL channel name.
            channel: TTL channel number.
        """
        super().__init__(parent=parent)
        # widgets
        monitor = Monitor(initial_value=None)
        monitorWidget = TTLMonitorWidget(monitor, self)
        self.levelButton = QPushButton("OFF")
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(QLabel(name, self))
        infoLayout.addWidget(QLabel(f"CH {channel}", self))
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(monitorWidget)
        layout.addWidget(self.levelButton)
