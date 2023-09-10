"""App module for showing the code and sequence viewer."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget

import qiwis

class CodeViewerFrame(QWidget):
    """Frame for showing the code."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Code Viewer", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)


class VisualizerApp(qiwis.BaseApp):
    """App for showing the code and sequence viewer."""

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.codeViewerFrame = CodeViewerFrame()

    def frames(self) -> Tuple[CodeViewerFrame]:
        """Overridden."""
        return (self.codeViewerFrame,)
