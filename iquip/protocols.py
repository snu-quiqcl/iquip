"""Protocol module for defining common forms."""

import dataclasses
from typing import Any, Dict, Optional

@dataclasses.dataclass
class ExperimentInfo:
    """Experiment information.
    
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
    """Submitted experiment information.
    
    Fields:
        rid: The run identifier value.
        status: The current status; "preparing", "running", "run_done", etc.
        priority: Higher value means sooner scheduling.
        pipeline: The pipeline to run the experiment in.
        due_date: The date time string in ISO format.
        file: The experiment file path.
        arguments: The passed build arguments.
    """
    rid: int
    status: str
    priority: int
    pipeline: str
    due_date: Optional[str]
    file: str
    arguments: Dict[str, Any]
