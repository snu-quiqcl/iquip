"""Module for oven controller."""

import logging
from typing import Any, List, Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QVBoxLayout, QWidget

import qiwis

logger = logging.getLogger(__name__)

class OvenControllerFrame(QWidget):
    """Frame for OvenControllerApp."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent=parent)
        layout = QVBoxLayout(self)


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
