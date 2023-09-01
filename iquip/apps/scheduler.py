"""App module for showing the experiment list."""

from typing import Optional, Tuple, Literal, List, Callable

import requests
import logging
from PyQt5.QtGui import QPainter
from PyQt5.QtCore import (
    Qt, QObject, QThread, pyqtSignal,
    QAbstractListModel, QModelIndex, QMimeData, QSize
)
from PyQt5.QtWidgets import (
    QStyleOptionViewItem, QWidget, QLayout, QLabel, QListView,
    QHBoxLayout, QVBoxLayout, QAbstractItemDelegate, QAction
)

import qiwis
from iquip.protocols import SubmittedExperimentInfo

logger = logging.getLogger(__name__)


def _dismiss_items(layout: Optional[QLayout] = None):
    """Decouples components in the layout.

    Args:
        layout: The layout whose elements are intended to be deleted.
    """
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
                layout.removeWidget(widget)
                widget.deleteLater()
            else:
                _dismiss_items(item.layout())


class SchedulerFrame(QWidget):
    """Frame for displaying the submitted experiment list.
    
    Attributes:
        runningView: The RunningExperimentView widget displaying currently running experiment.
        queueView: The QListView widget holding queued experiments.
        model: The ExperimentModel that manages the data of queueView.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.runningView = RunningExperimentView()
        self.queueView = QListView()
        self.queueView.setItemDelegate(ExperimentDelegate(self.queueView))
        self.queueView.setMovement(QListView.Free)
        self.queueView.setObjectName("Queued Experiments")
        self.model = ExperimentModel()
        self.queueView.setModel(self.model)
        # layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.addWidget(QLabel("Currently running:", self))
        layout.addWidget(self.runningView)
        layout.addWidget(QLabel("Queued experiments:", self))
        layout.addWidget(self.queueView)


class RunningExperimentView(QWidget):
    """Widget for displaying the information of the experiment, especially for the one running.
    
    Attributes:
        experimentInfo: The SubmittedExperimentInfo instance that holds the experiment information.
        argsLayout: The HBoxLayout for displaying the experiment information.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.experimentInfo = None
        # layout
        layout = QVBoxLayout(self)
        self.argsLayout = QHBoxLayout()
        layout.addLayout(self.argsLayout)

    def updateInfo(self, info: Optional[SubmittedExperimentInfo] = None):
        """Updates the information by modification.
        
        This updates SchedulerFrame.runningView when a new experiment starts to run.

        Args:
            info: The experiment information. None if there is no experiements running.
        """
        _dismiss_items(self.argsLayout)
        self.experimentInfo = info
        if info is not None:
            for key, value in info.items():
                if key != "priority":
                    self.argsLayout.addWidget(QLabel(f"{key}: {value}", self))
        else:
            self.argsLayout.addWidget(QLabel("None", self))


class ExperimentView(QWidget):
    """Widget for displaying the information of the experiment."""

    def __init__(self, info: SubmittedExperimentInfo, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            info: The information of the experiment.
        """
        super().__init__(parent=parent)
        # widgets
        labels = tuple(QLabel(f"{key}: {value}", self) for key, value in info.items())
        # layout
        layout = QHBoxLayout(self)
        for label in labels:
            layout.addWidget(label)


class ExperimentModel(QAbstractListModel):
    """Model for managing the data in the submitted experiment list.
    
    Attributes:
        experimentQueue: The list of SubmittedExperimentInfo of queued experiments.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.experimentQueue: List[SubmittedExperimentInfo] = []

    def rowCount(self, parent: Optional[QModelIndex] = QModelIndex()) -> int:  # pylint: disable=unused-argument
        """Overridden."""
        return len(self.experimentQueue)

    def data(self,
        index: QModelIndex,
        role: Optional[Qt.ItemDataRole] = Qt.DisplayRole  # pylint: disable=unused-argument
    ) -> SubmittedExperimentInfo:
        """Overridden."""
        try:
            return self.experimentQueue[index.row()]
        except IndexError:
            return None

    def sort(self):
        """Sorts the experiments by priority value."""
        self.schedulerFrame.model.experimentQueue.sort(key=lambda x: x.priority, reverse=True)

    def supportedDropActions(self) -> int:
        """Overridden."""
        return Qt.CopyAction | Qt.MoveAction

    def mimeData(self, index: QModelIndex) -> QMimeData:
        """Overridden.

        Fetches the index of the selected element.
        
        Args:
            index: The ModelIndex instance containing 
              row, column, and etc. values of the selected element.
        
        Returns:
            A QMimeData instance that holds str value of the index.
        """
        mime = super().mimeData(index)
        mime.setText(str(index[0].row()))
        return mime

    def dropMimeData(self,  # pylint: disable=too-many-arguments
        mimedata: QMimeData,
        action: QAction,
        row: int,
        column: int,  # pylint: disable=unused-argument
        parentIndex: QModelIndex  # pylint: disable=unused-argument
    ) -> Literal[True]:
        """Overridden."""
        idx = int(mimedata.text())
        if action == Qt.IgnoreAction:
            return True
        if row < 0:
            row = self.rowCount()
        if (self.experimentQueue[idx].arginfo["priority"]
            != self.experimentQueue[min(row, self.rowCount() - 1)].arginfo["priority"]):
            return True
        if idx != row:
            item = self.experimentQueue.pop(idx)
            self.experimentQueue.insert((row - 1) if idx < row else row, item)

        # TODO(giwon2004): emit signal for change of priority through artiq-proxy.
        return True

    def flags(self, index: QModelIndex) -> int:
        """Overridden."""
        defaultFlags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.isValid():
            return Qt.ItemIsEditable | Qt.ItemIsDragEnabled | defaultFlags
        return Qt.ItemIsDropEnabled | defaultFlags


class ExperimentDelegate(QAbstractItemDelegate):
    """Delegate for displaying the layout of each data in the experiment list.

    TODO(giwon2004): Enabling buttons when displayed using QAbstractDelegate.
    """

    def paint(self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex):
        """Overridden."""
        data = index.data(Qt.DisplayRole)
        if data is None:
            return
        experimentView = ExperimentView(data)
        experimentView.resize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        experimentView.render(painter)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:  # pylint: disable=unused-argument
        """Overridden."""
        data = index.data(Qt.DisplayRole)
        if data is None:
            return QSize(0, 0)
        experimentView = ExperimentView(data)
        return experimentView.sizeHint()


class _ExperimentQueueFetcherThread(QThread):
    """QThread for fetching the queued experiments from the proxy server.

    Signals:
        fetched(experimentList, runningExperiment):
          The experiment queue and currently running experiment are fetched.
    """

    fetched = pyqtSignal(list, object)

    def __init__(
        self,
        callback: Callable[[SubmittedExperimentInfo, None], List[SubmittedExperimentInfo]],
        parent: Optional[QObject] = None
    ):
        """Extended.

        Args:
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.

        Fetches the experiment list as a dictionary from the proxy server,
        and emits a list and an ExperimentInfo instance for display.
        """
        while True:
            try:
                response = requests.get("http://127.0.0.1:8000/experiment/queue/", timeout=10)
                response.raise_for_status()
                response = response.json()
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException as err:
                logger.exception("Failed to fetch the experiment queue.")
                return
            runningExperiment = None
            experimentList = []
            for key, value in response.items():
                experimentInfo = SubmittedExperimentInfo(rid=int(key))
                for item in tuple(item for item, _ in experimentInfo.items()):
                    setattr(experimentInfo, item, value[item])
                if value["status"] in ["running", "run_done", "analyzing", "deleting"]:
                    runningExperiment = experimentInfo
                    continue
                experimentList.append(experimentInfo)
            self.fetched.emit(experimentList, runningExperiment)


class SchedulerApp(qiwis.BaseApp):
    """App for displaying the submitted experiment queue.

    Attributes:
        schedulerFrame: The frame that shows the submitted experiment queue.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.schedulerFrame = SchedulerFrame()
        self.thread = _ExperimentQueueFetcherThread(
            self._snycExperimentQueue,
            self
        )
        self.thread.start()

    def _snycExperimentQueue(self,
                             experimentList: List[SubmittedExperimentInfo],
                             runningExperiment: Optional[SubmittedExperimentInfo] = None,
        ):
        """Displays the experiments fetched from the uploaded queue in the proxy server.

        Args:
            experimentList: The queue of pending experiments.
            runningExperiment: The experiment running now. None if there is no experiements running.
        """
        self.schedulerFrame.model.experimentQueue = experimentList
        self.schedulerFrame.model.dataChanged.emit(self.schedulerFrame.model.index(0),  # refresh
                                                   self.schedulerFrame.model.index(0),
                                                   [Qt.EditRole])
        self.schedulerFrame.model.sort()
        self._runExperiment(runningExperiment)

    def _runExperiment(self, info: Optional[SubmittedExperimentInfo] = None):
        """Sets the experiment onto 'currently running' section.

        Args:
            info: The experiment running now. None if there is no experiements running.
        """
        self.schedulerFrame.runningView.updateInfo(info)
        if info in self.schedulerFrame.model.experimentQueue:
            self.deleteExperiment(info)

    def _addExperiment(self, info: SubmittedExperimentInfo):
        """Adds the experiment to 'queued experiments' section.

        Args:
            info: The experiment to be added.
        """
        self.schedulerFrame.model.experimentQueue.append(info)
        self.schedulerFrame.model.sort()

    def _changeExperiment(self, index: int, info: Optional[SubmittedExperimentInfo] = None):
        """Changes the information of the particular experiment to given information.

        Args:
            index: The index of to-be-changed experiment.
            info: The experiment information. None for deletion.
        """
        if info is not None:
            self.schedulerFrame.model.experimentQueue[index] = info
            self.schedulerFrame.model.sort()
        else:
            self._deleteExperiment(self.schedulerFrame.model.experimentQueue[index])

    def _deleteExperiment(self, info: SubmittedExperimentInfo):
        """Deletes the experiment from 'queued experiments' section.

        Args:
            info: The experiment to be deleted.
        """
        self.schedulerFrame.model.experimentQueue.remove(info)

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)
