"""App module for visualizing the experiment code."""

from typing import Optional

from PyQt5.QtCore import QObject

import qiwis

class VisualizerApp(qiwis.BaseApp):
    """App for showing the code viewer and the sequence viewer."""

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)
