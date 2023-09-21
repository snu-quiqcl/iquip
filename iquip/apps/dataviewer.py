"""App module for data viewers which displays result data using plot, etc."""

import abc
import dataclasses
import enum
import functools
import logging
from typing import Dict, Tuple, Sequence, Optional, Union

import numpy as np
import pyqtgraph as pg
from pyqtgraph.GraphicsScene import mouseEvents
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QRadioButton, QButtonGroup, QStackedWidget,
    QAbstractSpinBox, QSpinBox, QDoubleSpinBox, QGroupBox, QSplitter,
    QHBoxLayout, QVBoxLayout, QGridLayout,
)
from PyQt5.QtCore import pyqtSignal, pyqtSlot

logger = logging.getLogger(__name__)

MAX_INT = 2**31 - 1

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
        plotItem: pg.PlotItem object for the plot.
    """

    def __init__(self, ndim: int):
        """
        Args:
            ndim: See attribute docstring.
        """
        self.ndim = ndim
        self.plotItem = pg.PlotItem()

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

    def nearestDataPoint(
        self,
        scenePos: pg.Point,  # pylint: disable=unused-argument
        tolerance: Optional[float] = None,  # pylint: disable=unused-argument
    ) -> Optional[Tuple[int, ...]]:
        """Returns the index of the nearest data point.
        
        Args:
            scenePos: Scene position coordinates.
            tolerance: Maximum Euclidean distance in the scene coordinate,
              for aiming tolerance. If None, the tolerance is infinity,
              i.e., the nearest data point is always returned.
              Otherwise, it might return None if there is no data point
              within the tolerance.
        """
        return None

class CurvePlotViewer(NDArrayViewer):  # pylint: disable=too-few-public-methods
    """Plot viewer for visualizing a 2D curve.
    
    Attributes:
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

    def nearestDataPoint(
        self,
        scenePos: pg.Point,
        tolerance: Optional[float] = None,
    ) -> Optional[Tuple[int]]:
        """Overridden."""
        viewBox = self.plotItem.getViewBox()
        viewPos = viewBox.mapSceneToView(scenePos)
        viewRect = viewBox.viewRect()
        sceneRect = viewBox.rect()
        x, y = self.curve.getOriginalDataset()
        dx, dy = viewPos.x() - x, viewPos.y() - y
        rx, ry = sceneRect.width() / viewRect.width(), sceneRect.height() / viewRect.height()
        distanceSquared = np.square(dx * rx) + np.square(dy * ry)
        minIndex = np.argmin(distanceSquared)
        if tolerance is None or distanceSquared[minIndex] <= np.square(tolerance):
            return (minIndex,)
        return None


class HistogramViewer(NDArrayViewer):  # pylint: disable=too-few-public-methods
    """Histogram viewer showing a bar graph.
    
    Attributes:
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

    def nearestDataPoint(
        self,
        scenePos: pg.Point,
        tolerance: Optional[float] = None,  # pylint: disable=unused-argument
    ) -> Optional[Tuple[int, int]]:
        """Overridden.
        
        ImageViewer does not use tolerance since it has a clear bounding box for
          each data point.
        """
        dataPos = self.image.mapFromDevice(scenePos)
        x, y = np.floor(dataPos.x()), np.floor(dataPos.y())
        w, h = self.image.width(), self.image.height()
        if 0 <= x < w and 0 <= y < h:
            return int(x), int(y)
        return None


class _RealtimePart(QWidget):
    """Part widget for configuring realtime mode of the source widget.
    
    Attributes:
        label: Label for showing information about the current experiment.
          When it is synchronized with an experiment, it displays the RID
          of the experiment. Otherwise, it shows "No running experiment.".
        button: Button for synchronizing with the current artiq master.
    """

    def __init__(self, parent: Optional[QWidget] = None):
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

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.spinbox = QSpinBox(self)
        self.spinbox.setMaximum(MAX_INT)
        self.spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.label = QLabel("Unknown", self)
        layout = QHBoxLayout(self)
        layout.addWidget(self.spinbox)
        layout.addWidget(self.label)


class SourceWidget(QWidget):
    """Widget for data source selection.
    
    Attributes:
        buttonGroup: The radio button group for source selection.
        stack: The stacked widget for additional interface of each source option.
    """

    class ButtonId(enum.IntEnum):
        """Source selection button id.
        
        Since the int value is used for the stacked widget index as well, it
          must increase by 1, starting from 0.
        """
        REALTIME = 0
        REMOTE = 1

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        buttonGroupLayout = QVBoxLayout()
        self.buttonGroup = QButtonGroup(self)
        for buttonId in SourceWidget.ButtonId:
            button = QRadioButton(buttonId.name.capitalize(), self)
            self.buttonGroup.addButton(button, id=buttonId)
            buttonGroupLayout.addWidget(button)
        self.buttonGroup.button(SourceWidget.ButtonId.REALTIME).setChecked(True)
        self.stack = QStackedWidget(self)
        for _Part in (_RealtimePart, _RemotePart):  # same order as in ButtonId
            self.stack.addWidget(_Part(self))
        self.stack.setCurrentIndex(SourceWidget.ButtonId.REALTIME)
        layout = QHBoxLayout(self)
        layout.addLayout(buttonGroupLayout)
        layout.addWidget(self.stack)
        self.buttonGroup.idClicked.connect(self.stack.setCurrentIndex)


class DataPointWidget(QWidget):
    """Widget for configuring each data point.
    
    Attributes:
        seriesLabel: Label showing the name of the current data series (dataset).
        numberOfSamplesBox: Spin box showing the total number of samples.
        thresholdBox: Spin box for setting the threshold for state discrimination.
        buttonGroup: Data type selection radio button group.
        valueBoxes: Dict of spin boxes for each data type.
        histogram: HistogramViewer for showing the photon count histogram.

    Signals:
        dataTypeChanged(dataType): Current data type is changed to dataType.
        thresholdChanged(threshold): Current threshold value is changed to threshold.
    """

    class DataType(enum.IntEnum):
        """Type of each data point.
        
        Each item is used as its index in the button group.
        """
        TOTAL = 0
        AVERAGE = 1
        P1 = 2

    dataTypeChanged = pyqtSignal(DataType)
    thresholdChanged = pyqtSignal(int)

    # pylint: disable=too-many-statements
    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        layout = QGridLayout(self)
        # first column (general information)
        self.seriesLabel = QLabel(self)
        self.numberOfSamplesBox = QSpinBox(self)
        self.numberOfSamplesBox.setMaximum(MAX_INT)
        self.numberOfSamplesBox.setButtonSymbols(QAbstractSpinBox.NoButtons)
        self.numberOfSamplesBox.setReadOnly(True)
        self.numberOfSamplesBox.setFrame(False)
        self.thresholdBox = QSpinBox(self)
        self.thresholdBox.setMaximum(MAX_INT)
        self.thresholdBox.setButtonSymbols(QAbstractSpinBox.PlusMinus)
        self.thresholdBox.setPrefix("> ")
        seriesLayout = QHBoxLayout()
        seriesLayout.addWidget(QLabel("Series: ", self))
        seriesLayout.addWidget(self.seriesLabel)
        numberOfSamplesLayout = QHBoxLayout()
        numberOfSamplesLayout.addWidget(QLabel("#Samples: ", self))
        numberOfSamplesLayout.addWidget(self.numberOfSamplesBox)
        thresholdLayout = QHBoxLayout()
        thresholdLayout.addWidget(QLabel("Threshold: ", self))
        thresholdLayout.addWidget(self.thresholdBox)
        firstColumn = seriesLayout, numberOfSamplesLayout, thresholdLayout
        for row, item in enumerate(firstColumn):
            layout.addLayout(item, row, 0)
        # second column (data type selection)
        self.buttonGroup = QButtonGroup(self)
        self.valueBoxes: Dict[DataPointWidget.DataType, QSpinBox] = {}
        for dataType in DataPointWidget.DataType:
            button = QRadioButton(dataType.name.capitalize(), self)
            self.buttonGroup.addButton(button, id=dataType)
            if dataType is DataPointWidget.DataType.TOTAL:
                spinbox = QSpinBox(self)
                spinbox.setMaximum(MAX_INT)
            else:
                spinbox = QDoubleSpinBox(self)
                if dataType is DataPointWidget.DataType.P1:
                    spinbox.setMaximum(1)
                else:
                    spinbox.setMaximum(np.inf)
            spinbox.setButtonSymbols(QAbstractSpinBox.NoButtons)
            spinbox.setReadOnly(True)
            spinbox.setFrame(False)
            self.valueBoxes[dataType] = spinbox
            layout.addWidget(button, dataType, 2)
            layout.addWidget(QLabel(":", self), dataType, 3)
            layout.addWidget(spinbox, dataType, 4)
        layout.setColumnStretch(1, 1)
        self.setDataType(DataPointWidget.DataType.P1)
        # histogram viewer
        self.histogram = HistogramViewer(title="Photon count histogram",
                                         labels={"left": "#samples"})
        lineX = self.threshold() + 0.5
        self._thresholdLine = self.histogram.plotItem.addLine(x=lineX)
        layout.addWidget(
            self.histogram.widget, len(DataPointWidget.DataType), 0, 1, 5,
        )
        # signal connection
        self.buttonGroup.idToggled.connect(self._idToggledSlot)
        self.thresholdBox.valueChanged.connect(self.thresholdChanged)
        self.thresholdChanged.connect(self._plotThresholdLine)

    def seriesName(self) -> str:
        """Returns the current data series name."""
        return self.seriesLabel.text()

    @pyqtSlot(str)
    def setSeriesName(self, name: str):
        """Sets the current data series name.
        
        Args:
            name: New data series name.
        """
        self.seriesLabel.setText(name)

    def numberOfSamples(self) -> int:
        """Returns the number of samples for the current data point."""
        return self.numberOfSamplesBox.value()

    @pyqtSlot(int)
    def setNumberOfSamples(self, numberOfSamples: int):
        """Sets the current number of samples.
        
        Args:
            numberOfSamples: New value for the number of samples.
        """
        self.numberOfSamplesBox.setValue(numberOfSamples)

    def threshold(self) -> int:
        """Returns the current threshold."""
        return self.thresholdBox.value()

    @pyqtSlot(int)
    def setThreshold(self, threshold: int):
        """Sets the threshold for state discrimination.
        
        Args:
            threshold: A measurement is regarded as 1 if photon count > threshold.
        """
        self.thresholdBox.setValue(threshold)

    def dataType(self) -> DataType:
        """Returns the current data type."""
        return DataPointWidget.DataType(self.buttonGroup.checkedId())

    @pyqtSlot(DataType)
    def setDataType(self, dataType: DataType):
        """Sets the curent data type.
        
        Args:
            dataType: Desired data type.
        """
        self.buttonGroup.button(dataType).setChecked(True)

    def value(self, dataType: Optional[DataType] = None) -> Union[int, float]:
        """Returns the data value of the given data type.
        
        Args:
            dataType: Target data type. None for the current data type (selected).
        """
        if dataType is None:
            dataType = self.dataType()
        return self.valueBoxes[dataType].value()

    @pyqtSlot(int, DataType)
    @pyqtSlot(float, DataType)
    def setValue(self, value: Union[int, float], dataType: DataType):
        """Sets the data value of the given data type.
        
        Args:
            value: New data value.
            dataType: Target data type. Note that this is not optional.
        """
        self.valueBoxes[dataType].setValue(value)

    def setHistogramData(self, data: np.ndarray, axes: Sequence[AxisInfo]):
        """Sets the histogram data.
        
        Args:
            data, axes: See HistogramViewer.setData().
        """
        self.histogram.setData(data, axes)

    @pyqtSlot(int)
    def _plotThresholdLine(self, threshold: int):
        """Draws a vertical infinite line indicating the threshold.
        
        Args:
            threshold: The current threshold value.
        """
        self._thresholdLine.setValue(threshold + 0.5)

    @pyqtSlot(int, bool)
    def _idToggledSlot(self, id_: int, checked: bool):
        """Slot for buttonGroup.idToggled signal.
        
        Args:
            id_: The event source button id in the button group.
            checked: Whether the button is now checked or not.
        """
        if checked:
            self.dataTypeChanged.emit(DataPointWidget.DataType(id_))


class MainPlotWidget(QWidget):
    """Widget showing the main plot.
    
    Attributes:
        stack: Stacked widget for switching plot type.
        viewers: Dict of NDArrayViewer objects.

    Signals:
        dataClicked(index): The data point at index is clicked. The index is
          in general a tuple since the data can be n-dimension.
    """

    dataClicked = pyqtSignal(tuple)

    class PlotType(enum.IntEnum):
        """Main plot type.

        This is used as the index of the stacked widget.
        
        Members:
            CURVE: Linear curve plot style which is for 1D data.
            IMAGE: Color-mapped image style which is for 2D data.
        """
        CURVE = 0
        IMAGE = 1

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.viewers: Dict[MainPlotWidget.PlotType, NDArrayViewer] = {
            MainPlotWidget.PlotType.CURVE: CurvePlotViewer(),
            MainPlotWidget.PlotType.IMAGE: ImageViewer(),
        }
        self.stack = QStackedWidget(self)
        for plotType in MainPlotWidget.PlotType:
            self.stack.addWidget(self.viewers[plotType].widget)
        layout = QHBoxLayout(self)
        layout.addWidget(self.stack)
        # signal connection
        for viewer in self.viewers.values():
            viewer.plotItem.scene().sigMouseClicked.connect(
                functools.partial(self._mouseClicked, viewer),
            )

    def setData(self, data: np.ndarray, axes: Sequence[AxisInfo]):
        """Sets the data to plot.

        If the dimension of data is 1, CURVE plot will be shown. If it is 2,
          IMAGE plot will be shown.
        
        Args:
            data, axes: See NDArrayViewer.setData().
        """
        if data.ndim == 1:
            plotType = MainPlotWidget.PlotType.CURVE
        elif data.ndim == 2:
            plotType = MainPlotWidget.PlotType.IMAGE
        else:
            logger.error("MainPlotWidget does not support %d-dim data", data.ndim)
            return
        self.viewers[plotType].setData(data, axes)
        self.stack.setCurrentIndex(plotType)

    def _mouseClicked(self, viewer: NDArrayViewer, event: mouseEvents.MouseClickEvent):
        """Mouse is clicked on the plot.
        
        Args:
            viewer: The source of the event.
            event: Mouse click event object.
        """
        index = viewer.nearestDataPoint(event.scenePos(), tolerance=20)
        if index is not None:
            self.dataClicked.emit(index)


class DataViewerFrame(QSplitter):
    """Frame for data viewer app.
    
    Attributes:
        sourceWidget: SourceWidget for source selection.
        dataPointWidget: DataPointWidget for data point configuration.
        mainPlotWidget: MainPlotWidget for the main plot.
    """

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        sourceBox = QGroupBox("Source", self)
        dataPointBox = QGroupBox("Data point", self)
        mainPlotBox = QGroupBox("Main plot", self)
        toolBox = QGroupBox("Tools", self)
        self.sourceWidget = SourceWidget(self)
        self.dataPointWidget = DataPointWidget(self)
        self.mainPlotWidget = MainPlotWidget(self)
        QHBoxLayout(sourceBox).addWidget(self.sourceWidget)
        QHBoxLayout(dataPointBox).addWidget(self.dataPointWidget)
        QHBoxLayout(mainPlotBox).addWidget(self.mainPlotWidget)
        leftWidget = QWidget(self)
        leftLayout = QVBoxLayout(leftWidget)
        leftLayout.addWidget(sourceBox)
        leftLayout.addWidget(dataPointBox)
        self.addWidget(leftWidget)
        self.addWidget(mainPlotBox)
        self.addWidget(toolBox)


class DataViewerApp(qiwis.BaseApp):
    """App for data visualization.
    
    Attributes:
        dataViewerFrame: DataViewerFrame instance.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.dataViewerFrame = DataViewerFrame()

    def frames(self) -> Tuple[DataViewerFrame]:
        """Overridden."""
        return (self.dataViewerFrame,)
