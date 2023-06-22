"""App module for editting the build arguments and submitting the experiment."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import (
    QPushButton, QVBoxLayout, QWidget
)

import qiwis

class BuilderFrame(QWidget):
    """Frame for showing the build arguments and requesting to submit it."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.submitButton = QPushButton("Submit", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.submitButton)


class BuilderApp(qiwis.BaseApp):
    """App for editting the build arguments and submitting the experiment.
    
    Attributes:
        builderFrame: The frame that shows the build arguments and requests to submit it.
    """

    def __init__(self, name: str, experimentPath: str, parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            experimentPath: The path of the experiment file.
        """
        super().__init__(name, parent=parent)
        self.builderFrame = BuilderFrame()

    def frames(self) -> Tuple[BuilderFrame]:
        """Overridden."""
        return (self.builderFrame,)
