"""App module for data viewers which displays result data using plot, etc."""

import dataclasses
import logging
from typing import Iterable

logger = logging.getLogger(__name__)


@dataclasses.dataclass
class AxisInfo:
    """Axis information of NDArray data."""
    name: str
    unit: str
    values: Iterable
