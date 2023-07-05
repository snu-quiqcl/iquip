"""App module for visualizing the experiment code."""

import ast
from typing import Callable, List, Optional, Tuple

import requests
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

import qiwis

class CodeViewerFrame(QWidget):
    """Frame for showing the code viewer."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.viewerTree = QTreeWidget(self)
        self.viewerTree.setColumnCount(2)
        self.viewerTree.setHeaderLabels(["line", "code"])
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.viewerTree)


class _ExperimentCodeThread(QThread):
    """QThread for obtaining the experiment code from the proxy server.
    
    Signals:
        fetched(str): The experiment code is fetched.

    Attributes:
        experimentPath: The path of the experiment file.
    """

    fetched = pyqtSignal(str)

    def __init__(
        self,
        experimentPath: str,
        callback: Callable[[str], None],
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            experimentPath: See the attributes section in _ExperimentCodeThread.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.experimentPath = experimentPath
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.
        
        Fetches the experiment code from the proxy server.

        If the path is a directory or non-existing file, 500 Server error occurs.
        
        After finished, the fetched signal is emitted.
        """
        try:
            response = requests.get("http://127.0.0.1:8000/experiment/code/",
                                    params={"file": self.experimentPath},
                                    timeout=10)
            response.raise_for_status()
            code = response.json()
        except requests.exceptions.RequestException as err:
            print(err)
            return
        self.fetched.emit(code)


class VisualizerApp(qiwis.BaseApp):
    """App for showing the code and sequence viewers.
    
    Attributes:
        experimentClsName: The class name of the experiment.
    """

    def __init__(
        self,
        name: str,
        experimentPath: str,
        experimentClsName: str,
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            experimentPath: See the attributes section in _ExperimentCodeThread.
            experimentClsName: See the attributes section in VisualizerApp.
        """
        super().__init__(name, parent=parent)
        self.experimentClsName = experimentClsName
        self.codeViewerFrame = CodeViewerFrame()
        self.fetchCode(experimentPath)

    @pyqtSlot()
    def fetchCode(self, experimentPath: str):
        """Fetches the experiment code and loads it in self.codeViewerFrame.viewerTree.
        
        Args:
            experimentPath: See the attributes section in _ExperimentCodeThread.
        """
        self.thread = _ExperimentCodeThread(experimentPath, self.loadCodeViewer, self)
        self.thread.start()

    def loadCodeViewer(self, code: str):
        """Loads the code viewer from the experiment code.
        
        Args:
            code: The experiment code.
        """
        stmtList = self.findExperimentStmtList(code)
        for stmt in stmtList:
            stmtText = ast.get_source_segment(code, stmt)
            self.addCodeViewerItem(stmt.lineno, stmtText)

    def findExperimentStmtList(self, code: str) -> List[ast.stmt]:
        """Finds run() of the given experiment code and returns its statement list as ast types.

        Args:
            code: The experiment code.

        Returns:
            A list of all statements in run() of the given experiment code.
            Each element is an instance of ast.stmt class.
        """
        fullStmtList = ast.parse(code).body
        experimentClsStmtList = next(
            stmt for stmt in fullStmtList
            if isinstance(stmt, ast.ClassDef) and stmt.name == self.experimentClsName
        ).body
        runFunctionStmtList = next(
            stmt for stmt in experimentClsStmtList
            if isinstance(stmt, ast.FunctionDef) and stmt.name == "run"
        ).body
        return runFunctionStmtList

    def addCodeViewerItem(self, lineno: int, content: str):
        """Adds the given information into self.codeViewerFrame.viewerTree.
        
        Args:
            lineno: The code line number.
            content: It will be set to a raw code text.
        """
        stmtItem = QTreeWidgetItem(self.codeViewerFrame.viewerTree)
        stmtItem.setText(0, str(lineno))
        stmtItem.setText(1, content)

    def frames(self) -> Tuple[CodeViewerFrame]:
        """Overridden."""
        return (self.codeViewerFrame,)
