import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QPushButton, QVBoxLayout

import iquip.apps.dataviewer as dv

class DemoWidget(QWidget):

    def __init__(self):
        super().__init__()
        self.viewer = dv.CurvePlotViewer(title="Demo", labels={"left": ("Voltage", "V")})
        self.button = QPushButton("Update")
        self.button.clicked.connect(self.updatePlot)
        layout = QVBoxLayout(self)
        layout.addWidget(self.viewer.plotWidget)
        layout.addWidget(self.button)

    def updatePlot(self):
        axis = dv.AxisInfo("time", (0, 1e-6, 2e-6, 3e-6), "s")
        data = np.random.randint(1, 4, 4) * 1e-3
        self.viewer.setData(data, (axis,))


qapp = QApplication([])
widget = DemoWidget()
widget.show()
qapp.exec_()
