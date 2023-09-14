import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

import iquip.apps.dataviewer as dv

class DemoWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.viewer = dv.HistogramViewer(title="Demo", labels={"left": ("# events",)})
        self.button = QPushButton("Update")
        self.button.clicked.connect(self.updatePlot)
        layout = QVBoxLayout(self)
        layout.addWidget(self.viewer.plotWidget)
        layout.addWidget(self.button)

    def updatePlot(self):
        axis = dv.AxisInfo("Photon count", range(10))
        data = np.random.randint(0, 10, 10)
        self.viewer.setData(data, (axis,))


qapp = QApplication([])
widget = DemoWidget()
widget.show()
qapp.exec_()
