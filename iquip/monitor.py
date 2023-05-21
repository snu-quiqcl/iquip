"""Module for monitoring devices."""

from typing import Any, TypeVar, Generic, Optional, Callable

from PyQt5.QtWidgets import QWidget


T = TypeVar("T")


class Monitor(Generic[T]):
    """A basic monitor class with a generic value type T.
    
    Monitors watch a single value, and notify any change of the value by calling
    a callback function.

    This class can be used as a concrete Monitor if the usage is simple enough
    and there is no need to implement self._read().
    
    In a Monitor object, there is two kinds of values: the public self.value()
    and the internal self._value.
    In most cases they will be the same, as self.value() returns self._value by default.
    However, for some reason, one might want to keep it different.
    In such cases, be aware of which kind of value you are using.
    """

    def __init__(
        self,
        updated_callback: Optional[Callable[[T], Any]] = None,
        initial_update: bool = True,
    ):
        """
        Args:
            updated_callback: A function which will be called when the value is updated.
            initial_update: Whether to update the value from the beginning.
              If True, it updates the value and always call the callback function.
              If False, it does not update the value, so the current value remains None.
        """
        self.updated_callback = updated_callback
        self._value = None
        if initial_update:
            self.update()

    def value(self) -> Optional[T]:
        """Returns the latest value or None if it is unknown or invalid."""
        return self._value

    def set_value(self, _value: Optional[T]):
        """Sets the current monitored value.
        
        This method will be called by the value source, to notify the value change.
        This will call the callback function.

        Args:
            _value: The new value, which should be the same kind of the internal self._value.
        """
        self._value = _value
        if self.updated_callback is not None:
            self.updated_callback(self.value())

    def update(self):
        """Updates the current value by actively reading the value.
        
        This could be helpful when the monitor is newly created and has no value yet,
        or the value source does not support reporting all the changes.
        """
        self.set_value(self._read())

    def _read(self) -> Optional[T]:
        """Actively reads the current value and returns it.
        
        Unless this is overriden, it just returns the latest value.
        
        The return value must be the same kind of the internal self._value,
        in case where self.value() differs from self._value.
        """
        return self._value


class TTLMonitorWidget(QWidget):
    """Single TTL channel monitor widget."""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
