"""App module for showing the schedule for experiments."""

import enum
import functools
import logging
from typing import Any, Optional, Sequence, Tuple

import requests
from PyQt5.QtCore import (
    pyqtSignal, pyqtSlot, QAbstractTableModel, QModelIndex, QObject, Qt, QThread, QVariant
)
from PyQt5.QtGui import QGuiApplication
from PyQt5.QtWidgets import QAction, QPushButton, QTableView, QVBoxLayout, QWidget

import qiwis
from iquip.protocols import SubmittedExperimentInfo

logger = logging.getLogger(__name__)

class DeleteType(enum.Enum):
    """Experiment deletion type."""
    DELETE = "delete"
    TERMINTATE = "terminate"


class _ScheduleFetcherThread(QThread):
    """QThread for fetching the current schedule from the proxy server.
    
    Signals:
        fetched(schedule): The current schedule is fetched.
          The "schedule" is a list with SubmittedExperimentInfo elements.

    Attributes:
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(list)

    def __init__(
        self,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Fetches the current schedule from the proxy server.

        After finished, the fetched signal is emitted.
        """
        params = {"timestamp": -1, "timeout": 10}
        while True:
            try:
                response = requests.get(f"http://{self.ip}:{self.port}/schedule/",
                                        params=params,
                                        timeout=12)
                response.raise_for_status()
                response = response.json()
            except requests.exceptions.RequestException:
                logger.exception("Failed to fetch the current schedule.")
                return
            timestamp, ridInfos = response
            schedule = []
            for rid, info in ridInfos.items():
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
            self.fetched.emit(schedule)
            params["timestamp"] = timestamp


class _DeleteExperimentThread(QThread):
    """QThread for deleting the target experiment through the proxy server.
    
    Attributes:
        rid: The run identifier value of the target executed experiment.
        deleteType: The deletion type to execute.
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    def __init__(
        self,
        rid: int,
        deleteType: DeleteType,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            See the attributes section.
        """
        super().__init__(parent=parent)
        self.rid = rid
        self.deleteType = deleteType
        self.ip = ip
        self.port = port

    def run(self):
        """Overridden.
        
        Requests the proxy server to delete the target experiment.
        """
        params = {"rid": self.rid}
        try:
            response = requests.post(
                f"http://{self.ip}:{self.port}/experiment/{self.deleteType.value}/",
                params=params,
                timeout=10
            )
            response.raise_for_status()
        except requests.exceptions.RequestException:
            logger.exception("Failed to delete the target experiment.")
            return
        logger.info("Delete the experiment with RID %d.", self.rid)


class ScheduleModel(QAbstractTableModel):
    """Model for handling the schedule as a table data."""

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
        self._schedule: Sequence[SubmittedExperimentInfo] = ()

    def rowCount(
        self,
        parent: QModelIndex = QModelIndex()  # pylint: disable=unused-argument
    ) -> int:
        """Overridden."""
        return len(self._schedule)

    def columnCount(
        self,
        parent: QModelIndex = QModelIndex()  # pylint: disable=unused-argument
    ) -> int:
        """Overridden."""
        return len(ScheduleModel.InfoFieldId)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole = Qt.DisplayRole) -> Any:
        """Overridden.

        Returns:
            DisplayRole: Column-th info field of row-th experiment in the schedule.
        """
        if not index.isValid() or role != Qt.DisplayRole:
            return QVariant()
        row, column = index.row(), index.column()
        infoField = ScheduleModel.InfoFieldId(column).name.lower()
        data = getattr(self._schedule[row], infoField)
        if column == ScheduleModel.InfoFieldId.ARGUMENTS:
            return ", ".join([
                f"{key}: {round(value, 9) if isinstance(value, (int, float)) else value}"
                for key, value in data.items()
            ])
        return data

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

    def setSchedule(self, value: Sequence[SubmittedExperimentInfo]):
        """Sets the schedule to the value.
        
        Args:
            value: A new schedule value.
        """
        self.beginResetModel()
        self._schedule = value
        self.endResetModel()

    def experimentInfo(self, idx: int) -> str:
        """Returns the specific experiment info.
        
        Args:
            idx: The index of the experiment.

        Returns:
            The experiment info in string or an empty string if the idx is invalid.
        """
        if idx < 0 or idx >= len(self._schedule):
            return ""
        return str(self._schedule[idx])


class SchedulerFrame(QWidget):
    """Frame for showing the schedule.
    
    Attributes:
        scheduleView: The table view for showing the schedule.
        scheduleModel: The model for handling the schedule.
        button: The button for restarting to fetch schedules. When the button is clicked,
          it is disabled. It will be enabled once a thread fetching schedules is finished.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.scheduleView = QTableView(self)
        self.scheduleModel = ScheduleModel(self)
        self.scheduleView.setModel(self.scheduleModel)
        self.scheduleView.setContextMenuPolicy(Qt.ActionsContextMenu)
        self.button = QPushButton("Restart", self)
        self.button.setEnabled(False)
        # layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.scheduleView)
        layout.addWidget(self.button)


class SchedulerApp(qiwis.BaseApp):
    """App for fetching and showing the schedule.

    Attributes:
        proxy_id: The proxy server IP address.
        proxy_port: The proxy server PORT number.
        scheduleFetcherThread: The most recently executed _ScheduleFetcherThread instance.
        deleteExperimentThread: The most recently executed _DeleteExperimentThread instance.
        schedulerFrame: The frame that shows the schedule.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        self.proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.scheduleFetcherThread: Optional[_ScheduleFetcherThread] = None
        self.deleteExperimentThread: Optional[_DeleteExperimentThread] = None
        self.schedulerFrame = SchedulerFrame()
        # signal connection
        button = self.schedulerFrame.button
        button.clicked.connect(functools.partial(button.setEnabled, False))
        button.clicked.connect(self.startScheduleFetcherThread)
        self.setCopyAction()
        self.setDeleteActions()
        self.startScheduleFetcherThread()

    def setCopyAction(self):
        """Sets a copy action in schedulerFrame.scheduleView."""
        view = self.schedulerFrame.scheduleView
        action = QAction("Copy", view)
        action.triggered.connect(self.copyExperimentInfo)
        view.addAction(action)

    @pyqtSlot()
    def copyExperimentInfo(self):
        """Copies the selected experiment info to the system clipboard."""
        index = self.schedulerFrame.scheduleView.currentIndex()
        if not index.isValid():
            return
        row = index.row()

    def setDeleteActions(self):
        """Sets experiment deletion actions in schedulerFrame.scheduleView."""
        view = self.schedulerFrame.scheduleView
        for deleteType in DeleteType:
            action = QAction(deleteType.value.capitalize(), view)
            action.triggered.connect(functools.partial(self.deleteExperiment, deleteType))
            view.addAction(action)

    @pyqtSlot(DeleteType)
    def deleteExperiment(self, deleteType: DeleteType):
        """Deletes the selected experiment through _DeleteExperimentThread.
        
        Args:
            See _DeleteExperimentThread attributes section.
        """
        index = self.schedulerFrame.scheduleView.currentIndex()
        if not index.isValid():
            return
        row = index.row()
        model = self.schedulerFrame.scheduleModel
        ridIndex = model.index(row, 0)
        rid = model.data(ridIndex)
        self.deleteExperimentThread = _DeleteExperimentThread(
            rid,
            deleteType,
            self.proxy_ip,
            self.proxy_port
        )
        self.deleteExperimentThread.finished.connect(self.deleteExperimentThread.deleteLater)
        self.deleteExperimentThread.start()

    @pyqtSlot(list)
    def updateScheduleModel(self, schedule: Sequence[SubmittedExperimentInfo]):
        """Updates schedulerFrame.scheduleModel using the given schedule.
        
        Args:
            See _ScheduleFetcherThread signals section.
        """
        self.schedulerFrame.scheduleModel.setSchedule(schedule)

    def startScheduleFetcherThread(self):
        """Creates and starts a new _ScheduleFetcherThread instance."""
        self.scheduleFetcherThread = _ScheduleFetcherThread(self.proxy_ip, self.proxy_port)
        self.scheduleFetcherThread.fetched.connect(self.updateScheduleModel,
                                                   type=Qt.QueuedConnection)
        self.scheduleFetcherThread.finished.connect(
            functools.partial(self.schedulerFrame.button.setEnabled, True),
            type=Qt.QueuedConnection,
        )
        self.scheduleFetcherThread.finished.connect(self.scheduleFetcherThread.deleteLater)
        self.scheduleFetcherThread.start()

    def frames(self) -> Tuple[Tuple[str, SchedulerFrame]]:
        """Overridden."""
        return (("", self.schedulerFrame),)
