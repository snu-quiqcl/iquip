import logging
from typing import Dict, Optional, Tuple

from PyQt5.QtCore import QObject

import qiwis

logger = logging.getLogger(__name__)


RPCTargetInfo = Tuple[str, int, str]  # ip, port, target_name


class StageControllerApp(qiwis.BaseApp):
    """App for monitoring and controlling motorized stages.
    
    Attributes:

    """

    def __init__(
        self,
        name: str,
        stages: Dict[str, RPCTargetInfo],
        parent: Optional[QObject] = None,
    ):
        """Extended.
        
        Args:
            stages: Dictionary of stage information. Each key is the name of the
              stage and the value is its RPC target information.
        """
        super().__init__(name, parent=parent)
