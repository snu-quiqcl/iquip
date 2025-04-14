"""Module for oven controller."""

from __future__ import annotations

import functools
import logging
from typing import Any, Callable, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject, Qt, QThread, QTimer
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
        outputChanged(outputted): The output status is changed,
          with the output status as True for turned on, False for turned off.
        clientError(exception): An exception is occurred during client operation,
          with the exception object.
        [current, voltage]Reported([current, voltage]): The [current, voltage] is reported,
          with its value.
        See _signal() method for the other signal's.
    """

    connectionChanged = pyqtSignal(bool)
    outputChanged = pyqtSignal(bool)
    clientError = pyqtSignal(Exception)
    currentReported = pyqtSignal(float)
    voltageReported = pyqtSignal(float)

    closeTarget = pyqtSignal()
    openTarget = pyqtSignal(tuple)
    readCurrent = pyqtSignal()
    readVoltage = pyqtSignal()
    setCurrent = pyqtSignal(float)
    output = pyqtSignal(float)

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        self._client: Optional[Client] = None
        self._targetChannel: Optional[str] = None
        api = (
            "closeTarget",
            "openTarget",
            "readCurrent",
            "readVoltage",
            "setCurrent",
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

    @pyqtSlot(tuple)
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
            self._client = Client(*info[:3], timeout=10)
        except OSError as error:
            self.clientError.emit(error)
        else:
            self._targetChannel = info[3].upper()
            self.connectionChanged.emit(True)

    @pyqtSlot()
    @use_client
    def _readCurrent(self, client: Client):
        """Requests to read the current and reports it."""
        self.currentReported.emit(client.read_current())

    @pyqtSlot()
    @use_client
    def _readVoltage(self, client: Client):
        """Requests to read the voltage and reports it."""
        self.voltageReported.emit(client.read_voltage())

    @pyqtSlot()
    @use_client
    def _setCurrent(self, client: Client, current: float):
        """Sets the current
        
        Args:
            current: Target current.
        """
        client.set_current(current)

    @pyqtSlot(float)
    @use_client
    def _output(self, client: Client, on: bool):
        """Set the current.
        
        Args:
            on: Whether to turn on or off.
        """
        client.output(on)
        self.outputChanged.emit(on)


class OvenProxy:  # pylint: disable=too-few-public-methods
    """Proxy for emitting signals.
    
    Attributes:
        manager: OvenManager object where the power supply unit client for oven object lives.

    Usage:
        proxy = StageProxy(manager)
        proxy.signal(x, y)  # equivalent to: manager.signal.emit(x, y)
    """

    def __init__(self, manager: OvenManager):
        """
        Args:
            See Attributes section.
        """
        self.manager = manager

    @functools.lru_cache(maxsize=8)
    def __getattr__(self, name: str) -> Callable:
        """Returns the signal emit function.
        
        Args:
            name: Signal name in the manager. It will raise an error if there
              is no signal with the given name.
        """
        signal = getattr(self.manager, name)
        return signal.emit


class OvenControllerFrame(QWidget):  # pylint: disable=too-many-instance-attributes
    """Frame for OvenControllerApp.
    
    Attributes:
        connectionButton: Button for toggling rpc connection.
        [current, voltage, timer]DisplayBox: Spinbox displaying the [current, voltage, timer],
          respectively (read-only).
        timerResetButton: Button for timer reset.
        [current, timer]InputBox: Spinbox for target [current, timer].
        outputButton: Button for toggling output.

    Signals:
        openTarget(): Open button is clicked.
        closeTarget(): Close button is clicked.
        setCurrent(current): Current setting is requested, with the target current.
        output(on): Output button is clicked, with whether to turn on or off.
    """

    openTarget = pyqtSignal()
    closeTarget = pyqtSignal()
    setCurrent = pyqtSignal(float)
    output = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):  # pylint: disable=too-many-statements
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
        self.timerDisplayBox = QDoubleSpinBox(self)
        self.timerDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timerDisplayBox.setReadOnly(True)
        self.timerDisplayBox.setDecimals(1)
        self.timerDisplayBox.setSuffix("s")
        self.timerResetButton = QPushButton("Reset", self)
        self.currentInputBox = QDoubleSpinBox(self)
        self.currentInputBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.currentInputBox.setDecimals(3)
        self.currentInputBox.setSingleStep(0.01)
        self.currentInputBox.setSuffix("A")
        self.timerInputBox = QSpinBox(self)
        self.timerInputBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timerInputBox.setMaximum(1000)
        self.timerInputBox.setMinimum(10)
        self.timerInputBox.setSingleStep(10)
        self.timerInputBox.setSuffix("s")
        self.timerInputBox.setValue(100)
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
        self.connectionButton.clicked.connect(self._connectionButtonClicked)
        self.outputButton.clicked.connect(self._outputButtonClicked)
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

    def isConnected(self) -> bool:
        """Returns whether the client is currently connected."""
        return self.connectionButton.isChecked()

    @pyqtSlot(bool)
    def _connectionButtonClicked(self, checked: bool):
        """Connection button is clicked.
        
        Args:
            checked: True for opening the target, False for closing.
        """
        self.connectionButton.setEnabled(False)
        if checked:
            self.openTarget.emit()
        else:
            self.closeTarget.emit()

    @pyqtSlot(float)
    def setDisplayedCurrent(self, current: float):
        """Sets the current displayed on the widget.
        
        Args:
            current: Current.
        """
        self.currentDisplayBox.setValue(current)

    @pyqtSlot(float)
    def setDisplayedVoltage(self, voltage: float):
        """Sets the voltage displayed on the widget.
        
        Args:
            voltage: Voltage.
        """
        self.voltageDisplayBox.setValue(voltage)

    @pyqtSlot(float)
    def setDisplayedTimer(self, on_duration: float):
        """Sets the timer displayed on the widget.
        
        Args:
            on_duration: Duration while the output is turned on.
        """
        self.timerDisplayBox.setValue(on_duration)

    @pyqtSlot(bool)
    def setOutput(self, output_: bool):
        """Sets the current output status.

        This also changes the enabled status and the output button text.
        
        Args:
            open_: True for turned on, False for turned off.
        """
        self.outputButton.setEnabled(True)
        self.outputButton.setText("Off" if output_ else "On")

    @pyqtSlot(bool)
    def _outputButtonClicked(self, checked: bool):
        """Output button is clicked.
        
        Args:
            checked: True for turning on the target, False for turning off.
        """
        self.outputButton.setEnabled(False)
        if checked:
            self.setCurrent.emit(self.currentInputBox.value())
        self.output.emit(checked)

    def expirationTime(self) -> int:
        """Returns timerInputBox value."""
        return self.timerInputBox.value()


class OvenControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling power supply unit for oven.
    
    Attributes:
        managerThread: Oven manager thread.
        manager: OvenManager object.
        proxy: OvenProxy object.
        readTimer: QTimer object for periodic current and voltage read.
        offTimer: QTimer object for automatically turning off output.
        frame: Oven controller frame object.
    """

    def __init__(
        self,
        name: str,
        target: List[Any],
        readPeriod: float = 10.0,
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            target: List of target info: "ip", port, "target_name", "target_channel".
              The target channel must be one of "p6v", "p25v", or "n25v".
            readPeriod: Voltage and current reading period in seconds.
        """
        super().__init__(name, parent=parent)
        # setup threaded manager
        self.managerThread = QThread()
        self.manager = OvenManager()
        self.proxy = OvenProxy(self.manager)
        self.manager.moveToThread(self.managerThread)
        self.managerThread.finished.connect(self.manager.deleteLater)
        self.managerThread.finished.connect(self.managerThread.deleteLater)
        self.managerThread.start()
        # timer for periodic current and voltage read
        self.readTimer = QTimer(self)
        self.readTimer.start(round(readPeriod * 1000))
        # timer for automatically turning off output
        self._on_duration_ms = 0
        self.offTimer = QTimer(self)
        # setup controller frame
        self.frame = OvenControllerFrame()
        self.frame.openTarget.connect(functools.partial(self.proxy.openTarget, tuple(target)))
        self.frame.closeTarget.connect(self.proxy.closeTarget)
        self.frame.timerResetButton.clicked.connect(self.resetTimer)
        self.frame.setCurrent.connect(self.proxy.setCurrent)
        self.frame.output.connect(self.proxy.output)
        self.frame.output.connect(self.handleTimer)
        # signal connection
        self.readTimer.timeout.connect(self.readCurrent, type=Qt.QueuedConnection)
        self.readTimer.timeout.connect(self.readVoltage, type=Qt.QueuedConnection)
        self.offTimer.timeout.connect(self.checkTimer, type=Qt.QueuedConnection)
        self.manager.connectionChanged.connect(
            self.handleConnectionChanged, type=Qt.QueuedConnection
        )
        self.manager.outputChanged.connect(
            self.handleOutputChanged, type=Qt.QueuedConnection
        )
        self.manager.clientError.connect(
            self.handleClientError, type=Qt.QueuedConnection
        )
        self.manager.currentReported.connect(
            self.handleCurrentReported, type=Qt.QueuedConnection
        )
        self.manager.voltageReported.connect(
            self.handleVoltageReported, type=Qt.QueuedConnection
        )

    @pyqtSlot()
    def readCurrent(self):
        """Requests to read the current."""
        if self.frame.isConnected():
            self.proxy.readCurrent()

    @pyqtSlot()
    def readVoltage(self):
        """Requests to read the voltage."""
        if self.frame.isConnected():
            self.proxy.readVoltage()

    @pyqtSlot()
    def resetTimer(self):
        """Resets offTimer."""
        self._on_duration_ms = 0
        self.frame.setDisplayedTimer(0.0)

    @pyqtSlot(float)
    def handleTimer(self, on: bool):
        """Starts or stops offTimer.
        
        Args:
            See OvenControllerFrame.output signal.
        """
        if on:
            self.offTimer.start(100)
        else:
            self.offTimer.stop()

    @pyqtSlot()
    def checkTimer(self):
        """Checks if offTimer has expired."""
        self._on_duration_ms += self.offTimer.interval()
        expirationTime = self.frame.expirationTime()
        if self._on_duration_ms >= expirationTime * 1000:
            self.frame.outputButton.click()
            self.resetTimer()
        else:
            self.frame.setDisplayedTimer(self._on_duration_ms / 1000)

    @pyqtSlot(bool)
    def handleConnectionChanged(self, connected: bool):
        """Handles connectionChanged signal.
        
        Args:
            See OvenManager.connectionChanged signal.
        """
        self.frame.setConnected(connected)

    @pyqtSlot(bool)
    def handleOutputChanged(self, outputted: bool):
        """Handles outputChanged signal.
        
        Args:
            See OvenManager.outputChanged signal.
        """
        self.frame.setOutput(outputted)

    @pyqtSlot(Exception)
    def handleClientError(self, error: Exception):
        """Handles clientError signal.
        
        Args:
            See OvenManager.clientError signal.
        """
        logger.error("Oven reported an error.", exc_info=error)
        self.handleConnectionChanged(False)

    @pyqtSlot(float)
    def handleCurrentReported(self, current: float):
        """Handles currentReported signal.
        
        Args:
            See OvenManager.currentReported signal.
        """
        self.frame.setDisplayedCurrent(current)

    @pyqtSlot(float)
    def handleVoltageReported(self, voltage: float):
        """Handles voltageReported signal.
        
        Args:
            See OvenManager.voltageReported signal.
        """
        self.frame.setDisplayedVoltage(voltage)

    def __del__(self):
        """Quits the thread before destructing."""
        self.managerThread.quit()

    def frames(self) -> Tuple[Tuple[str, OvenControllerFrame]]:
        """Overridden."""
        return (("", self.frame),)
