"""App module for showing the code and sequence viewer."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt5.Qsci import QsciScintilla

import qiwis

class CodeViewerFrame(QWidget):
    """Frame for showing the code."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Code Viewer", self)
        self.editor = QsciScintilla(self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.editor)
        self.setLayout(layout)


# TODO(BECATRUE): This frame will be implemented in #123.
class SequenceViewerFrame(QWidget):
    """Frame for showing the sequence from the vcd file."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Sequence Viewer", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        self.setLayout(layout)


class VisualizerApp(qiwis.BaseApp):
    """App for showing the code and sequence viewer."""

    def __init__(self, name: str, rid: str, parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            rid: The run identifier value of the target executed experiment.
        """
        super().__init__(name, parent=parent)
        self.codeViewerFrame = CodeViewerFrame()
        self.sequenceViewerFrame = SequenceViewerFrame()

    def frames(self) -> Tuple[CodeViewerFrame, SequenceViewerFrame]:
        """Overridden."""
        return (self.codeViewerFrame, self.sequenceViewerFrame)
