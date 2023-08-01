"""App module for log viewer in apps."""

import logging
from logging import handlers
from typing import Any, Optional, Tuple, Callable

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QDialogButtonBox, QComboBox, QGridLayout
)

import qiwis

logger = logging.getLogger(__name__)


class _Signaller(QObject):
    """Signal only for LoggingHandler.

    Signals:
        signal(log): A formatted log message is emitted. 
    """

    signal = pyqtSignal(str)


class LoggingHandler(logging.Handler):
    """Handler for logger.

    Sends a log message to the connected function through a signal.

    Attributes:
        signaller: A _Signaller class contains signal for emitting log.
    """

    def __init__(self, slotfunc: Callable[[str], Any]):
        """Extended.

        Connects the slotfunc to the signal.

        Args:
            slotfunc: A slot function which is called when a log record is emitted.
        """
        super().__init__()
        self.signaller = _Signaller()
        self.signaller.signal.connect(slotfunc)

    def emit(self, record: logging.LogRecord):
        """Overridden.
        
        Emits input signal to the connected function.
        """
        logMsg = self.format(record)
        self.signaller.signal.emit(logMsg)


class LoggerFrame(QWidget):
    """Frame for logging.

    Attributes:
        logEdit: A textEdit which shows all logs.
        clearButton: A button for clearing all logs.
        frameLevelBoxLabel: A label for describing frameLevelBox.
        frameLevelBox: A comboBox for setting the logger's level for displaying logs to Loggerframe.
        fileLevelBoxLabel: A label for describing fileLevelBox.
        fileLevelBox: A comboBox for setting the file logger's level for saving logs to file.
    """

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.logEdit = QTextEdit(self)
        self.logEdit.setReadOnly(True)
        self.clearButton = QPushButton("Clear", self)
        self.frameLevelBoxLabel = QLabel("Select screen log's level:")
        self.frameLevelBox = QComboBox(self)
        self.fileLevelBoxLabel = QLabel("Select file log's level:")
        self.fileLevelBox = QComboBox(self)
        # layout
        layout = QGridLayout(self)
        layout.addWidget(self.logEdit, 0, 0, 1, 6)
        layout.addWidget(self.clearButton,1, 0, 1, 6)
        layout.addWidget(self.frameLevelBoxLabel, 2, 0, 1, 2)
        layout.addWidget(self.frameLevelBox, 2, 2, 1, 4)
        layout.addWidget(self.fileLevelBoxLabel, 3, 0, 1, 2)
        layout.addWidget(self.fileLevelBox, 3, 2, 1, 4)


class ConfirmClearingFrame(QWidget):
    """A confirmation frame for log clearing in the LoggerFrame.
    
    Attributes:
        label: The label for displaying a confirmation message to clear logs in the LoggerFrame.
        buttonBox: The buttonBox with OK and Cancel button to check whether to clear logs.

    Signals:
        confirmed: A pyqtSignal that emits signal when Ok button is clicked.
    """

    confirmed = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Are you sure to clear?", self)
        self.buttonBox = QDialogButtonBox(self)
        self.buttonBox.addButton("OK", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Cancel", QDialogButtonBox.RejectRole)
        # connect signals
        self.buttonBox.accepted.connect(self.buttonOKClicked)
        self.buttonBox.rejected.connect(self.buttonCancelClicked)
        # layouts
        layout = QVBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.buttonBox)

    def buttonOKClicked(self):
        """Called when the OK button is clicked."""
        self.confirmed.emit()
        self.close()

    def buttonCancelClicked(self):
        """Called when the Cancel button is clicked."""
        self.close()


class LoggerApp(qiwis.BaseApp):
    """App for logging.

    Sets a handler of the root logger and manages the loggerFrame to show log messages.
    Gives options to clear logs and select log level in the loggerFrame.

    Attributes:
        loggerFrame: A frame that shows the logs.
        confirmFrame: A frame that asks whether to clear logs.
        frameHandler: A handler for adding logs to the loggerFrame.
        fileHandler: A handler for saving logs to file.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.loggerFrame = LoggerFrame()
        self.confirmFrame = ConfirmClearingFrame()
        # connect signals to slots
        self.loggerFrame.clearButton.clicked.connect(self.checkToClear)
        self.confirmFrame.confirmed.connect(self.clearLog)
        #initialize logger
        self.initLogger()
        # set loggerFrame's frameLevelBox
        self.loggerFrame.frameLevelBox.addItems(self.levels_dict.values())
        self.loggerFrame.frameLevelBox.textActivated.connect(self.setFrameLevel)
        self.loggerFrame.frameLevelBox.setCurrentText(self.levels_dict[self.frameHandler.level])
        # set loggerFrame's fileLevelBox
        self.loggerFrame.fileLevelBox.addItems(self.levels_dict.values())
        self.loggerFrame.fileLevelBox.textActivated.connect(self.setFileLevel)
        self.loggerFrame.fileLevelBox.setCurrentText(self.levels_dict[self.fileHandler.level])

    def initLogger(self):
        """Initializes the root logger and handlers for constructor."""
        self.levels_dict = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        # initialize handlers
        self.frameHandler = LoggingHandler(self.addLog)
        self.fileHandler = handlers.TimedRotatingFileHandler(filename = "log", when = "midnight",
                                                             interval = 1, encoding = 'utf-8')
        self.fileHandler.suffix = '-%Y%m%d'
        simpleFormat = "[%(name)s] %(message)s"
        complexFormat = "%(asctime)s %(levelname)s [%(name)s]"\
                        " [%(filename)s:%(lineno)d] %(message)s"
        self.frameHandler.setFormatter(logging.Formatter(simpleFormat))
        self.fileHandler.setFormatter(logging.Formatter(complexFormat))
        # set rootLogger
        rootLogger = logging.getLogger()
        rootLogger.addHandler(self.frameHandler)
        rootLogger.addHandler(self.fileHandler)
        self.fileHandler.setLevel("WARNING")
        self.setFrameLevel("WARNING")
        self.setFileLevel("WARNING")


    def frames(self) -> Tuple[LoggerFrame]:
        """Overridden."""
        return (self.loggerFrame,)

    @pyqtSlot(str)
    def setFrameLevel(self, levelText: str):
        """Responds to the loggerFrame's frameLevelBox widget and changes the handler's level.

        Args:
            leveltext: Selected level in the level select box.
              It should be one of "DEBUG", "INFO", "WARNING", "ERROR" and "CRITICAL".
              It should be case-sensitive and any other input is ignored.
        """
        if levelText in self.levels_dict.values():
            self.frameHandler.setLevel(levelText)
            if self.frameHandler.level < self.fileHandler.level:
                logging.getLogger().setLevel(levelText)
            else:
                logging.getLogger().setLevel(self.levels_dict[self.fileHandler.level])

    @pyqtSlot(str)
    def setFileLevel(self, levelText: str):
        """Responds to the loggerFrame's fileLevelBox widget and changes the handler's level.

        Args:
            leveltext: Selected level in the level select box.
              It should be one of "DEBUG", "INFO", "WARNING", "ERROR" and "CRITICAL".
              It should be case-sensitive and any other input is ignored.
        """
        if levelText in self.levels_dict.values():
            self.fileHandler.setLevel(levelText)
            if self.fileHandler.level < self.frameHandler.level:
                logging.getLogger().setLevel(levelText)
            else:
                logging.getLogger().setLevel(self.levels_dict[self.frameHandler.level])

    @pyqtSlot(str)
    def addLog(self, content: str):
        """Adds a received log message to the LoggerFrame.

        Args:
            content: Received log message.
        """
        timeString = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.loggerFrame.logEdit.insertPlainText(f"{timeString}: {content}\n")

    @pyqtSlot()
    def checkToClear(self):
        """Shows a confirmation frame for clearing logs in the loggerFrame."""
        logger.info("Tried to clear logs by clicking clear button")
        self.confirmFrame.show()

    @pyqtSlot()
    def clearLog(self):
        """Clears the log texts in the loggerFrame."""
        self.loggerFrame.logEdit.clear()
