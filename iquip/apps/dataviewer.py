# pylint: disable=too-many-lines
"""App module for data viewers which displays result data using plot, etc."""

import abc
import dataclasses
import enum
import functools
import json
import logging
from typing import (
    Any, List, Dict, Tuple, Sequence, Iterable, Callable, Optional, Union,
)

import numpy as np
import pyqtgraph as pg
import qiwis
from pyqtgraph.GraphicsScene import mouseEvents
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QRadioButton, QButtonGroup, QStackedWidget,
    QAbstractSpinBox, QSpinBox, QDoubleSpinBox, QGroupBox, QSplitter,
    QCheckBox, QComboBox, QHBoxLayout, QVBoxLayout, QGridLayout,
)
from PyQt5.QtCore import pyqtSignal, pyqtSlot, QMutex, QObject, QThread, Qt, QWaitCondition
from websockets.sync.client import connect, ClientConnection
from websockets.exceptions import ConnectionClosedOK, WebSocketException

logger = logging.getLogger(__name__)

MAX_INT = 2**31 - 1

def p_1(threshold: int, array: np.ndarray) -> float:
    """Returns P1 given threshold and photon count array.
    
    Args:
        threshold: If the photon count is strictly greater than threshold, it is
          taken as 1 state.
        array: The array of photon counts.
    """
    return np.sum(array > threshold) / array.size


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

    def highlight(self, index: Optional[Tuple[int, ...]]):
        """Highlights the data point at the given index.

        Args:
            index: Data point index to highlight. None for removing the highlight.
        """


class CurvePlotViewer(NDArrayViewer):  # pylint: disable=too-few-public-methods
    """Plot viewer for visualizing a 2D curve.
    
    Attributes:
        widget: The PlotWidget which contains the plotItem.
        curve: The PlotDataItem which represents the curve plot.
        lines: The highlight vertical and horizontal lines. None if there is no
          lines currently.
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
        self.lines: Optional[Tuple[pg.InfiniteLine, pg.InfiniteLine]] = None

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

    def highlight(self, index: Optional[Tuple[int]]):
        """Overridden.
        
        A vertical and a horizontal lines appear at the data point.
        If there was already a highlight lines, they move to the new point, i.e.,
          there are at most one highlighted data point at once.
        """
        if index is None:
            if self.lines is not None:
                for line in self.lines:
                    self.plotItem.removeItem(line)
                self.lines = None
            return
        i = index[0]
        x, y = self.curve.getOriginalDataset()
        if self.lines is None:
            vline = self.plotItem.addLine(x=x[i])
            hline = self.plotItem.addLine(y=y[i])
            self.lines = (vline, hline)
        else:
            vline, hline = self.lines
            vline.setPos(x[i])
            hline.setPos(y[i])


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
        syncButton: Button for start/stop synchronization. When the button is clicked,
          it is disabled. It should be manually enabled after doing proper works.
        periodSpinBox: Spinbox for period of fetching a dataset.
        label: Status label for showing status including errors.
    
    Signals:
        syncToggled(checked): Synchronize button is clicked with the current
          checked state (True for start sync, False for stop).
    """

    syncToggled = pyqtSignal(bool)

    def __init__(self, parent: Optional[QWidget] = None):
        """Extended."""
        super().__init__(parent=parent)
        self.syncButton = QPushButton("OFF", self)
        self.syncButton.setCheckable(True)
        self.periodSpinBox = QDoubleSpinBox(self)
        self.periodSpinBox.setSuffix("s")
        self.periodSpinBox.setSingleStep(0.1)
        self.periodSpinBox.setMinimum(0.1)
        self.periodSpinBox.setMaximum(10)
        self.periodSpinBox.setDecimals(1)
        self.periodSpinBox.setValue(1)
        self.label = QLabel(self)
        layout = QHBoxLayout(self)
        layout.addWidget(QLabel("Sync:", self))
        layout.addWidget(self.syncButton)
        layout.addWidget(self.periodSpinBox)
        layout.addWidget(self.label)
        layout.addStretch()
        # signal connection
        self.syncButton.toggled.connect(self._buttonToggled)
        self.syncButton.clicked.connect(functools.partial(self.syncButton.setEnabled, False))
        self.syncButton.clicked.connect(self.syncToggled)

    def setStatus(
        self,
        message: Optional[str] = None,
        sync: Optional[bool] = None,
        enable: Optional[bool] = None,
    ):
        """Sets the status message and synchronization button status.
        
        Args:
            message: New status message to display on the label. None for not changing.
            sync: New button checked status. None for not changing.
            enable: New button enabled status. None for not changing.
        """
        if message is not None:
            self.label.setText(message)
        if sync is not None:
            self.syncButton.setChecked(sync)
        if enable is not None:
            self.syncButton.setEnabled(enable)

    @pyqtSlot(bool)
    def _buttonToggled(self, checked: bool):
        """Called when the button is toggled.
        
        Args:
            checked: Whether the button is now checked.
        """
        self.syncButton.setText("ON" if checked else "OFF")
        self.periodSpinBox.setEnabled(not checked)


class _RemotePart(QWidget):
    """Part widget for configuring remote mode of the source widget.
    
    Attributes:
        spinbox: Spinbox for RID input.
        label: Label for showing the execution time of the experiment.

    Signals:
        ridEditingFinished(rid): The editingFinished signal of spinbox is emitted.
          The current spinbox value is given as rid.
    """

    ridEditingFinished = pyqtSignal(str)

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
        # signal connection
        self.spinbox.editingFinished.connect(self._editingFinished)

    @pyqtSlot()
    def _editingFinished(self):
        """Emits the ridEditingFinished signal with the current RID."""
        self.ridEditingFinished.emit(str(self.spinbox.value()))


class SourceWidget(QWidget):
    """Widget for data source selection.

    Signals:
        axisApplied(axis): Axis parameter selection apply button is clicked.
          See SimpleScanDataPolicy.extract() for axis argument.
        realtimeDatasetUpdateRequested(): The realtime dataset list update
          is requested.

    Attributes:
        datasetBox: The combo box for selecting a dataset.
        axisBoxes: The dict of the combo boxes for selecting the X, Y axis parameter.
          The user must select the X axis before the Y axis. Keys are "X" and "Y".
        axisApplyButton: The button for applying the current axis parameter selection.
        buttonGroup: The radio button group for source selection.
        stack: The stacked widget for additional interface of each source option.
    """

    axisApplied = pyqtSignal(tuple)
    realtimeDatasetUpdateRequested = pyqtSignal()

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
        self.datasetBox = QComboBox(self)
        self.datasetBox.setEditable(True)
        self.datasetBox.lineEdit().setPlaceholderText("Dataset")
        self.datasetBox.setInsertPolicy(QComboBox.NoInsert)
        self.axisBoxes = {axis: QComboBox(self) for axis in "XY"}
        self.axisBoxes["Y"].setEnabled(False)
        self.axisApplyButton = QPushButton("Apply", self)
        datasetLayout = QHBoxLayout()
        datasetLayout.addWidget(self.datasetBox)
        for axis, combobox in self.axisBoxes.items():
            combobox.setPlaceholderText("(Disabled)")
            datasetLayout.addWidget(QLabel(f"{axis}:", self))
            datasetLayout.addWidget(combobox)
        datasetLayout.addWidget(self.axisApplyButton)
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
        sourceLayout = QHBoxLayout()
        sourceLayout.addLayout(buttonGroupLayout)
        sourceLayout.addWidget(self.stack)
        layout = QVBoxLayout(self)
        layout.addLayout(datasetLayout)
        layout.addLayout(sourceLayout)
        self.axisBoxes["X"].currentIndexChanged.connect(self._handleXIndexChanged)
        self.axisApplyButton.clicked.connect(self._handleApplyClicked)
        self.buttonGroup.idClicked.connect(self.stack.setCurrentIndex)

    def setParameters(self, parameters: Iterable[str], units: Iterable[Optional[str]]):
        """Sets the parameter and unit list.

        This resets the current axis selection combo boxes and updates their items.
        If the previously selected names are in the new parameter set
          (as well as the unit), then it preserves the selected parameter names.
        Since it simulates selecting X and then Y, if the previous X is not in
          the new parameter set, Y is not preserved even if the previous Y is.
        
        Args:
            See SimpleScanDataPolicy.
        """
        previousText: Dict[str, str] = {}
        for axis, combobox in self.axisBoxes.items():
            if combobox.currentIndex() >= 0:
                previousText[axis] = combobox.currentText()
        items = [parameter if unit is None else f"{parameter} ({unit})"
                 for parameter, unit in zip(parameters, units)]
        for axis in "YX":
            self.axisBoxes[axis].clear()
            self.axisBoxes[axis].addItems(items)
        for axis, text in previousText.items():
            self.axisBoxes[axis].setCurrentText(text)
        self._handleApplyClicked()

    @pyqtSlot(int)
    def _handleXIndexChanged(self, index: int):
        """Called when X axis combobox index is changed.
        
        It updates the Y axis combobox status properly.

        Args:
            index: Currently selected combobox item index.
        """
        xBox, yBox = self.axisBoxes.values()
        if index < 0:
            yBox.setCurrentIndex(-1)
            yBox.setEnabled(False)
            return
        yBox.setEnabled(True)
        for i in range(xBox.count()):
            yBox.model().item(i).setEnabled(i != index)
        if index == yBox.currentIndex():
            yBox.setCurrentIndex(-1)

    @pyqtSlot()
    def _handleApplyClicked(self):
        """Called when the axis parameter apply button is clicked."""
        xBox, yBox = self.axisBoxes.values()
        x, y = xBox.currentIndex(), yBox.currentIndex()
        if x < 0:
            axis = ()
        elif y < 0:
            axis = (x,)
        else:
            axis = (y, x)
        self.axisApplied.emit(axis)


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

    def setHistogramData(self, bins: Sequence[int], counts: np.ndarray):
        """Sets the histogram data.
        
        Args:
            bins: The X axis data of the histogram.
            counts: The Y axis data of the histogram. The length should be equal
              to that of bins.
        """
        axes = (AxisInfo("Photon count", bins),)
        self.histogram.setData(counts, axes)

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
        autoRangeBox: Check box for toggling auto ranging.

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
        self.autoRangeBox = QCheckBox("Auto-range (X)", self)
        layout = QVBoxLayout(self)
        layout.addWidget(self.autoRangeBox)
        layout.addWidget(self.stack)
        # signal connection
        for viewer in self.viewers.values():
            viewer.plotItem.scene().sigMouseClicked.connect(
                functools.partial(self._mouseClicked, viewer),
            )

    def viewer(self) -> NDArrayViewer:
        """Returns the current viewer."""
        return self.viewers[self.stack.currentIndex()]

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
        if self.autoRangeBox.isChecked():
            plotItem = self.viewers[plotType].plotItem
            bounds = plotItem.getViewBox().childrenBoundingRect(items=None)
            plotItem.setXRange(bounds.left(), bounds.right())
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
    
    Signals:
        syncToggled(checked): See _RealtimePart.syncToggled.
        dataRequested(rid): Data for the given rid is requested.
    """

    syncToggled = pyqtSignal(bool)
    dataRequested = pyqtSignal(str)

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
        # signal connection
        remotePart = self.sourceWidget.stack.widget(SourceWidget.ButtonId.REMOTE)
        remotePart.ridEditingFinished.connect(self.dataRequested)
        realtimePart = self.sourceWidget.stack.widget(SourceWidget.ButtonId.REALTIME)
        realtimePart.syncToggled.connect(self.syncToggled)

    def datasetName(self) -> str:
        """Returns the current dataset name in the line edit."""
        return self.sourceWidget.datasetBox.currentText()


class _DatasetListThread(QThread):
    """QThread for fetching the list of available datasets.
    
    Signals:
        fetched(datasets): Fetched the dataset name list.
    
    Attributes:
        url: The web socket url.
    """

    fetched = pyqtSignal(list)

    def __init__(self, ip: str, port: int, parent: Optional[QObject] = None):
        """Extended.
        
        Args:
            ip: IP address of the proxy server.
            port: PORT number of the proxy server.
        """
        super().__init__(parent=parent)
        self.url = f"ws://{ip}:{port}/dataset/master/list/"

    def _filter(self, names: List[str]) -> List[str]:
        """Returns a new list excluding "*.parameters" and "*.units".
        
        Args:
            names: Dataset name list which includes "*.parameters" and "*.units".
        """
        return [name for name in names if not name.endswith((".parameters", ".units"))]

    def run(self):
        """Overridden."""
        try:
            with connect(self.url) as websocket:
                for response in websocket:
                    self.fetched.emit(self._filter(json.loads(response)))
        except WebSocketException:
            logger.exception("Failed to fetch the schedule.")


class _DatasetFetcherThread(QThread):
    """QThread for fetching the dataset from the proxy server.
    
    Signals:
        initialized(dataset, parameters, units): Full dataset is fetched providing
          the initialization information for the dataset.
          See `SimpleScanDataPolicy` for argument description.
        modified(modifications): Dataset modifications are fetched.
          The argument modifications is a list of dictionary.
          See mod dictionary in sipyco.sync_struct for its structure.
        stopped(cause): The thread is stopped with a cause message.
    
    Attributes:
        info: Dictionary sent to the server in the beginning of the connection. It has two keys;
          "name" for target dataset name and "period" for period of fetching the dataset in seconds.
        url: The web socket url.
        websocket: The web socket object.
        mutex: Mutex for wait condition modifyDone.
        modifyDone: Wait condition which should be notified when the dataset
          modification is done by the main GUI thread.
    """

    initialized = pyqtSignal(np.ndarray, list, list)
    modified = pyqtSignal(list)
    stopped = pyqtSignal(str)

    def __init__(
        self,
        name: str,
        period: float,
        ip: str,
        port: int,
        parent: Optional[QObject] = None
    ):  # pylint: disable=too-many-arguments
        """Extended.
        
        Args:
            name, period: See info in the attributes section.
            ip: IP address of the proxy server.
            port: PORT number of the proxy server.
        """
        super().__init__(parent=parent)
        self.info = {"name": name, "period": period}
        self.url = f"ws://{ip}:{port}/dataset/master/modification/"
        self.websocket: ClientConnection
        self.mutex = QMutex()
        self.modifyDone = QWaitCondition()

    def _initialize(self):
        """Fetches the target dataset to initialize the local dataset."""
        self.websocket = connect(self.url)
        self.websocket.send(json.dumps(self.info))
        rawDataset = json.loads(self.websocket.recv())
        dataset = np.array(rawDataset)
        numParameters = dataset.shape[1] if dataset.ndim > 1 else 0
        parameters = json.loads(self.websocket.recv())
        if not parameters:
            parameters = list(map(str, range(numParameters)))
        rawUnits = json.loads(self.websocket.recv())
        if rawUnits:
            units = [unit if unit else None for unit in rawUnits]
        else:
            units = [None] * numParameters
        self.initialized.emit(dataset, parameters, units)

    def stop(self):
        """Stops the thread."""
        try:
            self.websocket.close()
        except WebSocketException:
            logger.exception("Failed to stop synchronizing.")

    def run(self):
        """Overridden."""
        try:
            self._initialize()
            while True:
                modifications = json.loads(self.websocket.recv())
                if modifications:
                    self.mutex.lock()
                    self.modified.emit(modifications)
                    self.modifyDone.wait(self.mutex)
                    self.mutex.unlock()
                else:  # dataset is overwritten or removed
                    self.websocket.close()
                    self._initialize()
        except ConnectionClosedOK:
            self.stopped.emit("Stopped synchronizing.")
        except WebSocketException:
            msg = "Failed to synchronize the dataset."
            self.stopped.emit(msg)
            logger.exception(msg)


class DataViewerApp(qiwis.BaseApp):
    """App for data visualization.
    
    Attributes:
        frame: DataViewerFrame instance.
        fetcherThread: The most recently executed _DatasetFetcherThread instance.
        listThread: The most recently executed _DatasetListThread instance.
        policy: Data policy instance. None if there is currently no data.
        axis: The current plot axis parameter indices. See SimpleScanDataPolicy.extract().
        dataPointIndex: The most recently selected data point index.
    """

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
        self.frame = DataViewerFrame()
        self.fetcherThread: Optional[_DatasetFetcherThread] = None
        self.listThread: Optional[_DatasetListThread] = None
        self.policy: Optional[SimpleScanDataPolicy] = None
        self.axis: Tuple[int, ...] = ()
        self.dataPointIndex: Tuple[int, ...] = ()
        self.startDatasetListThread()
        self.frame.syncToggled.connect(self._toggleSync)
        self.frame.sourceWidget.axisApplied.connect(self.setAxis)
        self.frame.dataPointWidget.dataTypeChanged.connect(self.setDataType)
        self.frame.dataPointWidget.thresholdChanged.connect(self.setThreshold)
        self.frame.mainPlotWidget.dataClicked.connect(self.selectDataPoint)

    def startDatasetListThread(self):
        """Creates and starts a new _DatasetListThread instance."""
        self.listThread = _DatasetListThread(
            self.constants.proxy_ip,  # pylint: disable=no-member
            self.constants.proxy_port,  # pylint: disable=no-member
        )
        self.listThread.fetched.connect(self._updateDatasetBox)
        self.listThread.finished.connect(self.listThread.deleteLater)
        self.listThread.start()

    @pyqtSlot(list)
    def _updateDatasetBox(self, datasets: List[str]):
        """Updates the dataset box with the new dataset name list.
        
        Args:
            datasets: The new dataset name list.
        """
        box = self.frame.sourceWidget.datasetBox
        currentName = box.currentText()
        box.clear()
        box.addItems(datasets)
        if currentName in datasets:
            box.setCurrentText(currentName)

    @pyqtSlot(bool)
    def _toggleSync(self, checked: bool):
        """Toggles the synchronization state.
        
        Args:
            checked: True for starting synchronization, False for stopping.
        """
        if checked:
            self.synchronize()
        else:
            self.fetcherThread.stop()

    @pyqtSlot()
    def synchronize(self):
        """Fetches the dataset from artiq master and updates the viewer."""
        realtimePart: _RealtimePart = self.frame.sourceWidget.stack.widget(
            SourceWidget.ButtonId.REALTIME
        )
        realtimePart.setStatus(message="Start synchronizing.")
        self.fetcherThread = _DatasetFetcherThread(
            self.frame.datasetName(),
            realtimePart.periodSpinBox.value(),
            self.constants.proxy_ip,  # pylint: disable=no-member
            self.constants.proxy_port,  # pylint: disable=no-member
        )
        self.fetcherThread.initialized.connect(self.setDataset, type=Qt.QueuedConnection)
        self.fetcherThread.modified.connect(self.modifyDataset, type=Qt.QueuedConnection)
        self.fetcherThread.stopped.connect(realtimePart.setStatus, type=Qt.QueuedConnection)
        self.fetcherThread.finished.connect(
            functools.partial(realtimePart.setStatus, sync=False, enable=True),
            type=Qt.QueuedConnection,
        )
        self.fetcherThread.finished.connect(self.fetcherThread.deleteLater)
        self.fetcherThread.start()
        realtimePart.setStatus(enable=True)

    @pyqtSlot(np.ndarray, list, list)
    def setDataset(
        self,
        dataset: np.ndarray,
        parameters: List[str],
        units: List[Optional[str]],
    ):
        """Sets the dataset to show and updates the axis viewer.
        
        Args:
            See SimpleScanDataPolicy.
        """
        self.policy = SimpleScanDataPolicy(dataset, parameters, units)
        self.frame.sourceWidget.setParameters(parameters, units)

    @pyqtSlot(list)
    def modifyDataset(self, modifications: List[Dict[str, Any]]):
        """Modifies the dataset and updates the plot.

        Args:
            See _DatasetFetcherThread.modified signal.
        """
        # TODO(kangz12345@snu.ac.kr): Implement modifications other than "append".
        if self.policy is None:
            logger.error("Tried to modify data when data policy is None.")
            return
        appended = np.vstack(tuple(m["x"] for m in modifications if m["action"] == "append"))
        if self.policy.dataset.size == 0:
            self.policy.dataset = appended
        else:
            self.policy.dataset = np.concatenate((self.policy.dataset, appended))
        if self.axis:
            self.updateMainPlot(self.axis, self.frame.dataPointWidget.dataType())
        self.fetcherThread.mutex.lock()
        self.fetcherThread.mutex.unlock()
        self.fetcherThread.modifyDone.wakeAll()

    @pyqtSlot(tuple)
    def setAxis(self, axis: Sequence[int]):
        """Given the axis information, draws the main plot.
        
        Args:
            axis: See updateMainPlot().
        """
        self.axis = axis
        if self.policy is None or self.policy.dataset.size == 0:
            return
        dataType = self.frame.dataPointWidget.dataType()
        self.updateMainPlot(axis, dataType)

    @pyqtSlot(DataPointWidget.DataType)
    def setDataType(self, dataType: DataPointWidget.DataType):
        """Given the data type, draws the main plot.
        
        Args:
            dataType: See updateMainPlot().
        """
        self.updateMainPlot(self.axis, dataType)

    def updateMainPlot(self, axis: Sequence[int], dataType: DataPointWidget.DataType):
        """Updates the main plot.
        
        Args:
            axis: See SimpleScanDataPolicy.extract().
            dataType: Target data type.
        """
        if self.policy is None or not axis:
            return
        reduce = self._reduceFunction(dataType)
        data, axes = self.policy.extract(axis, reduce)
        self.frame.mainPlotWidget.setData(data, axes)
        if data.ndim == 1 and dataType == DataPointWidget.DataType.P1:
            self.frame.mainPlotWidget.viewer().plotItem.setYRange(0, 1)
        index = self.dataPointIndex
        if data.ndim == len(index) and np.all(np.less(index, data.shape)):
            self.selectDataPoint(index)
        else:
            self.selectDataPoint((-1,) * data.ndim)

    def dataPoint(self, index: Tuple[int, ...]) -> np.ndarray:
        """Returns the data array at the given index.
        
        Args:
            index: The index of the target data point, in the dataset array.
        """
        parameters, symbols = self.policy.symbolize(self.axis)
        positive_index = tuple(i % len(p) for i, p in zip(index, parameters))
        data_indices = np.all(symbols.T == positive_index, axis=1)
        return self.policy.dataset[:, 0][data_indices].astype(int)

    @pyqtSlot(tuple)
    def selectDataPoint(self, index: Tuple[int, ...]):
        """Selects a data point at the given index.
        
        Args:
            index: See dataPoint().
        """
        if self.policy is None:
            return
        self.frame.mainPlotWidget.viewer().highlight(index)
        self.dataPointIndex = index
        data = self.dataPoint(index)
        for dataType in DataPointWidget.DataType:
            value = self._reduceFunction(dataType)(data)
            self.frame.dataPointWidget.setValue(value, dataType)
        self.frame.dataPointWidget.setNumberOfSamples(data.size)
        bins, counts = np.unique(data, return_counts=True)
        self.frame.dataPointWidget.setHistogramData(bins, counts)

    @pyqtSlot()
    def setThreshold(self):
        """Updates the p1 value and main plot when the threshold is changed."""
        dataTypeP1 = DataPointWidget.DataType.P1
        if self.frame.dataPointWidget.dataType() is dataTypeP1:
            self.updateMainPlot(self.axis, self.frame.dataPointWidget.dataType())
        data = self.dataPoint(self.index)
        value = self._reduceFunction(dataTypeP1)(data)
        self.frame.dataPointWidget.setValue(value, dataTypeP1)

    def frames(self) -> Tuple[Tuple[str, DataViewerFrame]]:
        """Overridden."""
        return (("", self.frame),)

    def _reduceFunction(
        self,
        dataType: DataPointWidget.DataType,
    )-> Callable[[np.ndarray], float]:
        """Returns the reduce function corresponding to the given data type.
        
        Args:
            dataType: Target data type.
        """
        if dataType == DataPointWidget.DataType.TOTAL:
            return np.sum
        if dataType == DataPointWidget.DataType.AVERAGE:
            return np.mean
        return functools.partial(p_1, self.frame.dataPointWidget.threshold())


class SimpleScanDataPolicy:
    """Data structure policy for simple scan experiments.
    
    Attriutes:
        dataset: The raw data array which should be a 2d array, whose each row
          should be (data, param0, param1, ...) where params are the scan
          parameter values, which may appear on the plot axes.
        parameters: The parameter names in the corresponding order with dataset.
        units: The parameter units corresponding to parameters. A unit can be
          None which stands for unitless.
    """

    def __init__(
        self,
        dataset: np.ndarray,
        parameters: Sequence[str],
        units: Sequence[Optional[str]],
    ):
        """
        Args:
            See attribute section.
        """
        self.dataset = dataset
        self.parameters = parameters
        self.units = units

    def symbolize(self, axis: Iterable[int]) -> Tuple[List[np.ndarray], np.ndarray]:
        """Returns the list of unique parameters and symbolized parameter ndarray.
        
        It first identifies the unique parameter values in the dataset.
        These unique values are called "symbols", and hence the process "symbolize".
        Specifically, symbols are defined by the indices in the unique parameter
          array (params), i.e., the "inverse" of np.unique().
        
        Args:
            axis: Indices of interested axes. The other axes will be reduced.
              Note that the index starts from 0, i.e., the index in paremeters,
              not the dataset column index.
        
        Returns:
            The list of unique parameter values and the symbolized parameter ndarray,
              where each row corresponds to a parameter, i.e., the shape is
              (#parameters, #data).
        """
        params_list: List[np.ndarray] = []
        symbols_list: List[np.ndarray] = []
        for index in axis:
            params, symbols = np.unique(self.dataset[:, index+1], return_inverse=True)
            params_list.append(params)
            symbols_list.append(symbols)
        return params_list, np.vstack(symbols_list)

    # pylint: disable=too-many-locals
    def extract(
        self,
        axis: Sequence[int],
        reduce: Callable[[np.ndarray], Any],
    ) -> Tuple[np.ndarray, List[AxisInfo]]:
        """Returns the reduced data ndarray and axes information.
        
        Args:
            axis: Indices of interested axes. The other axes will be reduced.
              Note that the index starts from 0, i.e., the index in paremeters,
              not the dataset column index.
            reduce: The function for reducing the not-interested axes.
        """
        data = self.dataset[:, 0]  # shape=(N,)
        if not axis:
            return np.array(reduce(data)), []
        params_list, symbol_array = self.symbolize(axis)
        axis_infos: List[AxisInfo] = []
        for dataset_axis, params in zip(axis, params_list):
            axis_info = AxisInfo(
                name=self.parameters[dataset_axis],
                values=params,
                unit=self.units[dataset_axis],
            )
            axis_infos.append(axis_info)
        shape = tuple(map(len, params_list))
        sorted_indices = np.lexsort(np.flip(symbol_array, axis=0))
        sorted_symbols = symbol_array.T[sorted_indices]  # shape=(N, M)
        unique_symbols, unique_indices = np.unique(
            sorted_symbols, return_index=True, axis=0,
        )
        # construct the reduced data array
        data_groups = np.split(data[sorted_indices], unique_indices[1:])
        reduced = np.zeros(shape)
        for index, data_group in zip(unique_symbols, data_groups):
            reduced[tuple(index)] = reduce(data_group)
        return reduced, axis_infos
