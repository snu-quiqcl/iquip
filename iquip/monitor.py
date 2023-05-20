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

    def value(self) -> Optional[T]:
        """Returns the latest value or None if it is unknown or invalid."""
        return None
