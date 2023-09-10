"""App module for showing the code and sequence viewer."""

from typing import Optional

from PyQt5.QtCore import QObject

import qiwis

class VisualizerApp(qiwis.BaseApp):
    """App for showing the code and sequence viewer."""

    def __init__(self, name: str, parent: Optional[QObject] = None):
        """Extended."""
        super().__init__(name, parent=parent)