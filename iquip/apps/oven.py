"""Module for oven controller."""

import functools
import logging
from typing import Any, List, Optional, Tuple

from PyQt5.QtCore import pyqtSignal, pyqtSlot, QObject
from PyQt5.QtWidgets import (
    QAbstractSpinBox, QDoubleSpinBox, QHBoxLayout, QPushButton, QSpinBox, QVBoxLayout, QWidget
)

import qiwis

logger = logging.getLogger(__name__)

class OvenControllerFrame(QWidget):
    """Frame for OvenControllerApp.
    
    Attributes:
        connectionButton: Button for toggling rpc connection.
        [current, voltage, timer]DisplayBox: Spinbox displaying the [current, voltage, timer],
          respectively (read-only).

    Signals:
        openTarget(): Open button is clicked.
        closeTarget(): Close button is clicked.
    """

    openTarget = pyqtSignal()
    closeTarget = pyqtSignal()

    def __init__(
        self,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent=parent)
        # widgets
        self.connectionButton = QPushButton("Open", self)
        self.connectionButton.setCheckable(True)
        self.currentDisplayBox = QDoubleSpinBox(self)
        self.currentDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.currentDisplayBox.setReadOnly(True)
        self.currentDisplayBox.setDecimals(3)
        self.currentDisplayBox.setSuffix("A")
        self.voltageDisplayBox = QDoubleSpinBox(self)
        self.voltageDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.voltageDisplayBox.setReadOnly(True)
        self.voltageDisplayBox.setDecimals(3)
        self.voltageDisplayBox.setSuffix("V")
        self.timerDisplayBox = QSpinBox(self)
        self.timerDisplayBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timerDisplayBox.setReadOnly(True)
        self.timerDisplayBox.setSuffix("s")
        self.timerResetButton = QPushButton("Reset", self)
        self.currentInputBox = QDoubleSpinBox(self)
        self.currentInputBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.currentInputBox.setDecimals(3)
        self.currentInputBox.setSingleStep(0.01)
        self.currentInputBox.setSuffix("A")
        self.timerInputBox = QSpinBox(self)
        self.timerInputBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.timerInputBox.setSingleStep(10)
        self.timerInputBox.setSuffix("s")
        self.outputButton = QPushButton("On", self)
        self.outputButton.setCheckable(True)
        self._inner = QWidget(self)  # except connectionButton
        # layout
        displayLayout = QHBoxLayout()
        displayLayout.addWidget(self.currentDisplayBox)
        displayLayout.addWidget(self.voltageDisplayBox)
        displayLayout.addWidget(self.timerDisplayBox)
        displayLayout.addWidget(self.timerResetButton)
        inputLayout = QHBoxLayout()
        inputLayout.addWidget(self.currentInputBox)
        inputLayout.addWidget(self.timerInputBox)
        inputLayout.addWidget(self.outputButton)
        innerLayout = QVBoxLayout(self._inner)
        innerLayout.addLayout(displayLayout)
        innerLayout.addLayout(inputLayout)
        layout = QVBoxLayout(self)
        layout.addWidget(self.connectionButton)
        layout.addWidget(self._inner)
        # signal connection
        self.connectionButton.clicked.connect(
            functools.partial(self.connectionButton.setEnabled, False))
        self.connectionButton.clicked.connect(self._connectionButtonClicked)
        # initialize state
        self.setConnected(False)

    @pyqtSlot(bool)
    def setConnected(self, open_: bool):
        """Sets the current connection status.

        This also changes the enabled status and the connection button text.
        
        Args:
            open_: True for open, False for closed.
        """
        self._inner.setEnabled(open_)
        self.connectionButton.setEnabled(True)
        self.connectionButton.setText("Close" if open_ else "Open")

    @pyqtSlot(bool)
    def _connectionButtonClicked(self, checked: bool):
        """Connection button is clicked.
        
        Args:
            checked: True for opening the target, False for closing.
        """
        if checked:
            self.openTarget.emit()
        else:
            self.closeTarget.emit()


class OvenControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling power supply unit for oven."""

    def __init__(
        self,
        name: str,
        target: List[Any],
        period: float = 10.0,
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            target: List of target info: "ip", port, "target_name", "target_channel".
              The target channel must be one of "p6v", "p25v", or "n25v".
            period: Voltage and current reading period in seconds.
        """
        super().__init__(name, parent=parent)
        self.frame = OvenControllerFrame()

    def frames(self) -> Tuple[Tuple[str, OvenControllerFrame]]:
        """Overridden."""
        return (("", self.frame),)
