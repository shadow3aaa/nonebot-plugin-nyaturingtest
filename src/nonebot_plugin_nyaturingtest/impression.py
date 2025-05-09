from dataclasses import dataclass
from datetime import datetime


@dataclass
class Impression:
    """
    记录某次互动带来的印象
    """

    timestamp: datetime
    delta: dict
