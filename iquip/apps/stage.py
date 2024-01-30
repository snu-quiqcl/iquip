import logging
from typing import Any, Dict, Optional, Tuple

from sipyco.pc_rpc import Client
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QDoubleSpinBox, QGroupBox, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout
)

import qiwis

logger = logging.getLogger(__name__)

RPCTargetInfo = Tuple[str, int, str]  # ip, port, target_name

class StageManager(QObject):
    """Manages the stage RPC clients which live in a dedicated thread.
    
    An instance of this class should be moved to a thread other than the main
      GUI thread to prevent GUI from freezing.
    Therefore, the private methods must not be called from the main thread.
    Instead, use signals to communicate.

    Signals:

    """

    def __init__(self, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(parent=parent)
        self._clients: Dict[str, Client] = {}


class StageWidget(QWidget):
    """UI for stage control.

    Signals:
        moveTo(position_m): Absolute move button is clicked, with the destination
          position in meters.
        moveBy(displacement_m): Relative move button is clicked, with the desired
          displacement in meters.
    
    All the displayed values are in mm unit.
    However, the values for interface (methods and signals) are in m.
    """

    moveTo = pyqtSignal(float)
    moveBy = pyqtSignal(float)

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        # widgets
        self.positionBox = QDoubleSpinBox(self)
        self.positionBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.positionBox.setReadOnly(True)
        self.absoluteBox = QDoubleSpinBox(self)
        self.absoluteBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.absoluteButton = QPushButton("Go", self)
        self.relativeBox = QDoubleSpinBox(self)
        self.relativeBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.relativePositiveButton = QPushButton("Move +", self)
        self.relativeNegativeButton = QPushButton("Move -", self)
        # layout
        abosluteLayout = QVBoxLayout()
        abosluteLayout.addWidget(self.absoluteBox)
        abosluteLayout.addWidget(self.absoluteButton)
        relativeLayout = QVBoxLayout()
        relativeLayout.addWidget(self.relativePositiveButton)
        relativeLayout.addWidget(self.relativeBox)
        relativeLayout.addWidget(self.relativeNegativeButton)
        moveLayout = QHBoxLayout()
        moveLayout.addLayout(abosluteLayout)
        moveLayout.addLayout(relativeLayout)
        layout = QVBoxLayout(self)
        layout.addWidget(self.positionBox)
        layout.addLayout(moveLayout)
        # signal connection
        self.absoluteButton.clicked.connect(self._absoluteMove)
        self.relativePositiveButton.clicked.connect(self._relativePositiveMove)
        self.relativeNegativeButton.clicked.connect(self._relativeNegativeMove)
    
    @pyqtSlot(float)
    def setPosition(self, position_m):
        """Sets the current position displayed on the widget.
        
        Args:
            position_m: Position in meters.
        """
        self.positionBox.setValue(position_m * 1e3)

    def position(self) -> float:
        """Returns the current position in meters."""
        return self.positionBox.value() / 1e3
    
    @pyqtSlot()
    def _absoluteMove(self):
        """Absolute move button is clicked."""
        self.moveTo.emit(self.absoluteBox.value() / 1e3)
    
    @pyqtSlot()
    def _relativePositiveMove(self):
        """Relative positive move button is clicked."""
        self.moveBy.emit(self.relativeBox.value() / 1e3)
    
    @pyqtSlot()
    def _relativeNegativeMove(self):
        """Relative negative move button is clicked."""
        self.moveBy.emit(-self.relativeBox.value() / 1e3)


class StageControllerFrame(QWidget):
    """Frame for StageControllerApp."""

    def __init__(
        self,
        stages: Dict[str, Dict[str, Any]],
        parent: Optional[QObject] = None
    ):
        """Extended.
        
        Args:
            See StageControllerApp.
        """
        super().__init__(parent=parent)
        self.widgets: Dict[str, StageWidget] = {}
        layout = QGridLayout(self)
        for stage_name, stage_info in stages.items():
            widget = StageWidget(self)
            groupbox = QGroupBox(stage_name, self)
            groupboxLayout = QHBoxLayout(groupbox)
            groupboxLayout.addWidget(widget)
            layout.addWidget(groupbox, *stage_info["index"])
            self.widgets[stage_name] = widget


class StageControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling motorized stages.
    
    Attributes:

    """

    def __init__(
        self,
        name: str,
        stages: Dict[str, Dict[str, Any]],
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            stages: Dictionary of stage information. Each key is the name of the
              stage and the value is agian a dictionary, whose structure is:
              {
                "index": [row, column],
                "target": ["ip", port, "target_name"]
              }
        """
        super().__init__(name, parent=parent)
        self.frame = StageControllerFrame(stages, self)
        
    def frames(self) -> Tuple[Tuple[str, StageControllerFrame]]:
        """Overridden."""
        return (("", self.frame),)
