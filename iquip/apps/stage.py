import logging
from typing import Dict, Optional, Tuple

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QDoubleSpinBox, QPushButton, QWidget,
    QVBoxLayout, QHBoxLayout,
)

import qiwis

logger = logging.getLogger(__name__)


RPCTargetInfo = Tuple[str, int, str]  # ip, port, target_name


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


class StageControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling motorized stages.
    
    Attributes:

    """

    def __init__(
        self,
        name: str,
        stages: Dict[str, RPCTargetInfo],
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            stages: Dictionary of stage information. Each key is the name of the
              stage and the value is its RPC target information.
        """
        super().__init__(name, parent=parent)
