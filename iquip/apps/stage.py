"""Module for stage controller."""

import functools
import logging
from typing import Callable, Dict, Optional, Tuple

from sipyco.pc_rpc import Client
from PyQt5.QtCore import QObject, Qt, pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)

RPCTargetInfo = Tuple[str, int, str]  # ip, port, target_name

def use_client(function: Callable[..., None]) -> Callable[..., None]:
    """Decorator which substitutes a string key to a client object.

    If the key does not exist, function is not called at all.
    If an OSError occurs while running function, the RPC client is closed and
        removed from the client dictionary. 
    
    Args:
        function: Decorated function. It should take a Client object as the
            first argument.
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
            return
        try:
            function(self, client, *args, **kwargs)
        except OSError:
            logger.exception("Error occurred while running %s with client %s.", function, key)
            client.close_rpc()
            self._clients.pop(key)  # pylint: disable=protected-access
    return wrapped

class StageManager(QObject):
    """Manages the stage RPC clients which live in a dedicated thread.
    
    An instance of this class should be moved to a thread other than the main
      GUI thread to prevent GUI from freezing.
    Therefore, the private methods must not be called from the main thread.
    Instead, use signals to communicate.

    Signals:
        See _signal() method for each signal.
    """

    clear = pyqtSignal()
    closeTarget = pyqtSignal(str)
    connectTarget = pyqtSignal(str, tuple)
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
        for client in self._clients.values():
            client.close_rpc()
        self._clients.clear()

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
            client.close_rpc()
        self._clients[key] = Client(*info)

    @pyqtSlot(str, float)
    @use_client
    def _moveBy(self, client: Client, displacement_m: float):
        """Moves the stage by given displacement.
        
        Args:
            client: Client object.
            displacement_m: Relative move displacement in meters.
        """
        client.move_by(displacement_m)

    @pyqtSlot(str, float)
    @use_client
    def _moveTo(self, client: Client, position_m: float):
        """Moves the stage to given position.
        
        Args:
            client: Client object.
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
