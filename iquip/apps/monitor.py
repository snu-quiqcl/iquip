"""App module for monitoring and controlling ARTIQ hardwares e.g., TTL, DDS, and DAC."""

from typing import Dict, Optional

from PyQt5.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

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

    Constants:
        NUM_COLUMNS: Column number of TTL widgets container layout.
    
    Attributes:
        ttlWidgets: Dictionary with TTL controller widgets.
          Each key is a TTL channel name, and its value is the corresponding TTLControllerWidget.
        overrideButton: Button for setting the override.
    """

    NUM_COLUMNS = 4

    def __init__(self, ttlInfo: Dict[str, int], parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            ttlInfo: Dictionary with TTL channels info.
              Each key is a TTL channel name, and its value is the channel number.
        """
        super().__init__(parent=parent)
        self.ttlWidgets = {}
        # widgets
        ttlWidgetLayout = QGridLayout()
        for idx, (name, channel) in enumerate(ttlInfo.items()):
            ttlWidget = TTLControllerWidget(name, channel, self)
            row = idx // TTLControllerFrame.NUM_COLUMNS
            column = idx % TTLControllerFrame.NUM_COLUMNS
            self.ttlWidgets[name] = ttlWidget
            ttlWidgetLayout.addWidget(ttlWidget, row, column)
        self.overrideButton = QPushButton("Not Overridden", self)
        self.overrideButton.setCheckable(True)
        # layout
        layout = QVBoxLayout(self)
        layout.addLayout(ttlWidgetLayout)
        layout.addWidget(self.overrideButton)
