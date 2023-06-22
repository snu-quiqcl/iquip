"""Protocol module for defining common forms."""

import dataclasses
from typing import Any, Dict

@dataclasses.dataclass
class ExperimentInfo:
    """Experiment Information.
    
    Fields:
        name: The experiment name which is set as the docstring in the experiment file.
        arginfo: The dictionary containing arguments of the experiment.
          Each key is an argument name and its value contains the argument type,
          the default value, and the additional information for the argument.
    """
    name: str
    argInfo: Dict[str, Any]
