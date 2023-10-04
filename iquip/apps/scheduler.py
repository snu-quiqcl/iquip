"""App module for showing the scheduled queue for experiments."""

import enum
from typing import Any, Optional, Tuple

from PyQt5.QtCore import QAbstractTableModel, QModelIndex, QObject, Qt, QVariant
from PyQt5.QtWidgets import QTableView, QVBoxLayout, QWidget

import qiwis
from iquip.protocols import SubmittedExperimentInfo

class ScheduleModel(QAbstractTableModel):
    """Model for handling the scheduled queue as a table data.
    
    Attributes:
        scheduleList: The list with submitted experiment information.
    """

    class InfoFieldId(enum.IntEnum):
        """Submitted experiment information field id.
        
        Since the int value is used for the column index, it must increase by 1, starting from 0.
        """
        RID = 0
        STATUS = 1
        PRIORITY = 2
        PIPELINE = 3
        DUE_DATE = 4
        FILE = 5
        CONTENT = 6
        ARGUMENTS = 7

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

    def rowCount(
        self,
        parent: QModelIndex = QModelIndex()  # pylint: disable=unused-argument
    ) -> int:
        """Overridden."""
        return len(self.scheduleList)
    
    def columnCount(
        self,
        parent: QModelIndex = QModelIndex()  # pylint: disable=unused-argument
    ) -> int:
        """Overridden."""
        return len(ScheduleModel.InfoFieldId)
    
    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole) -> Any:
        """Overridden."""
        if not index.isValid():
            return QVariant()
        if role == Qt.DisplayRole:
            row, column = index.row(), index.column()
            infoField = ScheduleModel.InfoFieldId(column).name.lower()
            return getattr(self.scheduleList[row], infoField)
        else:
            return QVariant()


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
