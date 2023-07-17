"""App module for showing the experiment list."""

from typing import Optional, Tuple

from PyQt5.QtGui import QFont, QPainter
from PyQt5.QtCore import Qt, QObject, QAbstractListModel, QModelIndex, QMimeData, QModelIndex
from PyQt5.QtWidgets import QStyleOptionViewItem, QWidget, QLayout, QLabel, QListView, \
                            QPushButton, QHBoxLayout, QVBoxLayout, QAbstractItemDelegate, QAction

import qiwis
from iquip.protocols import ExperimentInfo

def delete_items_of_layout(layout: QLayout):
    """Auxiliary function for deleting components in the layout.

    Args:
        layout: The layout whose elements are intended to be deleted.
    """
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
            else:
                delete_items_of_layout(item.layout())


class SchedulerFrame(QWidget):
    """Frame for displaying the experiment list.
    
    Attributes:
        expRun: The ExperimentView widget displaying currently running experiment.
        expList: The QListView widget holding queued experiments.
        model: The ExperimentModel that manages the data of expList.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended. """
        super().__init__(parent=parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 20)
        self.expRun = RunningExperimentView(None, self)
        self.expList = QListView(self)
        self.expList.setItemDelegate(ExperimentDelegate(self.expList))
        self.expList.setMovement(QListView.Free)
        self.expList.setObjectName("Queued Experiments")
        self.model = ExperimentModel([])
        self.expList.setModel(self.model)
        layout.addWidget(QLabel("Currently running:"))
        layout.addWidget(self.expRun)
        layout.addWidget(QLabel("Queued experiments:"))
        layout.addWidget(self.expList)
        self.setLayout(layout)

        # Below are for testing before connecting to artiq-proxy
        self.addExp(ExperimentInfo("exp1", {"rid": 9, "priority": 3}))
        self.addExp(ExperimentInfo("exp2", {"rid": 10, "priority": 3}))
        self.addExp(ExperimentInfo("exp3", {"rid": 11, "priority": 4}))
        self.runExp(ExperimentInfo("exp4", {"rid": 12, "priority": 2}))

    #TODO: Below are called by the signal from artiq-proxy
    def runExp(self, info: ExperimentInfo):
        """Sets the experiment onto 'currently running' section (expRun).

        Args:
            info: The experiment information.
        """
        self.expRun.changeInfo(info)

    def addExp(self, info: ExperimentInfo):
        """Adds the experiment to 'queued experiments' section (expList).

        Args:
            info: The experiment information.
        """
        self.model.expData.append(info)
        self.model.expData.sort(key = lambda x: x.arginfo["priority"], reverse = True)

    def changeExp(self, idx: int, info: ExperimentInfo):
        """Changes the information of the particular experiment to given information.

        Args:
            idx: The index of to-be-changed experiment.
            info: The experiment information.
        """
        if info:
            self.model.expData[idx].changeInfo(info)
        else:
            self.delExp(self.model.expData[idx])

    def delExp(self, info: ExperimentInfo):
        """Deletes the experiment from 'queued experiments' section (expList).

        Args:
            info: The experiment information.
        """
        self.model.expData.remove(info)


class ExperimentModel(QAbstractListModel):
    """Model for managing the data in the experiment list.
    
    Attributes:
        data: The list of ExperimentView widget.
    """

    def __init__(self, data: list, parent=None):
        super().__init__(parent)
        self.expData = data

    def rowCount(self, parent=QModelIndex()):
        """Overrided."""
        return len(self.expData)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        """Overrided."""
        return self.expData[index.row()]

    def supportedDropActions(self):
        """Overrided."""
        return Qt.CopyAction | Qt.MoveAction

    def mimeData(self, index: QModelIndex) -> QMimeData:
        """Fetches the index of the selected element.
        
        Args:
            index: The ModelIndex instance containing 
                   row, column, and etc. values of the selected element.
        """
        mime = super().mimeData(index)
        mime.setText(str(index[0].row()))
        return mime

    def dropMimeData(self,
        mimedata: QMimeData,
        action: QAction,
        row: int,
        column: int,
        parentIndex: QModelIndex):
        """Changes the priority of the experiments.
        
        Args:
            mimedata: The QMimeData instance containing str value of the index.
            action: The QtAction instance classifying the action 
                    (for terminating the function when it is not dropped in the appropriate region)
            row: The target row that is to be changed with the experiment in mimedata.
            column: The target column, which is set to zero as it is a QListView.
            parentIndex: The ModelIndex instance containing
                         row, column, and etc. values of the target element.
        """
        idx = int(mimedata.text())
        if action == Qt.IgnoreAction:
            return True
        taridx = row if row < self.rowCount() else -1
        if self.expData[idx].arginfo["priority"] != self.expData[taridx].arginfo["priority"]:
            return True
        if idx > row:
            self.expData = self.expData[:row] + [self.expData[idx]] + \
                           self.expData[row:idx] + self.expData[idx+1:]
        elif idx < row:
            self.expData = self.expData[:idx] + self.expData[idx+1:row] + \
                           [self.expData[idx]] + self.expData[row:]

        #TODO: emit signal for change of priority through artiq-proxy
        return True

    def flags(self, index):
        """Overrided."""
        defaultFlags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.isValid():
            return Qt.ItemIsEditable | Qt.ItemIsDragEnabled | defaultFlags
        return Qt.ItemIsDropEnabled | defaultFlags


class ExperimentDelegate(QAbstractItemDelegate):
    """Delegate for displaying the layout of each data in the experiment list.
    
    Attributes:
        data: The list of ExperimentView widget.
    """

    def paint(self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex):
        """Overrided."""
        info = index.data(Qt.DisplayRole)
        expView = ExperimentView(info, self.parent())
        expView.resize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        expView.render(painter)
        painter.restore()

    def sizeHint(self, option: QStyleOptionViewItem, index: QModelIndex):
        """Overrided."""
        info = index.data(Qt.DisplayRole)
        expView = ExperimentView(info, self.parent())
        return expView.sizeHint()

    #TODO: Enabling buttons when displayed using QAbstractDelegate


class ExperimentView(QWidget):
    """Widget for displaying the information the experiment.
    
    Attributes:
        layout: The list of ExperimentView widget.
        argslayout: The HBoxLayout for displaying the experiment information besides its name.
        name: The QLabel instance for displaying the experiment name.
        editBtn: The button to call frame for edition of the experiment.
    """

    def __init__(self, info: ExperimentInfo, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            info: The information of the experiment.
        """
        super().__init__(parent=parent)
        layout = QHBoxLayout(self)
        if info:
            self.argslayout = QHBoxLayout()
            self.name = QLabel(info.name)
            self.name.setFont(QFont("Arial", 15))
            self.argslayout.addWidget(self.name)
            self.args = []
            for key in info.arginfo:
                self.args.append(QLabel(key + ': ' + str(info.arginfo[key])))
                self.argslayout.addWidget(self.args[-1])
            layout.addLayout(self.argslayout, 5)
            self.editBtn = QPushButton("EDIT")
            self.editBtn.clicked.connect(self.edit)
            layout.addWidget(self.editBtn, 1)
        else:
            self.name = QLabel("None")
            self.name.setFont(QFont("Arial", 10))
            layout.addWidget(self.name)
        self.setLayout(layout)

    def changeInfo(self, info: ExperimentInfo):
        """Change the information by modification.

        Args:
            info: The experiment information.
        """
        delete_items_of_layout(self.argslayout)
        if info:
            self.name.setText(info.name)
            self.name.setFont(QFont("Arial", 15))
            self.argslayout.addWidget(self.name)
            self.args = []
            for key in info.arginfo:
                self.args.append(QLabel(key + ': ' + str(info.arginfo[key])))
                self.argslayout.addWidget(self.args[-1])
            self.editBtn = QPushButton("EDIT")
            self.editBtn.clicked.connect(self.edit)

    def data(self):
        """Data transfer for displaying in ExperimentDelegate."""
        return self.expInfo

    def edit(self):
        """Edition of experiment informations."""
        #TODO: Display a frame for editing the values.
        pass


class RunningExperimentView(QWidget):
    """Widget for displaying the information the experiment, especially for the one running.
    
    Attributes:
        layout: The list of ExperimentView widget.
        argslayout: The HBoxLayout for displaying the experiment information besides its name.
        name: The QLabel instance for displaying the experiment name.
    """

    def __init__(self, info: ExperimentInfo, parent: Optional[QWidget] = None):
        """Extended.
        
        Args:
            info: The information of the experiment.
        """
        super().__init__(parent=parent)
        self.layout = QVBoxLayout(self)
        self.name = QLabel("None")
        self.name.setFont(QFont("Arial", 10))
        self.layout.addWidget(self.name)

    def changeInfo(self, info: ExperimentInfo):
        """Change the information by modification.

        Args:
            info: The experiment information.
        """
        delete_items_of_layout(self.layout)
        if info:
            self.name = QLabel(info.name)
            self.name.setFont(QFont("Arial", 20))
            self.layout.addWidget(self.name)
            self.argslayout = QHBoxLayout()
            self.args = []
            for key in info.arginfo:
                if key == "priority":
                    continue
                self.args.append(QLabel(key + ': ' + str(info.arginfo[key])))
                self.argslayout.addWidget(self.args[-1])
            self.layout.addLayout(self.argslayout)
        else:
            self.name = QLabel("None")
            self.name.setFont(QFont("Arial", 10))
            self.layout.addWidget(self.name)


class SchedulerApp(qiwis.BaseApp):
    """App for displaying the experiment queue.

    Attributes:
        schedulerFrame: The frame that shows the experiment queue.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""  
        super().__init__(name, parent=parent)
        self.schedulerFrame = SchedulerFrame()

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)
