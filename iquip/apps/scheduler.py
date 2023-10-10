"""App module for showing the scheduled queue for experiments."""

import enum
import logging
from typing import Any, Callable, Iterable, Optional, Tuple

import requests
from PyQt5.QtCore import (
    pyqtSignal, pyqtSlot, QAbstractTableModel, QModelIndex, QObject, Qt, QThread, QVariant
)
from PyQt5.QtWidgets import QTableView, QVBoxLayout, QWidget

import qiwis
from iquip.protocols import SubmittedExperimentInfo

logger = logging.getLogger(__name__)


class _ScheduleThread(QThread):
    """QThread for obtaining the current scheduled queue from the proxy server.
    
    Signals:
        fetched(isChanged, updatedTime, schedule): The current scheduled queue is fetched.
          The "schedule" is a list with SubmittedExperimentInfo elements.
          The "updatedTime" is the time when the fetched schedule was updated.
          If a timeout occurs, i.e. the queue is not changed, the "isChanged" is set to False.

    Attributes:
        ip: The proxy server IP address.
        port: The proxy server PORT number.
        updatedTime: The last updated time, in the format of time.time().
    """

    fetched = pyqtSignal(bool, float, list)

    def __init__(
        self,
        ip: str,
        port: int,
        updatedTime: Optional[float],
        callback: Callable[[bool, float, Iterable[SubmittedExperimentInfo]], None],
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            ip, port, updatedTime: See the attributes section.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.ip = ip
        self.port = port
        self.updatedTime = updatedTime
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.
        
        Fetches the current scheduled queue from the proxy server.

        After finished, the fetched signal is emitted.
        """
        params = {"updated_time": self.updatedTime}
        try:
            response = requests.get(f"http://{self.ip}:{self.port}/experiment/queue/",
                                    params=params,
                                    timeout=10)
            response.raise_for_status()
            response = response.json()
        except requests.exceptions.Timeout:
            self.fetched.emit(False, self.updatedTime, [])
            return
        except requests.exceptions.RequestException:
            logger.exception("Failed to fetch the current scheduled queue.")
            return
        updatedTime, queue = response["updated_time"], response["queue"]
        schedule = []
        for rid, info in queue.items():
            expid = info["expid"]
            schedule.append(SubmittedExperimentInfo(
                rid=int(rid),
                status=info["status"],
                priority=info["priority"],
                pipeline=info["pipeline"],
                due_date=info["due_date"],
                file=expid.get("file", None),
                content=expid.get("content", None),
                arguments=expid["arguments"]
            ))
        self.fetched.emit(True, updatedTime, schedule)


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
                file=None, content="import numpy as np\nprint('Hello')", arguments={}
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
        """Overridden.

        Returns:
            DisplayRole: Column-th info field of row-th experiment in scheduleList.
        """
        if not index.isValid() or role != Qt.DisplayRole:
            return QVariant()
        row, column = index.row(), index.column()
        infoField = ScheduleModel.InfoFieldId(column).name.lower()
        return getattr(self.scheduleList[row], infoField)

    def headerData(self, section: int, orientation: Qt.Orientation, role: Qt.ItemDataRole) -> Any:
        """Overridden.
        
        Returns:
            Horizontal: The corresponding SubmittedExperimentInfo field.
            Vertical: The index started from 1.
        """
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            return ScheduleModel.InfoFieldId(section).name.capitalize()
        return section + 1


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
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        schedulerFrame: The frame that shows the scheduled queue.
        scheduleThread: The most recently executed _ScheduleThread instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.scheduleThread: Optional[_ScheduleThread] = None
        self.schedulerFrame = SchedulerFrame()
        self.startScheduleThread()

    @pyqtSlot(bool, float, list)
    def updateScheduleModel(
        self,
        isChanged: bool,
        updatedTime: float,
        schedule: Iterable[SubmittedExperimentInfo]
    ):
        """Updates schedulerFrame.scheduleModel using the given schedule.
        
        Args:
            See _ScheduleThread signals section.
        """
        if isChanged:
            model = self.schedulerFrame.scheduleModel
            model.beginResetModel()
            model.scheduleList = schedule
            model.endResetModel()
        self.startScheduleThread(updatedTime)

    def startScheduleThread(self, updatedTime: Optional[float] = None):
        """Creates and starts a new _ScheduleThread instance.
        
        Args:
            See _ScheduleThread attributes section.
        """
        self.scheduleThread = _ScheduleThread(
            self.proxy_ip,
            self.proxy_port,
            updatedTime,
            self.updateScheduleModel
        )
        self.scheduleThread.start()

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)
