"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

from typing import Dict, Optional

from PyQt5.QtWidgets import QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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
        self.levelButton = QPushButton("OFF")
        self.levelButton.setCheckable(True)
        # layout
        infoLayout = QHBoxLayout()
        infoLayout.addWidget(QLabel(name, self))
        infoLayout.addWidget(QLabel(f"CH {channel}", self))
        layout = QVBoxLayout(self)
        layout.addLayout(infoLayout)
        layout.addWidget(self.levelButton)


class TTLControllerFrame(QWidget):
    """Frame for monitoring and controlling TTL channels.
    
    Attributes:
        overrideButton: Button for setting the override.
    """

    def __init__(self, ttlInfo: Dict[str, int], parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.overrideButton = QPushButton("Not Overridden", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.overrideButton)
