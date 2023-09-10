"""App module for showing the code and sequence viewer."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt5.Qsci import QsciScintilla, QsciLexerPython

import qiwis

class CodeViewerFrame(QWidget):
    """Frame for showing the code."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Code Viewer", self)
        self.editor = QsciScintilla(self)
        self.lexer = QsciLexerPython(self.editor)
        code = """
import numpy as np

print("Hello, my name is Jaehun You.")

for i in range(10):
    if i == 5:
        b = 3
"""
        self.editor.setText(code)
        self.editor.setLexer(self.lexer)
        self.editor.setUtf8(True)
        self.editor.setWrapMode(QsciScintilla.WrapCharacter)
        self.editor.setMarginType(0, QsciScintilla.NumberMargin)
        self.editor.setMarginWidth(0, "000")
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


# TODO(BECATRUE): Obtaining the vcd file will be implemented in #123.
class _ResultFilesThread(QThread):
    """QThread for obtaining the code and vcd file from the proxy server.
    
    Signals:
        fetched(code):
          The code file is fetched.
          The "code" is a string format code.

    Attributes:
        rid: The run identifier value of the target executed experiment.
    """

    fetched = pyqtSignal(str)


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
