"""App module for showing the experiment list."""

from typing import Optional, Tuple, Literal, List, Callable

import logging
import dataclasses
import requests
from PyQt5.QtGui import QPainter, QMouseEvent
from PyQt5.QtCore import (
    Qt, QObject, QAbstractListModel, QModelIndex, QMimeData, QSize,
    QEvent, pyqtSignal, pyqtSlot, QThread
)
from PyQt5.QtWidgets import (
    QStyleOptionViewItem, QWidget, QLayout, QLabel, QListView,
    QHBoxLayout, QVBoxLayout, QAbstractItemDelegate, QAction, QMenu
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


def _thread_with_worker(worker: QObject, parent: Optional[QObject] = None) -> QThread:
    """Returns a new thread with given worker.

    Args:
        worker: The worker that must be run through another thread. It must have:
          - worker.run: the main function that has to be run.
          - worker.done: the signal that is emitted when the work is done.
        parent: The object that the thread lives in.
    """
    thread = QThread(parent=parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.done.connect(thread.quit)
    worker.done.connect(worker.deleteLater)
    thread.finished.connect(thread.deleteLater)
    return thread


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
        self.queueView = ExperimentListView()
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


class ExperimentListView(QListView):
    """Customized QListView class to detect right-click input.

    This list view contains the running experiments.
    
    Signals:
        rightButtonPressed(mouseEvent): The information of the click input is sent.
    """
    rightButtonPressed = pyqtSignal(QMouseEvent)

    def mousePressEvent(self, event: QMouseEvent):
        """Overridden."""
        if event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
            self.rightButtonPressed.emit(event)
        super().mousePressEvent(event)  # hand the signal to drag & drop


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
        self.schedulerFrame.model.experimentQueue.sort(key=lambda x: (-x.priority, x.rid))

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
        if (self.experimentQueue[idx].priority
            != self.experimentQueue[min(row, self.rowCount() - 1)].priority):
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
    """Delegates for displaying the layout of each data in the experiment list."""

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

    Attributes:
        ip: The proxy server IP address.
        port: The proxy server PORT number.
    """

    fetched = pyqtSignal(list, object)

    def __init__(
        self,
        ip: str,
        port: int,
        callback: Callable[[SubmittedExperimentInfo, None], List[SubmittedExperimentInfo]],
        parent: Optional[QObject] = None
    ):
        """Extended.

        Args:
            ip, port: See the attributes section.
            callback: The callback method called after this thread is finished.
        """
        super().__init__(parent=parent)
        self.ip = ip
        self.port = port
        self.fetched.connect(callback, type=Qt.QueuedConnection)

    def run(self):
        """Overridden.

        Fetches the experiment list as a dictionary from the proxy server,
          and emits a list and an ExperimentInfo instance for display.
        """
        while True:
            try:
                response = requests.get(
                    f"http://{self.ip}:{self.port}/experiment/queue/", timeout=10
                )
                response.raise_for_status()
                response = response.json()
            except requests.exceptions.Timeout:
                continue
            except requests.exceptions.RequestException:
                logger.exception("Failed to fetch the experiment queue.")
                return
            runningExperiment = None
            experimentList = []
            for key, value in response.items():
                experimentInfo = SubmittedExperimentInfo(rid=int(key))
                for item in dataclasses.fields(experimentInfo):
                    setattr(experimentInfo, item.name, value[item.name])
                if value["status"] in ["running", "run_done"]:
                    runningExperiment = experimentInfo
                    continue
                experimentList.append(experimentInfo)
            self.fetched.emit(experimentList, runningExperiment)


class SchedulerPostWorker(QObject):
    """Worker for posting a request to the proxy server, targeting the scheduler.

    Signals:
        done: The signal is emitted when the procedure of the worker is done.

    Attributes:
        ip: The proxy server IP address.
        port: The proxy server PORT number.
        mode: The type of command that is requested to the server.
        rid: The run identifier value of the target experiment.
    """
    done = pyqtSignal()

    def __init__(self, ip: str, port: int, mode: Optional[str] = None, rid: Optional[int] = None):
        """Extended.

        Args:
            ip, port, mode, rid: See the attributes section.
        """
        super().__init__()
        self.ip = ip
        self.port = port
        self.mode = mode
        self.rid = rid

    @pyqtSlot()
    def run(self):
        """Overridden."""
        basePath = f"http://{self.ip}/{self.port}/experiment/"
        requests.post(basePath + self.mode + "/", params={"rid": self.rid}, timeout=10)
        self.done.emit()


class SchedulerApp(qiwis.BaseApp):
    """App for displaying the submitted experiment queue.

    Attributes:
        schedulerFrame: The frame that shows the submitted experiment queue.
        thread: The thread that fetches the submitted experiment queue.
        menu: The QMenu instance to display menu when right-clicked.
        actions: The dictionary of possible outcomes made by menu.
        worker: The QObject instance that runs on the menu thread.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        proxy_ip = self.constants.proxy_ip  # pylint: disable=no-member
        proxy_port = self.constants.proxy_port  # pylint: disable=no-member
        self.schedulerFrame = SchedulerFrame()
        self.thread = _ExperimentQueueFetcherThread(
            proxy_ip,
            proxy_port,
            self._snycExperimentQueue,
            self
        )
        self.thread.start()
        self.schedulerFrame.queueView.rightButtonPressed.connect(self.displayMenu)
        self.menu = QMenu(self.schedulerFrame)
        # TODO(giwon2004) Remove icon space from the menu list (use menu.setStyleSheet)
        self.actions = {
            "edit": self.menu.addAction("Edit"),
            "delete": self.menu.addAction("Delete"),
            "terminate": self.menu.addAction("Request termination")
        }
        self.worker = SchedulerPostWorker(proxy_ip, proxy_port)

    @pyqtSlot(QMouseEvent)
    def displayMenu(self, event: QMouseEvent):
        """Displays the menu pop-up.

        Args:
            event: Information holder containing the clicked position.
        """
        for i in range(self.schedulerFrame.model.rowCount()):
            index = self.schedulerFrame.model.index(i)
            if self.schedulerFrame.queueView.rectForIndex(index).contains(event.pos()):
                rid = self.schedulerFrame.model.data(index).rid
                action = self.menu.exec_(event.globalPos())
                if action == self.actions["edit"]:
                # TODO(giwon2004) Create an app for editing scannables.
                    pass
                else:
                    self.worker.rid = rid
                    if action == self.actions["delete"]:
                        self.worker.mode = "delete"
                    else:
                        self.worker.mode = "terminate"
                    _thread_with_worker(self.worker, self).start()

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
