"""App module for showing the experiment list."""

from typing import Optional, Tuple, List

from PyQt5.QtGui import QPainter
from PyQt5.QtCore import Qt, QObject, QAbstractListModel, QModelIndex, QMimeData, QSize
from PyQt5.QtWidgets import (
    QStyleOptionViewItem, QWidget, QLayout, QLabel, QListView,
    QPushButton, QHBoxLayout, QVBoxLayout, QAbstractItemDelegate, QAction
)

import qiwis
from iquip.protocols import ExperimentInfo

def _dismiss_items(layout: Optional[QLayout] = None):
    """Auxiliary function for decoupling components in the layout.

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
                widget = None
            else:
                _dismiss_items(item.layout())


class SchedulerFrame(QWidget):
    """Frame for displaying the submitted experiment list.
    
    Attributes:
        expRun: The ExperimentView widget displaying currently running experiment.
        expList: The QListView widget holding queued experiments.
        model: The ExperimentModel that manages the data of expList.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.expRun = RunningExperimentView()
        self.expList = QListView()
        self.expList.setItemDelegate(ExperimentDelegate(self.expList))
        self.expList.setMovement(QListView.Free)
        self.expList.setObjectName("Queued Experiments")
        self.model = ExperimentModel([])
        self.expList.setModel(self.model)
        # layout
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        layout.addWidget(QLabel("Currently running:"))
        layout.addWidget(self.expRun)
        layout.addWidget(QLabel("Queued experiments:"))
        layout.addWidget(self.expList)


class RunningExperimentView(QWidget):
    """Widget for displaying the information of the experiment, especially for the one running.
    
    Attributes:
        argsLayout: The HBoxLayout for displaying the experiment information besides its name.
        nameLabel: The QLabel instance for displaying the experiment name.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.nameLabel = QLabel("None", self)
        self.args = []
        # layout
        layout = QVBoxLayout(self)
        self.argsLayout = QHBoxLayout()
        layout.addWidget(self.nameLabel)
        layout.addLayout(self.argsLayout)

    def updateInfo(self, info: Optional[ExperimentInfo] = None):
        """Updates the information by modification.
        This updates expRun when new experiment starts to run.
        If info is None, it means there is no experiments running.

        Args:
            info: The experiment information.
        """
        _dismiss_items(self.argsLayout)
        if info:
            self.nameLabel.setText(info.name)
            for key, value in info.arginfo.items():
                if key != "priority":
                    self.argsLayout.addWidget(QLabel(f"{key}: {value}", self))
        else:
            self.nameLabel.setText("None")
        pass

class ExperimentView(QWidget):
    """Widget for displaying the information the experiment.
    
    Attributes:
        layout: The list of ExperimentView widget.
        argsLayout: The HBoxLayout for displaying the experiment information besides its name.
        nameLabel: The QLabel instance for displaying the experiment name.
        editButton: The button to call frame for edition of the experiment.
    """

    def __init__(self, info: ExperimentInfo, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            info: The information of the experiment.
        """
        super().__init__(parent=parent)
        # widgets
        self.nameLabel = QLabel(info.name, self)
        self.args = [QLabel(f"{key}: {value}", self) for key, value in info.arginfo.items()]
        self.editButton = QPushButton("EDIT")
        self.editButton.clicked.connect(self.edit)
        # layout
        layout = QHBoxLayout(self)
        self.argsLayout = QHBoxLayout()
        self.argsLayout.addWidget(self.nameLabel)
        for widget in self.args:
            self.argsLayout.addWidget(widget)
        layout.addLayout(self.argsLayout, 5)
        layout.addWidget(self.editButton, 1)
        self.setLayout(layout)

    def updateInfo(self, info: ExperimentInfo):
        """Updates the information by modification.
        The function edit() uses this for updating the edited arguments.

        Args:
            info: The experiment information.
        """
        _dismiss_items(self.argsLayout)
        self.nameLabel.setText(info.name)
        for key, value in info.arginfo.items():
            self.argsLayout.addWidget(QLabel(f"{key}: {value}", self))

    def data(self) -> ExperimentInfo:
        """Data transfer for displaying in ExperimentDelegate."""
        return self.expInfo

    def edit(self):
        """Showing frame for edition of experiment information.
        It is called when editButton is pressed.
        """
        # TODO(giwon2004): Display a frame for editing the values.
        print("Button Clicked")


class ExperimentModel(QAbstractListModel):
    """Model for managing the data in the submitted experiment list.
    
    Attributes:
        experimentData: The list of ExperimentView widget.
    """

    def __init__(self, data: List[ExperimentView], parent: Optional[QWidget] = None):
        """Overridden."""
        super().__init__(parent)
        self.experimentData = data

    def rowCount(self, parent: Optional[QModelIndex] = QModelIndex()) -> int:
        """Overridden."""
        return len(self.experimentData)

    def data(self, index: QModelIndex, role: Optional[Qt.ItemDataRole] = Qt.DisplayRole) -> ExperimentView:
        """Overridden."""
        return self.experimentData[index.row()]

    def supportedDropActions(self) -> int:
        """Overridden."""
        return Qt.CopyAction | Qt.MoveAction

    def mimeData(self, index: QModelIndex) -> QMimeData:
        """Fetches the index of the selected element.
        
        Args:
            index: The ModelIndex instance containing 
              row, column, and etc. values of the selected element.
        
        Returns:
            A QMimeData instance that holds str value of the index.
        """
        mime = super().mimeData(index)
        mime.setText(str(index[0].row()))
        return mime

    def dropMimeData(self,
        mimedata: QMimeData,
        action: QAction,
        row: int,
        column: int,
        parentIndex: QModelIndex
    ) -> bool:  # pylint: disable=too-many-arguments
        """Changes the priority of the experiments.
        
        Args:
            mimedata: The QMimeData instance containing str value of the index.
            action: The QtAction instance classifying the action 
              (for terminating the function when it is not dropped in the appropriate region)
            row: The target row that is to be changed with the experiment in mimedata.
            column: The target column, which is set to zero as it is a QListView.
            parentIndex: The ModelIndex instance containing
                         row, column, and etc. values of the target element.

        Returns:
            True value.
        """
        idx = int(mimedata.text())
        if action == Qt.IgnoreAction:
            return True
        taridx = row if row < self.rowCount() else -1
        row = row if row >= 0 else self.rowCount()
        if self.experimentData[idx].arginfo["priority"] != self.experimentData[taridx].arginfo["priority"]:
            return True
        if idx > row:
            self.experimentData = (self.experimentData[:row] + [self.experimentData[idx]] +
                           self.experimentData[row:idx] + self.experimentData[idx+1:])
        elif idx < row:
            self.experimentData = (self.experimentData[:idx] + self.experimentData[idx+1:row] +
                           [self.experimentData[idx]] + self.experimentData[row:])

        # TODO(giwon2004): emit signal for change of priority through artiq-proxy.
        return True

    def flags(self, index: QModelIndex) -> int:
        """Overrided."""
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
        info = index.data(Qt.DisplayRole)
        expView = ExperimentView(info, self.parent())
        expView.resize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        expView.render(painter)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex) -> QSize:
        """Overridden."""
        info = index.data(Qt.DisplayRole)
        expView = ExperimentView(info, self.parent())
        return expView.sizeHint()


class SchedulerApp(qiwis.BaseApp):
    """App for displaying the submitted experiment queue.

    Attributes:
        schedulerFrame: The frame that shows the submitted experiment queue.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""  
        super().__init__(name, parent=parent)
        self.schedulerFrame = SchedulerFrame()
        # TODO(giwon2004): Below are for testing before connecting to artiq-proxy.
        self.addExperiment(ExperimentInfo("exp1", {"rid": 9, "priority": 3}))
        self.addExperiment(ExperimentInfo("exp2", {"rid": 10, "priority": 3}))
        self.addExperiment(ExperimentInfo("exp3", {"rid": 11, "priority": 4}))
        self.runExperiment(ExperimentInfo("exp4", {"rid": 12, "priority": 2}))

    # TODO(giwon2004): Below are called by the signal from artiq-proxy.
    def runExperiment(self, info: Optional[ExperimentInfo] = None):
        """Sets the experiment onto 'currently running' section.

        Args:
            info: The experiment information.
        """
        self.schedulerFrame.expRun.updateInfo(info)

    def addExperiment(self, info: ExperimentInfo):
        """Adds the experiment to 'queued experiments' section (expList).

        Args:
            info: The experiment information.
        """
        self.schedulerFrame.model.experimentData.append(info)
        self.schedulerFrame.model.experimentData.sort(key = lambda x: x.arginfo["priority"],
                                               reverse = True)

    def changeExperiment(self, idx: int, info: Optional[ExperimentInfo] = None):
        """Changes the information of the particular experiment to given information.

        Args:
            idx: The index of to-be-changed experiment.
            info: The experiment information.
        """
        if info:
            self.schedulerFrame.model.experimentData[idx].updateInfo(info)
        else:
            self.deleteExperiment(self.schedulerFrame.model.experimentData[idx])

    def deleteExperiment(self, info: ExperimentInfo):
        """Deletes the experiment from 'queued experiments' section (expList).

        Args:
            info: The experiment information.
        """
        self.schedulerFrame.model.experimentData.remove(info)

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)
