"""Module for monitoring devices."""

from typing import Any, TypeVar, Generic, Optional, Callable


T = TypeVar("T")


class Monitor(Generic[T]):
    """An interface for a monitor.
    
    Monitors watch a single value, and notify any change of the value by calling
      a callback function.
    """

    def __init__(self, updated_callback: Optional[Callable[[T], Any]] = None):
        """
        Args:
            updated_callback: A function which will be called when the value is updated.
        """
        self.updated_callback = updated_callback
        self._value = None

    def value(self) -> Optional[T]:
        """Returns the latest value or None if it is unknown or invalid."""
        return self._value

    def update(self, callback: bool = True) -> Optional[T]:
        """Returns the current value or None if it is unknown or invalid.
        
        This method will actively read the value and update the current value if it is changed.
        It could be helpful when the monitor is newly created and has no value yet,
        or the value source does not support reporting all the changes.

        Args:
            callback: Whether to call updated_callback, with the updated value.
              If updated_callback is None, it is ignored.
        """
        return None
