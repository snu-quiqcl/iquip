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
class ConfigurationInfo:
    """lolenc Configuartion Information.
    
    Fields:
        common_path: The common absolute path for the project.
        ip: The IP address of the board.
        port: The port number of the board.
        xilinx_include_path: The relative path to the Xilinx include directory.
        bsp_src_path: The relative path to the BSP source directory. All files 
            in this directory will be compiled and linked with actual application file.
        bsp_include_path: The relative path to the BSP include directory. Header files
            in this directory will be used as a header files in the bsp_src_path.
        bsp_lib_path: The relative path to the BSP library directory. Compiled bsp source
            files will be made as a library file in this directory.
        startup_path: The relative path to the startup file. This file will be used as a
            startup file in the linker file. (*.S)
        linker_path: The relative path to the linker file. (*.ld)
        compile_driver: Option for the compile driver.(True or False)
        device_config: The absolute path of device configuration file. (*.cpp)
        device_db: The absolute path of device database file. (*.json)
        log_path: The absolute path of path to the log file.
    """
    common_path: str
    ip: str
    port: str
    xilinx_include_path: str
    bsp_src_path: str
    bsp_include_path: str
    bsp_lib_path: str
    startup_path: str
    linker_path: str
    compile_driver: str
    device_config: str
    device_db: str
    log_path: str

    def __str__(self) -> str:
        """Overridden."""
        return str(dataclasses.asdict(self))


@dataclasses.dataclass
class SubmittedExperimentInfo:  # pylint: disable=too-many-instance-attributes
    """Submitted experiment information.
    
    Fields:
        rid: The run identifier value.
        status: The current status; "preparing", "running", "run_done", etc.
        priority: Higher value means sooner scheduling.
        pipeline: The pipeline to run the experiment in.
        due_date: The date time string in ISO format.
        file: The experiment file path.
        content: The experiment code. It is set when submitting the experiment code directly.
          One of file and content should be None.
        arguments: The passed build arguments.
    """
    rid: int
    status: str
    priority: int
    pipeline: str
    due_date: Optional[str]
    file: Optional[str]
    content: Optional[str]
    arguments: Dict[str, Any]

    def __str__(self) -> str:
        """Overridden."""
        return str(dataclasses.asdict(self))
