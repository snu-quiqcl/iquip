import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

import iquip.apps.dataviewer as dv

class DemoWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.histogram = dv.HistogramViewer(title="Histogram demo", labels={"left": ("# events",)})
        self.image = dv.ImageViewer(title="Image demo")
        self.button = QPushButton("Update")
        self.button.clicked.connect(self.updatePlot)
        layout = QVBoxLayout(self)
        layout.addWidget(self.histogram.widget)
        layout.addWidget(self.image.widget)
        layout.addWidget(self.button)

    def updatePlot(self):
        # histogram
        axis = dv.AxisInfo("Photon count", range(10))
        data = np.random.randint(0, 10, 10)
        self.histogram.setData(data, (axis,))
        # image
        vaxis = dv.AxisInfo("Vertical", np.linspace(2.76e-3, 6.76e-3, 5), "m")
        haxis = dv.AxisInfo("Horizontal", np.linspace(5.5e-3, 6.5e-3, 10), "m")
        data = np.random.randint(0, 10, (5, 10))
        self.image.setData(data, (vaxis, haxis))
        self.image.widget.autoRange()


qapp = QApplication([])
widget = DemoWidget()
widget.show()
qapp.exec_()
