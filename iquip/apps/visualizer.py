"""App module for showing the code and sequence viewer."""

import io
import logging
from typing import Callable, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget
from PyQt5.Qsci import QsciScintilla, QsciLexerPython

import qiwis

logger = logging.getLogger(__name__)


class CodeViewerFrame(QWidget):
    """Frame for showing the code.
    
    Attributes:
        editor: The QsciScintilla widget for showing the experiment code.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.editor = QsciScintilla(self)
        lexer = QsciLexerPython(self.editor)
        self.editor.setFolding(True)
        self.editor.setLexer(lexer)
        self.editor.setMarginType(0, QsciScintilla.NumberMargin)
        self.editor.setMarginWidth(0, "000")
        self.editor.setReadOnly(True)
        self.editor.setUtf8(True)
        self.editor.setWrapMode(QsciScintilla.WrapCharacter)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.editor)
        self.setLayout(layout)


# TODO(BECATRUE): This frame will be implemented in #123.
class SequenceViewerFrame(QWidget):
    """Frame for showing the sequence from the vcd file."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        label = QLabel("Sequence Viewer", self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(label)
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

    def __init__(
        self,
        rid: str,
        callback: Callable[[str], None],
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            rid: See the attributes section in _ResultFilesThread.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.rid = rid
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.
        
        Fetches the code file and read it.

        After fininshed, the fetched isgnal is emitted.
        """
        try:
            response = requests.get(f"http://127.0.0.1:8000/result/{self.rid}/code/", timeout=10)
            response.raise_for_status()
            file_contents = response.content
            code = file_contents.decode()
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the code file.")
            return
        self.fetched.emit(code)


class VisualizerApp(qiwis.BaseApp):
    """App for showing the code and sequence viewer.
    
    Attributes:
        rid: The run identifier value of the target executed experiment.
        resultFilesThread: The most recently executed _ResultFilesThread instance.
    """

    def __init__(self, name: str, rid: str, parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            rid: See the attributes section in VisualizerApp.
        """
        super().__init__(name, parent=parent)
        self.rid = rid
        self.resultFilesThread: Optional[_ResultFilesThread] = None
        self.codeViewerFrame = CodeViewerFrame()
        self.sequenceViewerFrame = SequenceViewerFrame()
        self.fetchResultFiles()

    def fetchResultFiles(self):
        """Fetches the code and vcd file."""
        self.resultFilesThread = _ResultFilesThread(self.rid, self._initViewer)
        self.resultFilesThread.start()

    def _initViewer(self, code: str):
        """Initializes the code and sequence viewer.
        
        Args:
            code: The experiment code.
        """
        self.codeViewerFrame.editor.setText(code)

    def frames(self) -> Tuple[CodeViewerFrame, SequenceViewerFrame]:
        """Overridden."""
        return (self.codeViewerFrame, self.sequenceViewerFrame)
