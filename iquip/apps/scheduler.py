"""App module for showing the experiment list."""

from typing import Optional, Tuple, Literal, List, Callable

import time
import requests
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
from iquip.protocols import ExperimentInfo

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
        display_arguments: The list of arguments that is displayed.
        experimentInfo: The ExperimentInfo instance that holds the experiment information.
        argsLayout: The HBoxLayout for displaying the experiment information besides its name.
        nameLabel: The QLabel instance for displaying the experiment name.
    """
    display_arguments = ["rid", "due_date", "status"]

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.experimentInfo = None
        # widgets
        self.nameLabel = QLabel("None", self)
        # layout
        layout = QVBoxLayout(self)
        self.argsLayout = QHBoxLayout()
        layout.addWidget(self.nameLabel)
        layout.addLayout(self.argsLayout)

    def updateInfo(self, info: Optional[ExperimentInfo] = None):
        """Updates the information by modification.
        
        This updates SchedulerFrame.runningView when a new experiment starts to run.

        Args:
            info: The experiment information. None if there is no experiements running.
        """
        _dismiss_items(self.argsLayout)
        self.experimentInfo = info
        if info is not None:
            self.nameLabel.setText(info.name)
            for key, value in info.arginfo.items():
                if key in self.display_arguments:
                    self.argsLayout.addWidget(QLabel(f"{key}: {value}", self))
        else:
            self.nameLabel.setText("None")


class ExperimentView(QWidget):
    """Widget for displaying the information of the experiment.
    
    Attributes:
        display_arguments: The list of arguments that is displayed.
        nameLabel: The QLabel instance for displaying the experiment name.
    """
    display_arguments = ["rid", "priority", "due_date", "status"]

    def __init__(self, info: ExperimentInfo, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            info: The information of the experiment.
        """
        super().__init__(parent=parent)
        # widgets
        self.nameLabel = QLabel(info.name, self)
        labels = (QLabel(f"{key}: {value}", self)
                  for key, value in info.arginfo.items() if key in self.display_arguments)
        # layout
        layout = QHBoxLayout(self)
        layout.addWidget(self.nameLabel)
        for label in labels:
            layout.addWidget(label)


class ExperimentModel(QAbstractListModel):
    """Model for managing the data in the submitted experiment list.
    
    Attributes:
        experimentQueue: The list of ExperimentInfo of queued experiments.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.experimentQueue: List[ExperimentInfo] = []

    def rowCount(self, parent: Optional[QModelIndex] = QModelIndex()) -> int:  # pylint: disable=unused-argument
        """Overridden."""
        return len(self.experimentQueue)

    def data(self,
        index: QModelIndex,
        role: Optional[Qt.ItemDataRole] = Qt.DisplayRole  # pylint: disable=unused-argument
    ) -> ExperimentInfo:
        """Overridden."""
        try:
            return self.experimentQueue[index.row()]
        except IndexError:
            return None

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
        callback: Callable[[ExperimentInfo, None], List[ExperimentInfo]],
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
                response = requests.get("http://127.0.0.1:8000/experiment/queue/")
                response.raise_for_status()
                response = response.json()
            except requests.exceptions.RequestException as err:
                print(err)
                return
            runningExperiment = None
            experimentList = []
            for key, value in response.items():
                value["rid"] = key
                experimentInfo = ExperimentInfo("", value)
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
                            experimentList: List[ExperimentInfo],
                            runningExperiment: Optional[ExperimentInfo] = None,
        ):
        """Displays the experiments fetched from the uploaded queue in the proxy server.

        Args:
            experimentList: The queue of pending experiments.
            runningExperiment: The experiment running now. None if there is no experiements running.
        """
        self.schedulerFrame.model.experimentQueue = experimentList
        self.schedulerFrame.model.dataChanged.emit(self.schedulerFrame.model.index(0), # refresh
                                                   self.schedulerFrame.model.index(0),
                                                   [Qt.EditRole])
        self.schedulerFrame.model.experimentQueue.sort(key=lambda x: x.arginfo["priority"],
                                                       reverse=True)
        self._runExperiment(runningExperiment)

    def _runExperiment(self, info: Optional[ExperimentInfo] = None):
        """Sets the experiment onto 'currently running' section.

        Args:
            info: The experiment running now. None if there is no experiements running.
        """
        self.schedulerFrame.runningView.updateInfo(info)
        if info in self.schedulerFrame.model.experimentQueue:
            self.deleteExperiment(info)

    def _addExperiment(self, info: ExperimentInfo):
        """Adds the experiment to 'queued experiments' section.

        Args:
            info: The experiment to be added.
        """
        self.schedulerFrame.model.experimentQueue.append(info)
        self.schedulerFrame.model.experimentQueue.sort(key=lambda x: x.arginfo["priority"],
                                                       reverse=True)

    def _changeExperiment(self, index: int, info: Optional[ExperimentInfo] = None):
        """Changes the information of the particular experiment to given information.

        Args:
            index: The index of to-be-changed experiment.
            info: The experiment information. None for deletion.
        """
        if info is not None:
            self.schedulerFrame.model.experimentQueue[index] = info
            self.schedulerFrame.model.experimentQueue.sort(key=lambda x: x.arginfo["priority"],
                                                           reverse=True)
        else:
            self._deleteExperiment(self.schedulerFrame.model.experimentQueue[index])

    def _deleteExperiment(self, info: ExperimentInfo):
        """Deletes the experiment from 'queued experiments' section.

        Args:
            info: The experiment to be deleted.
        """
        self.schedulerFrame.model.experimentQueue.remove(info)

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)
