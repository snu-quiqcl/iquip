"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

from typing import Optional

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

class TTLControllerWidget(QWidget):
    """Single TTL channel controller widget."""

    def __init__(self, name: str, channel: int, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            name: TTL channel name.
            channel: TTL channel number.
        """
        super().__init__(parent=parent)
        # widgets
        nameLabel = QLabel(name, self)
        channelLabel = QLabel(f"CH {channel}", self)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(nameLabel)
        infoLayout.addWidget(channelLabel)
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
