"""Protocol module for defining common forms."""
import posixpath
from typing import Callable, List, Optional, Tuple, Union

from PyQt5 import QtGui
from PyQt5.QtGui import QFont
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSlot, pyqtSignal, QVariant, QAbstractListModel, QModelIndex, QMimeData
from PyQt5.QtWidgets import QWidget, QLabel, QListView, QPushButton, QHBoxLayout, QVBoxLayout, QAbstractItemDelegate

import qiwis
from iquip.protocols import ExperimentInfo
from iquip.apps.thread import ExperimentInfoThread    

def deleteItemsOfLayout(layout):
    if layout is not None:
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
            else:
                deleteItemsOfLayout(item.layout())

class SchedulerFrame(QWidget):
    """Frame for displaying the experiment list.
    
    Attributes:
    """
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 20)
        self.expRun = RunningExperimentView(None, self)
        self.expList = QListView(self)
        self.expList.setItemDelegate(ExperimentDelegate(self.expList))
        self.expList.setMovement(QListView.Free)
        self.expList.setObjectName("Queued Experiments")
        self.model = ExperimentModel([])
        self.expList.setModel(self.model)
        self.layout.addWidget(QLabel("Currently running:"))
        self.layout.addWidget(self.expRun)
        self.layout.addWidget(QLabel("Queued experiments:"))
        self.layout.addWidget(self.expList)
        self.addExp(ExperimentInfo("exp1", {"rid": 9, "priority": 3}))
        self.addExp(ExperimentInfo("exp2", {"rid": 10, "priority": 3}))
        self.addExp(ExperimentInfo("exp3", {"rid": 11, "priority": 4}))
        self.runExp(ExperimentInfo("exp4", {"rid": 12, "priority": 2}))

    # below are called by the signal from artiq
    def runExp(self, exp: ExperimentInfo):
        self.expRun.changeInfo(exp)

    def addExp(self, exp: ExperimentInfo):
        self.model.data.append(exp)
        self.model.data.sort(key = lambda x: x.arginfo["priority"], reverse = True)

    def changeExp(self, idx, exp: ExperimentInfo):
        if exp:
            self.model.data[idx].changeInfo(exp)
        else:
            self.delExp(self.model.data[idx])

    def delExp(self, exp: ExperimentInfo):
        self.model.data.remove(exp)

class ExperimentModel(QAbstractListModel):
    def __init__(self, data, parent=None):
        super().__init__(parent)
        self.data = data

    def rowCount(self, parent=QModelIndex()):
        return len(self.data)

    def data(self, index, role=Qt.DisplayRole):
        return self.data[index.row()]

    def supportedDropActions(self):
        return Qt.CopyAction | Qt.MoveAction

    def mimeData(self, index):
        mime = super(ExperimentModel, self).mimeData(index)
        mime.setText(str(index[0].row()))
        return mime

    def dropMimeData(self, mimedata, action, row, column, parentIndex):
        print(column)
        idx = int(mimedata.text())
        if action == Qt.IgnoreAction: return True 
        if self.data[idx].arginfo["priority"] != self.data[row if row < self.rowCount() else -1].arginfo["priority"]: return True
        if idx > row:
            self.data = self.data[:row] + [self.data[idx]] + self.data[row:idx] + self.data[idx+1:]
        else:
            self.data = self.data[:idx] + self.data[idx+1:row] + [self.data[idx]] + self.data[row:]
        # emit signal for change of priority
        return True

    def flags(self, index):
        defaultFlags = Qt.ItemIsSelectable | Qt.ItemIsEnabled
        if index.isValid(): return Qt.ItemIsEditable | Qt.ItemIsDragEnabled | defaultFlags       
        else: return Qt.ItemIsDropEnabled | defaultFlags

class ExperimentDelegate(QAbstractItemDelegate):

    def paint(self, painter, option, index):
        info = index.data(Qt.DisplayRole)
        expView = ExperimentView(info, self.parent())
        expView.resize(option.rect.size())
        painter.save()
        painter.translate(option.rect.topLeft())
        expView.render(painter)
        painter.restore()

    def sizeHint(self, option, index):
        info = index.data(Qt.DisplayRole)
        expView = ExperimentView(info, self.parent())
        return expView.sizeHint()

class ExperimentView(QWidget):
    def __init__(self, info: ExperimentInfo, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.layout = QHBoxLayout(self)
        if info:
            self.argslayout = QHBoxLayout()
            self.name = QLabel(info.name)
            self.name.setFont(QFont("Arial", 15))
            self.argslayout.addWidget(self.name)
            self.args = []
            for key in info.arginfo:
                self.args.append(QLabel(key + ': ' + str(info.arginfo[key])))
                self.argslayout.addWidget(self.args[-1])
            self.layout.addLayout(self.argslayout, 5)
            self.editBtn = QPushButton("EDIT")
            self.editBtn.clicked.connect(self.edit)
            self.layout.addWidget(self.editBtn, 1)
        else:
            self.name = QLabel("None")
            self.name.setFont(QFont("Arial", 10))
            self.layout.addWidget(self.name)

    def changeInfo(self, info: ExperimentInfo):
        deleteItemsOfLayout(self.layout)
        if info:
            self.argslayout = QHBoxLayout()
            self.name = QLabel(info.name)
            self.name.setFont(QFont("Arial", 15))
            self.argslayout.addWidget(self.name)
            self.args = []
            for key in info.arginfo:
                self.args.append(QLabel(key + ': ' + str(info.arginfo[key])))
                self.argslayout.addWidget(self.args[-1])
            self.layout.addLayout(self.argslayout, 5)
            self.editBtn = QPushButton("EDIT")
            self.editBtn.clicked.connect(self.edit)
            self.layout.addWidget(self.editBtn, 1)

    def data(self):
        return self.expInfo

    def edit(self):
        print('!')

class RunningExperimentView(QWidget):
    def __init__(self, info: ExperimentInfo, parent: Optional[QWidget] = None):
        super().__init__(parent=parent)
        self.layout = QVBoxLayout(self)
        self.name = QLabel("None")
        self.name.setFont(QFont("Arial", 10))
        self.layout.addWidget(self.name)

    def changeInfo(self, info: ExperimentInfo):
        deleteItemsOfLayout(self.layout)
        if info:
            self.name = QLabel(info.name)
            self.name.setFont(QFont("Arial", 20))
            self.layout.addWidget(self.name)
            self.argslayout = QHBoxLayout()
            self.args = []
            for key in info.arginfo:
                if key == "priority": continue
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

    """

    def __init__(
        self,
        name: str,
        parent: Optional[QObject] = None
    ):  
        super().__init__(name, parent=parent)
        self.schedulerFrame = SchedulerFrame()

    def frames(self) -> Tuple[SchedulerFrame]:
        """Overridden."""
        return (self.schedulerFrame,)