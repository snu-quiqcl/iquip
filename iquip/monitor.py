"""Module for monitoring devices."""

from typing import Any, TypeVar, Generic, Optional, Callable

from PyQt5.QtWidgets import QWidget, QLabel, QHBoxLayout
from PyQt5.QtCore import pyqtSignal

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

    def get_value(self) -> T:
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


class TTLMonitorWidget(QWidget):
    """Single TTL channel monitor widget.

    Signals:
        valueUpdated: Emitted when the monitor value is updated. The argument is
          True, False or None.
    
    Attributes:
        monitor: A TTL monitor object, whose values are True, False or None, which
          represent HIGH, LOW or UNDEFINED, respectively.
          Its updated_callback function is _setValue method of this TTLMonitorWidget instance,
          which implies that only the monitor can change the widget value state.
        stateLabel: A QLabel object which represents the current monitor value.
          See _setValue() for the exact text for each state.
    """

    valueUpdated = pyqtSignal(object)

    def __init__(self, monitor: Monitor[Optional[bool]], parent: Optional[QWidget] = None):
        """Extended.

        Based on the current value of monitor, stateLabel text will be initialized.

        Args:
            monitor: A Monitor object whose value will be displayed on the widget.
        """
        super().__init__(parent=parent)
        self.monitor = monitor
        self.monitor.updated_callback = self._updateValue
        # widgets
        self.stateLabel = QLabel("--", self)
        self._setTextWith(monitor.get_value())
        # layout
        layout = QHBoxLayout(self)
        layout.addWidget(self.stateLabel)

    def _setTextWith(self, value: Optional[bool]):
        """Sets the current text on the label with value.

        This does not emit any signal.

        Args:
            value: TTL state value.
        """
        if value is None:
            text = "--"
        elif value:
            text = "HIGH"
        else:
            text = "LOW"
        self.stateLabel.setText(text)

    def _updateValue(self, value: Optional[bool]):
        """Updates the current value on the label and emits the signal.

        This method is internal since it is intended to be called only by the monitor callback.
        It changes the label text based on the value.
        
        Args:
            value: TTL state value which is passed by the monitor.
        """
        self._setTextWith(value)
        self.valueUpdated.emit(value)
