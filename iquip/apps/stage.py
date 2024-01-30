"""Module for stage controller."""

import functools
import logging
from typing import Any, Callable, Dict, Optional, Tuple

from sipyco.pc_rpc import Client
from PyQt5.QtCore import QObject, QThread, QTimer, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QDoubleSpinBox, QGroupBox, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
)

import qiwis

logger = logging.getLogger(__name__)

RPCTargetInfo = Tuple[str, int, str]  # ip, port, target_name

def use_client(function: Callable[..., None]) -> Callable[..., None]:
    """Decorator which adds a client object in arguments.

    If the key does not exist, function is not called at all.
    If an OSError occurs while running function, the RPC client is closed and
        removed from the client dictionary. 
    
    Args:
        function: Decorated function. It should take a Client object and its key
            as the first and second arguments, respectively.
    """
    @functools.wraps(function)
    def wrapped(self: "StageManager", key: str, *args, **kwargs):
        """Translates a string key to a client.
        
        Args:
            key: String key for identifying the client.
        """
        client = self._clients.get(key, None)  # pylint: disable=protected-access
        if client is None:
            logger.error("Failed to get client %s.", key)
            self.clientError.emit(key, KeyError(f"There is no client {key}"))
            return
        try:
            function(self, client, key, *args, **kwargs)
        except OSError as error:
            logger.exception("Error occurred while running %s with client %s.", function, key)
            self.clientError.emit(key, error)
            self._closeTarget(key)
    return wrapped


class StageManager(QObject):
    """Manages the stage RPC clients which live in a dedicated thread.
    
    An instance of this class should be moved to a thread other than the main
      GUI thread to prevent GUI from freezing.
    Therefore, the private methods must not be called from the main thread.
    Instead, use signals to communicate.

    Signals:
        connectionChanged(key, connected): A client connection status is changed,
          with its string key and connection status as True for connected, False
          for disconnected.
        clientError(key, exception): An exception is occurred during client operation,
          with the corresponding client key and exception object.
        positionReported(key, position_m): The current position of a stage is
          reported, with the client key and the position in meters.
        See _signal() method for the other signal's.
    """

    connectionChanged = pyqtSignal(str, bool)
    clientError = pyqtSignal(str, Exception)
    positionReported = pyqtSignal(str, float)

    clear = pyqtSignal()
    closeTarget = pyqtSignal(str)
    connectTarget = pyqtSignal(str, tuple)
    getPosition = pyqtSignal(str)
    moveBy = pyqtSignal(str, float)
    moveTo = pyqtSignal(str, float)

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        self._clients: Dict[str, Client] = {}
        api = (
            "clear",
            "closeTarget",
            "connectTarget",
            "moveBy",
            "moveTo",
        )
        for name in api:
            signal = getattr(self, name)
            method = getattr(self, f"_{name}")
            signal.connect(method, type=Qt.QueuedConnection)

    @pyqtSlot()
    def _clear(self):
        """Closes all the RPC clients and clears the client dictionary."""
        for key in tuple(self._clients):
            self._closeTarget(key)

    @pyqtSlot(str)
    def _closeTarget(self, key: str):
        """Closes a certain RPC client and removes it from the client dictionary.
        
        Args:
            key: String key for identifying the client. If the key does not exist,
              it logs the error and does not raise any exception.
        """
        client = self._clients.pop(key, None)
        if client is None:
            logger.error("Failed to close target: RPC client %s does not exist.", key)
            return
        client.close_rpc()
        self.connectionChanged.emit(key, False)

    @pyqtSlot(str, tuple)
    def _connectTarget(self, key: str, info: RPCTargetInfo):
        """Creates an RPC client and connects it to the server.
        
        Args:
            key: String key for identifying the client. If the key already exists,
              the previous one is closed and replaced with the new one.
            info: RPC target information tuple.
        """
        client = self._clients.get(key, None)
        if client is not None:
            self._closeTarget(key)
        try:
            self._clients[key] = Client(*info)
        except OSError as error:
            self.clientError.emit(key, error)
        else:
            self.connectionChanged.emit(key, True)

    @pyqtSlot(str)
    @use_client
    def _getPosition(self, client: Client, key: str):
        """Requests the current stage position in meters and reports it."""
        self.positionReported.emit(key, client.get_position())

    @pyqtSlot(str, float)
    @use_client
    def _moveBy(self, client: Client, _key: str, displacement_m: float):
        """Moves the stage by given displacement.
        
        Args:
            displacement_m: Relative move displacement in meters.
        """
        client.move_by(displacement_m)

    @pyqtSlot(str, float)
    @use_client
    def _moveTo(self, client: Client, _key: str, position_m: float):
        """Moves the stage to given position.
        
        Args:
            position_m: Absolute destination position in meters.
        """
        client.move_to(position_m)


class StageProxy:  # pylint: disable=too-few-public-methods
    """Proxy bound to a string key for emitting signals with the key.
    
    Usage:
        proxy = StageProxy(manager, key)
        proxy.signal(x, y)  # equivalent to: manager.signal.emit(key, x, y)
    """

    def __init__(self, manager: StageManager, key: str):
        """
        Args:
            manager: StageManager object where the target stage client object lives.
            key: String key for identifying the client.
        """
        self.manager = manager
        self.key = key

    @functools.lru_cache(maxsize=8)
    def __getattr__(self, name: str) -> Callable:
        """Returns partial signal emit function with the key included.
        
        Args:
            name: Signal name in the manager. It will raise an error if there
              is no signal with the given name.
        """
        signal = getattr(self.manager, name)
        return functools.partial(signal.emit, self.key)


class StageWidget(QWidget):
    """UI for stage control.

    Signals:
        moveTo(position_m): Absolute move button is clicked, with the destination
          position in meters.
        moveBy(displacement_m): Relative move button is clicked, with the desired
          displacement in meters.
        tryConnect(): Connect button is clicked.
    
    All the displayed values are in mm unit.
    However, the values for interface (methods and signals) are in m.
    """

    moveTo = pyqtSignal(float)
    moveBy = pyqtSignal(float)
    tryConnect = pyqtSignal()

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.connectButton = QPushButton("Connect", self)
        self.positionBox = QDoubleSpinBox(self)
        self.positionBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.positionBox.setReadOnly(True)
        self.positionBox.setDecimals(3)
        self.positionBox.setSuffix("mm")
        self.positionBox.setAlignment(Qt.AlignHCenter)
        self.absoluteBox = QDoubleSpinBox(self)
        self.absoluteBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.absoluteBox.setDecimals(3)
        self.absoluteBox.setSingleStep(0.001)
        self.absoluteBox.setAlignment(Qt.AlignRight)
        self.absoluteButton = QPushButton("Go", self)
        self.relativeBox = QDoubleSpinBox(self)
        self.relativeBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.relativeBox.setDecimals(3)
        self.relativeBox.setSingleStep(0.001)
        self.relativeBox.setAlignment(Qt.AlignRight)
        self.relativePositiveButton = QPushButton("Move +", self)
        self.relativeNegativeButton = QPushButton("Move -", self)
        self._inner = QWidget(self)  # except connectButton
        # layout
        abosluteLayout = QVBoxLayout()
        abosluteLayout.addWidget(self.absoluteBox)
        abosluteLayout.addWidget(self.absoluteButton)
        relativeLayout = QVBoxLayout()
        relativeLayout.addWidget(self.relativePositiveButton)
        relativeLayout.addWidget(self.relativeBox)
        relativeLayout.addWidget(self.relativeNegativeButton)
        moveLayout = QHBoxLayout()
        moveLayout.addLayout(abosluteLayout)
        moveLayout.addLayout(relativeLayout)
        innerLayout = QVBoxLayout(self._inner)
        innerLayout.addWidget(self.positionBox)
        innerLayout.addLayout(moveLayout)
        layout = QVBoxLayout(self)
        layout.addWidget(self.connectButton)
        layout.addWidget(self._inner)
        # signal connection
        self.connectButton.clicked.connect(self.tryConnect)
        self.absoluteButton.clicked.connect(self._absoluteMove)
        self.relativePositiveButton.clicked.connect(self._relativePositiveMove)
        self.relativeNegativeButton.clicked.connect(self._relativeNegativeMove)
        # initialize state
        self.setConnected(False)

    @pyqtSlot(bool)
    def setConnected(self, connected: bool):
        """Sets the current connection status.

        This also changes the enabled status and the connect button text.
        
        Args:
            connected: True for connected, False for disconnected.
        """
        self._inner.setEnabled(connected)
        self.connectButton.setEnabled(not connected)
        self.connectButton.setText("Connected" if connected else "Connect")

    def isConnected(self) -> bool:
        """Returns whether the client is currently connected."""
        return self._inner.isEnabled()

    @pyqtSlot(float)
    def setPosition(self, position_m: float):
        """Sets the current position displayed on the widget.
        
        Args:
            position_m: Position in meters.
        """
        self.positionBox.setValue(position_m * 1e3)

    def position(self) -> float:
        """Returns the current position in meters."""
        return self.positionBox.value() / 1e3

    @pyqtSlot()
    def _absoluteMove(self):
        """Absolute move button is clicked."""
        self.moveTo.emit(self.absoluteBox.value() / 1e3)

    @pyqtSlot()
    def _relativePositiveMove(self):
        """Relative positive move button is clicked."""
        self.moveBy.emit(self.relativeBox.value() / 1e3)

    @pyqtSlot()
    def _relativeNegativeMove(self):
        """Relative negative move button is clicked."""
        self.moveBy.emit(-self.relativeBox.value() / 1e3)


class StageControllerFrame(QWidget):
    """Frame for StageControllerApp.
    
    Attributes:
        widgets: Dictionary whose keys are stage names and the values are the
          corresponding stage widgets.
    """

    def __init__(
        self,
        stages: Dict[str, Dict[str, Any]],
        parent: Optional[QWidget] = None,
    ):
        """Extended.
        
        Args:
            See StageControllerApp.
        """
        super().__init__(parent=parent)
        self.widgets: Dict[str, StageWidget] = {}
        layout = QGridLayout(self)
        for stage_name, stage_info in stages.items():
            widget = StageWidget(self)
            groupbox = QGroupBox(stage_name, self)
            groupboxLayout = QHBoxLayout(groupbox)
            groupboxLayout.addWidget(widget)
            layout.addWidget(groupbox, *stage_info["index"])
            self.widgets[stage_name] = widget


class StageControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling motorized stages."""

    def __init__(
        self,
        name: str,
        stages: Dict[str, Dict[str, Any]],
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            stages: Dictionary of stage information. Each key is the name of the
              stage and the value is agian a dictionary, whose structure is:
              {
                "index": [row, column],
                "target": ["ip", port, "target_name"]
              }
        """
        super().__init__(name, parent=parent)
        # setup threaded manager
        self.thread = QThread()
        self.manager = StageManager()
        self.proxies = {key: StageProxy(self.manager, key) for key in stages}
        self.manager.moveToThread(self.thread)
        self.thread.finished.connect(self.manager.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.start()
        # timer for periodic position read
        self.timer = QTimer(self)
        self.timer.start(500)
        # setup controller frame
        self.frame = StageControllerFrame(stages, self)
        for key, info in stages.items():
            proxy = self.proxies[key]
            widget = self.frame.widgets[key]
            widget.tryConnect.connect(functools.partial(proxy.connectTarget, info["target"]))
            widget.moveBy.connect(proxy.moveBy)
            widget.moveTo.connect(proxy.moveTo)
        # signal connection
        self.timer.timeout.connect(self.readAllPositions, type=Qt.QueuedConnection)
        self.manager.connectionChanged.connect(
            self.handleConnectionChanged, type=Qt.QueuedConnection
        )
        self.manager.clientError.connect(
            self.handleClientError, type=Qt.QueuedConnection
        )
        self.manager.positionReported.connect(
            self.handlePositionReported, type=Qt.QueuedConnection
        )

    @pyqtSlot()
    def readAllPositions(self):
        """Requests positions of all connected stages."""
        for key, widget in self.frame.widgets.items():
            if widget.isConnected():
                self.proxies[key].getPosition()

    @pyqtSlot(str, bool)
    def handleConnectionChanged(self, key: str, connected: bool):
        """Handles connectionChanged signal.
        
        Args:
            See StageManager.connectionChanged signal.
        """
        try:
            widget = self.frame.widgets[key]
        except KeyError:
            logger.exception("Connection changed key does not exist.")
        else:
            widget.setConnected(connected)

    @pyqtSlot(str, Exception)
    def handleClientError(self, key: str, _error: Exception):
        """Handles clientError signal.
        
        Args:
            See StageManager.clientError signal.
        """
        self.handleConnectionChanged(key, False)

    @pyqtSlot(str, float)
    def handlePositionReported(self, key: str, position_m: float):
        """Handles positionReported signal.
        
        Args:
            See StageManager.positionReported signal.
        """
        try:
            widget = self.frame.widgets[key]
        except KeyError:
            logger.exception("Position reported key does not exist.")
        else:
            widget.setPosition(position_m)

    def __del__(self):
        """Quits the thread before destructing."""
        self.thread.quit()

    def frames(self) -> Tuple[Tuple[str, StageControllerFrame]]:
        """Overridden."""
        return (("", self.frame),)
