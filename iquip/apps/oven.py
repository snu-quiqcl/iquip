"""Module for oven controller."""

import functools
import logging
from typing import Any, Callable, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QDoubleSpinBox, QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

import qiwis
from sipyco.pc_rpc import Client

logger = logging.getLogger(__name__)

RPCTargetInfo = Tuple[str, int, str, str]  # ip, port, target_name, target_channel

def use_client(function: Callable[..., None]) -> Callable[..., None]:
    """Decorator which adds the client object in arguments.

    If an OSError occurs while running function, the RPC client is closed.
    
    Args:
        function: Decorated function. It should take the Client object as the first argument.
    """
    @functools.wraps(function)
    def wrapped(self: OvenManager, *args, **kwargs):
        """Adds the client object."""
        client = self._client  # pylint: disable=protected-access
        if client is None:
            logger.error("Failed to get client.")
            self.clientError.emit(ValueError("There is no client."))
            return
        try:
            function(self, client, *args, **kwargs)
        except (AttributeError, OSError, ValueError) as error:
            logger.exception("Error occurred while running %s with the client.", function.__name__)
            self.clientError.emit(error)
            self._closeTarget()  # pylint: disable=protected-access
    return wrapped


class OvenManager(QObject):
    """Manages the power supply unit RPC client for oven which lives in a dedicated thread.
    
    An instance of this class should be moved to a thread other than the main
      GUI thread to prevent GUI from freezing.
    Therefore, the private methods must not be called from the main thread.
    Instead, use signals to communicate.

    Signals:
        connectionChanged(connected): The client connection status is changed,
          with the connection status as True for connected, False for disconnected.
        clientError(exception): An exception is occurred during client operation,
          with the exception object.
        [current, voltage]Reported([current, voltage]): The [current, voltage] is reported,
          with its value.
        See _signal() method for the other signal's.
    """

    connectionChanged = pyqtSignal(bool)
    clientError = pyqtSignal(Exception)
    currentReported = pyqtSignal(float)
    voltageReported = pyqtSignal(float)

    closeTarget = pyqtSignal()
    openTarget = pyqtSignal()
    getCurrent = pyqtSignal()
    getVoltage = pyqtSignal()
    output = pyqtSignal(float)

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        self._client: Optional[Client] = None
        self._targetChannel: Optional[str] = None
        api = (
            "closeTarget",
            "openTarget",
            "getCurrent",
            "getVoltage",
            "output",
        )
        for name in api:
            signal = getattr(self, name)
            method = getattr(self, f"_{name}")
            signal.connect(method, type=Qt.QueuedConnection)

    @pyqtSlot()
    def _closeTarget(self):
        """Closes the RPC client."""
        if self._client is None:
            logger.error("Failed to close target: RPC client does not exist.")
            return
        self._client.close_rpc()
        self.connectionChanged.emit(False)

    @pyqtSlot()
    def _openTarget(self, info: RPCTargetInfo):
        """Creates the RPC client and connects it to the server.
        
        Args:
            info: RPC target information tuple.
        """
        if self._client is not None:
            self._closeTarget()
        if info[3] not in ("p6v", "p25v", "n25v"):
            self.clientError.emit(ValueError("Target channel must be one of p6v, p25v, or n25v."))
            return
        try:
            self._client = Client(*info[:3], timeout=5)
        except OSError as error:
            self.clientError.emit(error)
        else:
            self._targetChannel = info[3].upper()
            self.connectionChanged.emit(True)

    @pyqtSlot()
    @use_client
    def _getCurrent(self, client: Client):
        """Requests the current and reports it."""
        method = getattr(client, f"get_{self._targetChannel}_current")
        self.currentReported.emit(method())

    @pyqtSlot()
    def _getVoltage(self, client: Client):
        """Requests the voltage and reports it."""
        method = getattr(client, f"get_{self._targetChannel}_voltage")
        self.voltageReported.emit(method())

    @pyqtSlot(float)
    @use_client
    def _output(self, client: Client, current: float):
        """Set the current.
        
        Args:
            current: Target current in ampere.
        """
        method = getattr(client, f"set_{self._targetChannel}_current")
        method(current)


class OvenControllerFrame(QWidget):
    """Frame for OvenControllerApp.
    
    Attributes:
        connectionButton: Button for toggling rpc connection.
        [current, voltage, timer]DisplayBox: Spinbox displaying the [current, voltage, timer],
          respectively (read-only).

    Signals:
        openTarget(): Open button is clicked.
        closeTarget(): Close button is clicked.
    """

    openTarget = pyqtSignal()
    closeTarget = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent=parent)
        # widgets
        self.connectionButton = QPushButton("Open", self)
        self.connectionButton.setCheckable(True)
        self.currentDisplayBox = QDoubleSpinBox(self)
        self.currentDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.currentDisplayBox.setReadOnly(True)
        self.currentDisplayBox.setDecimals(3)
        self.currentDisplayBox.setSuffix("A")
        self.voltageDisplayBox = QDoubleSpinBox(self)
        self.voltageDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.voltageDisplayBox.setReadOnly(True)
        self.voltageDisplayBox.setDecimals(3)
        self.voltageDisplayBox.setSuffix("V")
        self.timerDisplayBox = QSpinBox(self)
        self.timerDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timerDisplayBox.setReadOnly(True)
        self.timerDisplayBox.setSuffix("s")
        self.timerResetButton = QPushButton("Reset", self)
        self.currentInputBox = QDoubleSpinBox(self)
        self.currentInputBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.currentInputBox.setDecimals(3)
        self.currentInputBox.setSingleStep(0.01)
        self.currentInputBox.setSuffix("A")
        self.timerInputBox = QSpinBox(self)
        self.timerInputBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timerInputBox.setSingleStep(10)
        self.timerInputBox.setSuffix("s")
        self.outputButton = QPushButton("On", self)
        self.outputButton.setCheckable(True)
        self._inner = QWidget(self)  # except connectionButton
        # layout
        displayLayout = QHBoxLayout()
        displayLayout.addWidget(self.currentDisplayBox)
        displayLayout.addWidget(self.voltageDisplayBox)
        displayLayout.addWidget(self.timerDisplayBox)
        displayLayout.addWidget(self.timerResetButton)
        inputLayout = QHBoxLayout()
        inputLayout.addWidget(self.currentInputBox)
        inputLayout.addWidget(self.timerInputBox)
        inputLayout.addWidget(self.outputButton)
        innerLayout = QVBoxLayout(self._inner)
        innerLayout.addLayout(displayLayout)
        innerLayout.addLayout(inputLayout)
        layout = QVBoxLayout(self)
        layout.addWidget(self.connectionButton)
        layout.addWidget(self._inner)
        # signal connection
        self.connectionButton.clicked.connect(
            functools.partial(self.connectionButton.setEnabled, False))
        self.connectionButton.clicked.connect(self._connectionButtonClicked)
        # initialize state
        self.setConnected(False)

    @pyqtSlot(bool)
    def setConnected(self, open_: bool):
        """Sets the current connection status.

        This also changes the enabled status and the connection button text.
        
        Args:
            open_: True for open, False for closed.
        """
        self._inner.setEnabled(open_)
        self.connectionButton.setEnabled(True)
        self.connectionButton.setText("Close" if open_ else "Open")

    @pyqtSlot(bool)
    def _connectionButtonClicked(self, checked: bool):
        """Connection button is clicked.
        
        Args:
            checked: True for opening the target, False for closing.
        """
        if checked:
            self.openTarget.emit()
        else:
            self.closeTarget.emit()


class OvenControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling power supply unit for oven."""

    def __init__(
        self,
        name: str,
        target: List[Any],
        period: float = 10.0,
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            target: List of target info: "ip", port, "target_name", "target_channel".
              The target channel must be one of "p6v", "p25v", or "n25v".
            period: Voltage and current reading period in seconds.
        """
        super().__init__(name, parent=parent)
        self.frame = OvenControllerFrame()

    def frames(self) -> Tuple[Tuple[str, OvenControllerFrame]]:
        """Overridden."""
        return (("", self.frame),)
