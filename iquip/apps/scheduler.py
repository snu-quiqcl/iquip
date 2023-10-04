"""App module for showing the scheduled queue for experiments."""

from typing import Optional, Tuple

from PyQt5.QtCore import QAbstractTableModel, QObject
from PyQt5.QtWidgets import QTableView, QVBoxLayout, QWidget

import qiwis
from iquip.protocols import SubmittedExperimentInfo

class ScheduleModel(QAbstractTableModel):
    """Model for handling the scheduled queue as a table data.
    
    Attributes:
        scheduleList: The list with submitted experiment information.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # TODO(BECATRUE): It is a temporary schedule list. (#182)
        self.scheduleList = [
            SubmittedExperimentInfo(
                rid=0, status="running", priority=0, pipeline="main", due_date=None,
                file="experiment1.py", content=None, arguments={"arg1": 10, "arg2": "value2"}
            ),
            SubmittedExperimentInfo(
                rid=1, status="preparing", priority=0, pipeline="main", due_date=None,
                file=None, content="blah blah", arguments={}
            )
        ]


class SchedulerFrame(QWidget):
    """Frame for showing the scheduled queue.
    
    Attributes:
        scheduleView: The table view for showing the scheduled queue.
        scheduleModel: The model for handling the scheduled queue.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.scheduleView = QTableView(self)
        self.scheduleModel = ScheduleModel(self)
        self.scheduleView.setModel(self.scheduleModel)
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
