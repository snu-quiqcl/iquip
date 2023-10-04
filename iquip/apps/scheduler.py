"""App module for showing the scheduled queue for experiments."""

from typing import Optional, Tuple

from PyQt5.QtCore import QObject
from PyQt5.QtWidgets import QTableView, QVBoxLayout, QWidget

import qiwis

class SchedulerFrame(QWidget):
    """Frame for showing the scheduled queue."""

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.scheduleView = QTableView(self)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.scheduleView)


class SchedulerApp(qiwis.BaseApp):
    """App for fetching and showing the scheduled queue.

    Attributes:
        schedulerFrame: The frame that shows the scheduled queue.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.schedulerFrame = SchedulerFrame()

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)
