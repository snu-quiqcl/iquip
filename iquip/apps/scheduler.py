"""App module for showing the scheduled queue for experiments."""

from typing import Optional

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QWidget

import qiwis

class SchedulerFrame(QWidget):
    """Frame for showing the scheduled queue."""


class SchedulerApp(qiwis.BaseApp):
    """App for fetching and showing the scheduled queue.

    Attributes:
        schedulerFrame: The frame that shows the scheduled queue.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.schedulerFrame = SchedulerFrame()
