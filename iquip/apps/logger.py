"""App module for log viewer in apps."""

import logging
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
        levelBoxLabel: A label for describing levelBox.
        levelBox: A comboBox for setting the logger's level.
        fileWriteButton: A button for wrtie logs to file.
        fileClearButton: A button for clear logs in file.
    """

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.logEdit = QTextEdit(self)
        self.logEdit.setReadOnly(True)
        self.clearButton = QPushButton("Clear", self)
        self.levelBoxLabel = QLabel("Select log's level:")
        self.levelBox = QComboBox(self)
        self.fileWriteButton = QPushButton("Save log to file")
        self.fileClearButton = QPushButton("Clear log file")
        # layout
        layout = QGridLayout(self)
        layout.addWidget(self.logEdit, 0, 0, 1, 6)
        layout.addWidget(self.clearButton,1, 0, 1, 6)
        layout.addWidget(self.levelBoxLabel, 2, 0, 1, 2)
        layout.addWidget(self.levelBox, 2, 2, 1, 4)
        layout.addWidget(self.fileWriteButton, 3, 0, 1, 3)
        layout.addWidget(self.fileClearButton, 3, 3, 1, 3)


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


class ConfirmFileClearFrame(QWidget):
    """A confirmation frame for clearing the log record file's log messages."""
    confirmed = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Are you sure to clear log file?")
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("OK", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Cancel", QDialogButtonBox.RejectRole)
        # connect signals
        self.buttonBox.accepted.connect(self.buttonOKClicked)
        self.buttonBox.rejected.connect(self.buttonCancelClicked)
        # layouts
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.label)
        layout.addWidget(self.buttonBox)

    def buttonOKClicked(self):
        """Clicked OK button to clear the log record file."""
        self.confirmed.emit()
        self.close()

    def buttonCancelClicked(self):
        """Clicked Cancel button not to clear the log record file."""
        self.close()


class ConfirmFileWriteFrame(QWidget):
    """A confirmation frame for writing log messages to the log record file."""
    confirmed = pyqtSignal()

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.label = QLabel("Are you sure to write log messages to log file?")
        self.buttonBox = QDialogButtonBox()
        self.buttonBox.addButton("OK", QDialogButtonBox.AcceptRole)
        self.buttonBox.addButton("Cancel", QDialogButtonBox.RejectRole)
        # connect signals
        self.buttonBox.accepted.connect(self.buttonOKClicked)
        self.buttonBox.rejected.connect(self.buttonCancelClicked)
        # layouts
        layout = QVBoxLayout()
        self.setLayout(layout)
        layout.addWidget(self.label)
        layout.addWidget(self.buttonBox)

    def buttonOKClicked(self):
        """Clicked OK button to wrtie log messages to the log record file."""
        self.confirmed.emit()
        self.close()

    def buttonCancelClicked(self):
        """Clicked Cancel button not to write log messages to the log record file."""
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
        self.confirmFileClearFrame = ConfirmFileClearFrame()
        self.confirmFileWriteFrame = ConfirmFileWriteFrame()
        # connect signals to slots
        self.loggerFrame.clearButton.clicked.connect(self.checkToClear)
        self.loggerFrame.fileWriteButton.clicked.connect(self.checkToWriteFile)
        self.loggerFrame.fileClearButton.clicked.connect(self.checkToClearFile)
        self.confirmFrame.confirmed.connect(self.clearLog)
        self.confirmFileClearFrame.confirmed.connect(self.clearFile)
        self.confirmFileWriteFrame.confirmed.connect(self.writeToFile)
        # clear the log_temp file
        self.dirTempLogFile = "log_temp.txt"
        self.dirLogFIle = "log_record.txt"
        with open(self.dirTempLogFile, mode = "w", encoding = "utf-8"):
            pass
        # initialize handlers
        self.frameHandler = LoggingHandler(self.addLog)
        self.fileHandler = logging.FileHandler(self.dirTempLogFile)
        simpleFormat = "[%(name)s] %(message)s"
        complexFormat = "%(asctime)s %(levelname)s [%(name)s]"\
                        " [%(filename)s:%(lineno)d] %(message)s"
        self.frameHandler.setFormatter(logging.Formatter(simpleFormat))
        self.fileHandler.setFormatter(logging.Formatter(complexFormat))
        # set rootLogger
        rootLogger = logging.getLogger()
        rootLogger.addHandler(self.frameHandler)
        rootLogger.addHandler(self.fileHandler)
        self.setLevel("WARNING")
        # set loggerFrame's levelBox
        levels_dict = {10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
        self.loggerFrame.levelBox.addItems(levels_dict.values())
        self.loggerFrame.levelBox.textActivated.connect(self.setLevel)
        self.loggerFrame.levelBox.setCurrentText(levels_dict[self.frameHandler.level])

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
            self.frameHandler.setLevel(levels[levelText])
            self.fileHandler.setLevel(levels[levelText])
            logging.getLogger().setLevel(levels[levelText])

    def frames(self) -> Tuple[LoggerFrame]:
        """Overridden."""
        return (self.loggerFrame,)

    @pyqtSlot(str)
    def addLog(self, content: str):
        """Adds a received log message to the LoggerFrame.

        Args:
            content: Received log message.
        """
        timeString = QDateTime.currentDateTime().toString("yyyy-MM-dd HH:mm:ss")
        self.loggerFrame.logEdit.insertPlainText(f"{timeString}: {content}\n")

    @pyqtSlot()
    def checkToWriteFile(self):
        """Shows a confirmation frame for writing to the log record file."""
        logger.info("Clicked to write log messages to log file.")
        self.confirmFileWriteFrame.show()

    @pyqtSlot()
    def writeToFile(self):
        """Writes log messages in log_temp file to log record file."""
        with open("log_record.txt", mode = "a", encoding = "utf-8") as logFile:
            with open("log_temp.txt", mode = "r+", encoding = "utf-8") as tempFile:
                while True:
                    line = tempFile.readline()
                    if not line:
                        break
                    logFile.write(line)
                tempFile.seek(0, 0)
                tempFile.truncate()

    @pyqtSlot()
    def checkToClearFile(self):
        """Shows a confirmation frame for clearing the log record file."""
        logger.info("Clicked to clear log messages in log file.")
        self.confirmFileClearFrame.show()

    @pyqtSlot()
    def clearFile(self):
        """Clears log messages in the log record file."""
        with open("log_record.txt", mode = "w", encoding = "utf-8"):
            pass

    @pyqtSlot()
    def checkToClear(self):
        """Shows a confirmation frame for clearing logs in the loggerFrame."""
        logger.info("Tried to clear logs by clicking clear button")
        self.confirmFrame.show()

    @pyqtSlot()
    def clearLog(self):
        """Clears the log texts in the loggerFrame."""
        self.loggerFrame.logEdit.clear()