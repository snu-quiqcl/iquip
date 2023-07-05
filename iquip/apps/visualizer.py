"""App module for visualizing the experiment code."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QTreeWidget, QVBoxLayout, QWidget

import qiwis

class CodeViewerFrame(QWidget):
    """Frame for showing the code viewer."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.viewer = QTreeWidget(self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.viewer)


class VisualizerApp(qiwis.BaseApp):
    """App for showing the code and sequence viewers."""

    def __init__(
        self,
        name: str,
        experimentPath: str,
        experimentClsName: str,
        parent: Optional[QObject] = None
    ):
        """Extended."""
        super().__init__(name, parent=parent)
        self.codeViewerFrame = CodeViewerFrame()

    def frames(self) -> Tuple[CodeViewerFrame]:
        """Overridden."""
        return (self.codeViewerFrame,)
