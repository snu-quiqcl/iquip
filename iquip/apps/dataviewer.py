"""App module for data viewers which displays result data using plot, etc."""

import abc
import dataclasses
import logging
from typing import Sequence, Optional

import numpy as np
import pyqtgraph as pg

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
          not kHz. In some cases, this might not be numeric values but string,
          etc.
        unit: The unit of the values without any unit prefix, e.g., u, m, k, M.
    """
    name: str
    values: Sequence
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
