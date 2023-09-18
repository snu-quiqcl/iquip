"""App module for data viewers which displays result data using plot, etc."""

import abc
import dataclasses
import enum
import logging
from typing import Sequence, Optional

import numpy as np
import pyqtgraph as pg
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QRadioButton, QButtonGroup, QStackedWidget,
    QAbstractSpinBox, QSpinBox, QHBoxLayout, QVBoxLayout
)

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AxisInfo:
    """Axis information of ndarray data.

    Usually each axis of an ndarray corresponds to a specific scan parameter.
    For example, if one counts the photons for 100 shots and t in range(0, 10),
      it yields 2 dimensional results (in total 1000 data points) whose shape
      is (10, 100) - axis 0 is "t" and axis 1 is "shot".
    
    Fields:
        name: The name describing the axis.
        values: The parameter values for the axis. The length should be equal
          to the corresponding ndarry size of the axis. If unit is given, the
          values should be in that unit, without any unit prefix, e.g., in Hz,
          not kHz.
        unit: The unit of the values without any unit prefix, e.g., u, m, k, M.
    """
    name: str
    values: Sequence[float]
    unit: Optional[str] = None


class NDArrayViewer(metaclass=abc.ABCMeta):  # pylint: disable=too-few-public-methods
    """Data viewer interface for ndarray data.
    
    Attributes:
        ndim: The number of array dimensions of the ndarray data.
    """

    def __init__(self, ndim: int):
        """
        Args:
            ndim: See attribute docstring.
        """
        self.ndim = ndim

    @abc.abstractmethod
    def setData(self, data: np.ndarray, axes: Sequence[AxisInfo]):
        """Updates the data for the viewer.
        
        Args:
            data: The new ndarray data. Its dimension should be self.ndim.
            axes: AxisInfos in the corresponding order of the data axes.
              Each axis values size must agree with the data shape.
        """
        if data.ndim != self.ndim:
            raise ValueError(f"Dimension mismatch: {data.ndim} != {self.ndim}")
        if data.ndim != len(axes):
            raise ValueError("Data dimension and number of axes do not match: "
                             f"{data.ndim} != {len(axes)}")
        for size, info in zip(data.shape, axes):
            if size != len(info.values):
                raise ValueError(f"Size mismatch in {info}: expected {size} values")


class CurvePlotViewer(NDArrayViewer):  # pylint: disable=too-few-public-methods
    """Plot viewer for visualizing a 2D curve.
    
    Attributes:
        plotItem: The PlotItem for showing the curve plot.
        widget: The PlotWidget which contains the plotItem.
        curve: The PlotDataItem which represents the curve plot.
    """

    def __init__(self, **kwargs):
        """
        Args:
            **kwargs: Passed as keyword arguments to instantiate a PlotItem.
        """
        super().__init__(ndim=1)
        self.plotItem = pg.PlotItem(**kwargs)
        self.widget = pg.PlotWidget(plotItem=self.plotItem)
        self.curve = self.plotItem.plot()

    def setData(self, data: np.ndarray, axes: Sequence[AxisInfo]):
        """Extended."""
        super().setData(data, axes)
        axis = axes[0]
        self.plotItem.setLabel(axis="bottom", text=axis.name, units=axis.unit)
        self.curve.setData(axis.values, data)


class HistogramViewer(NDArrayViewer):  # pylint: disable=too-few-public-methods
    """Histogram viewer showing a bar graph.
    
    Attributes:
        plotItem: The PlotItem for showing the histogram.
        widget: The PlotWidget which contains the plotItem.
        histogram: The BarGraphItem which represents the histogram.
    """

    def __init__(self, **kwargs):
        """
        Args:
            **kwargs: Passed as keyword arguments to instantiate a PlotItem.
        """
        super().__init__(ndim=1)
        self.plotItem = pg.PlotItem(**kwargs)
        self.widget = pg.PlotWidget(plotItem=self.plotItem)
        self.histogram = pg.BarGraphItem(x=(), height=(), width=1)
        self.plotItem.addItem(self.histogram)

    def setData(self, data: np.ndarray, axes: Sequence[AxisInfo]):
        """Extended."""
        super().setData(data, axes)
        axis = axes[0]
        self.plotItem.setLabel(axis="bottom", text=axis.name, units=axis.unit)
        self.histogram.setOpts(x=axis.values, height=data, width=1)


class ImageViewer(NDArrayViewer):  # pylint: disable=too-few-public-methods
    """2D image viewer, e.g., beam shape profile.
    
    Attributes:
        plotItem: The PlotItem for showing the image.
        widget: The ImageView which contains the plotItem.
        image: The ImageItem which represents the image.
    """

    def __init__(self, **kwargs):
        """
        Args:
            **kwargs: Passed as keyword arguments to instantiate a PlotItem.
        """
        super().__init__(ndim=2)
        self.plotItem = pg.PlotItem(**kwargs)
        self.image = pg.ImageItem(image=np.empty((1, 1)))
        self.widget = pg.ImageView(view=self.plotItem, imageItem=self.image)
        self.plotItem.setAspectLocked(False)
        self.plotItem.showGrid(True, True)

    def setData(self, data: np.ndarray, axes: Sequence[AxisInfo]):
        """Extended.
        
        Since the image should be transformed linearly, the given axes parameter
          values should be linearly increasing sequences.
        """
        super().setData(data, axes)
        self.image.setImage(data)
        vaxis, haxis = axes
        self.plotItem.setLabel(axis="left", text=vaxis.name, units=vaxis.unit)
        self.plotItem.setLabel(axis="bottom", text=haxis.name, units=haxis.unit)
        x, y = haxis.values[0], vaxis.values[0]
        width, height = haxis.values[-1] - x, vaxis.values[-1] - y
        self.image.setRect(x, y, width, height)


class _RealtimePart(QWidget):
    """Part widget for configuring realtime mode of the source widget.
    
    Attributes:
        label: Label for showing information about the current experiment.
          When it is synchronized with an experiment, it displays the RID
          of the experiment. Otherwise, it shows "No running experiment.".
        button: Button for synchronizing with the current artiq master.
    """

    def __init__(self, parent=None):
        """Extended."""
        super().__init__(parent=parent)
        self.label = QLabel("No running experiment.", self)
        self.button = QPushButton("Sync", self)
        layout = QHBoxLayout(self)
        layout.addWidget(self.label)
        layout.addWidget(self.button)


class _RemotePart(QWidget):
    """Part widget for configuring remote mode of the source widget.
    
    Attributes:
        spinbox: Spinbox for RID input.
        label: Label for showing the execution time of the experiment.
    """

    def __init__(self, parent=None):
        """Extended."""
        super().__init__(parent=parent)
        self.spinbox = QSpinBox(self)
        self.spinbox.setRange(0, 999_999_999)
        self.spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.label = QLabel("Unknown", self)


class SourceWidget(QWidget):
    """Widget for data source selection.
    
    Attributes:
        buttonGroup: The radio button group for source selection.
        stack: The stacked widget for additional interface of each source option.
    """

    class ButtonId(enum.IntEnum):
        """Source selection button id."""
        REALTIME = 0
        REMOTE = 1

    def __init__(self, parent=None):
        """Extended."""
        super().__init__(parent=parent)
        buttonGroupLayout = QVBoxLayout()
        self.buttonGroup = QButtonGroup(self)
        for buttonId in SourceWidget.ButtonId:
            button = QRadioButton(buttonId.name.capitalize(), self)
            self.buttonGroup.addButton(button, id=buttonId.value)
            buttonGroupLayout.addWidget(button)
        self.buttonGroup.button(SourceWidget.ButtonId.REALTIME).setChecked(True)
        self.stack = QStackedWidget(self)
        for _Part in (_RealtimePart, _RemotePart):
            self.stack.addWidget(_Part(self))
        self.stack.setCurrentIndex(SourceWidget.ButtonId.REALTIME)
        layout = QHBoxLayout(self)
        layout.addLayout(buttonGroupLayout)
        layout.addWidget(self.stack)
