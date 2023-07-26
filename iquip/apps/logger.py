"""App module for log viewer in apps."""

import logging
from typing import Any, Optional, Tuple, Callable

from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal, QDateTime
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QTextEdit, QLabel, QDialogButtonBox, QComboBox
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
        levelBox: A comboBox for setting the logger's level.
    """

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.logEdit = QTextEdit(self)
        self.logEdit.setReadOnly(True)
        self.clearButton = QPushButton("Clear", self)
        self.levelBox = QComboBox(self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.logEdit)
        layout.addWidget(self.clearButton)
        layout.addWidget(self.levelBox)


class ConfirmClearingFrame(QWidget):
    """A confirmation frame for log clearing in the LoggerFrame.
    
    Attributes:
        label: Displays a confirmation message to clear logs in the LoggerFrame.
        buttonBox: Contains OK and Cancel button to check whether to clear logs.
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

    Sets a handler of root logger and manages loggerFrame to show log messages.
    Gives options to clear logs and select log level in the loggerFrame.

    Attributes:
        loggerFrame: A frame that shows the logs.
        confirmFrame: A frame that asks whether to clear logs.
        handler: A handler for adding logs to the loggerFrame. 
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.loggerFrame = LoggerFrame()
        self.confirmFrame = ConfirmClearingFrame()
        # connect signals to slots
        self.loggerFrame.clearButton.clicked.connect(self.checkToClear)
        self.confirmFrame.confirmed.connect(self.clearLog)
        self.handler = LoggingHandler(self.addLog)
        # TODO(aijuh): Change the log format when it is determined.
        fs ="%(levelname)s [%(name)s] [%(filename)s:%(lineno)d] %(message)s "
        formatter = logging.Formatter(fs)
        self.handler.setFormatter(formatter)
        rootLogger = logging.getLogger()
        rootLogger.addHandler(self.handler)
        self.setLevel("WARNING")
        self.loggerFrame.levelBox.addItems(["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.loggerFrame.levelBox.textActivated.connect(self.setLevel)
        self.loggerFrame.levelBox.setCurrentText("WARNING")

    @pyqtSlot(str)
    def setLevel(self, levelText: str):
        """Responds to the loggerFrame's levelBox widget and changes the handler's level.

        Args:
            leveltext: Selected level in the level select box.
              It should be one of "DEBUG", "INFO", "WARNING", "ERROR" and "CRITICAL".
              It should be case-sensitive and any other input is ignored.
        """
        levels = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL
        }
        if levelText in levels:
            self.handler.setLevel(levels[levelText])
            logging.getLogger().setLevel(levels[levelText])

    def frames(self) -> Tuple[LoggerFrame]:
        """Overridden."""
        return (self.loggerFrame,)

    @pyqtSlot(str)
    def addLog(self, content: str):
        """Adds a channel name and log message.

        Args:
            content: Received log message.
        """
        timeString = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.loggerFrame.logEdit.insertPlainText(f"{timeString}: {content}\n")

    @pyqtSlot()
    def checkToClear(self):
        """Shows a confirmation frame for clearing log."""
        logger.info("Tried to clear logs by clicking clear button")
        self.confirmFrame.show()

    @pyqtSlot()
    def clearLog(self):
        """Clears the log text edit."""
        self.loggerFrame.logEdit.clear()
