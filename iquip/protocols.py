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
    arginfo: Dict[str, Any]


@dataclasses.dataclass
class SubmittedExperimentInfo:
    """Information holder for submitted experiments.
    
    Fields:
        rid: The run identifier value of the experiment.
        priority: The priority of the experiment.
        status: Current state of the experiment.
        pipeline: The pipeline of the experiment.
        expid: The overall information of the experiment, 
          which is a dictionary that may include arguments, file, etc.
        due_date: The due date of the experiment.
    """
    rid: int
    priority: int = 0
    status: str = ""
    pipeline: str = ""
    expid: Dict[str, Any] = dataclasses.field(default_factory = dict)
    due_date: str = ""

    def items(self) -> Any:
        """Returns the attributes of the experiment."""
        return self.__dict__.items()

    def __eq__(self, other: Any):
        """Overridden."""
        if not isinstance(other, SubmittedExperimentInfo):
            return False
        return self.rid == other.rid
