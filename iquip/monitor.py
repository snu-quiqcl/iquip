"""Module for monitoring devices."""

import enum
from typing import Any, TypeVar, Generic, Optional, Callable

from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout


T = TypeVar("T")


class Monitor(Generic[T]):
    """A basic monitor class with a generic value type T.
    
    Monitors watch a single value, and notify any change of the value by calling
    a callback function.

    This class can be used as a concrete Monitor if the usage is simple enough
    and there is no need to implement self._read().
    """

    def __init__(
        self,
        initial_value: T,
        updated_callback: Optional[Callable[[T], Any]] = None,
    ):
        """
        Args:
            initial_value: The initial value of self._value.
            updated_callback: A function which will be called when the value is updated.
        """
        self.updated_callback = updated_callback
        self._value = initial_value

    def value(self) -> T:
        """Returns the latest value."""
        return self._value

    def set_value(self, value: T):
        """Sets the current monitored value.
        
        This method will be called by the value source, to notify the value change.
        This will call the callback function.

        Args:
            value: The new value.
        """
        self._value = value
        if self.updated_callback is not None:
            self.updated_callback(value)

    def update(self):
        """Updates the current value by actively reading the value.
        
        This could be helpful when the monitor is newly created and has no value yet,
        or the value source does not support reporting all the changes.
        """
        self.set_value(self._read())

    def _read(self) -> T:
        """Actively reads the current value and returns it.
        
        Unless this is overriden, it just returns the latest value.
        """
        return self._value


class TTLMonitor(Monitor[Optional[bool]]):
    """Single TTL channel monitor.
    
    The possible states are: True (HIGH), False (LOW) or None (UNKNOWN).
    """


class TTLMonitorWidget(QWidget):
    """Single TTL channel monitor widget."""

    def __init__(self, monitor: TTLMonitor, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.monitor = monitor
        self.monitor.updated_callback = self._setValue
        # widgets
        self.stateLabel = QLabel("-")
        # layout
        layout = QHBoxLayout(self)
        layout.addWidget(self.stateLabel)

    def _setValue(self, value: Optional[bool]):
        """Sets the current value on the label.

        This method is internal since it is intended to be called only by the monitor callback.
        
        Args:
            value: True, False or None.
        """
        if value is None:
            text = "--"
        elif value:
            text = "HIGH"
        else:
            text = "LOW"
        self.stateLabel.setText(text)
