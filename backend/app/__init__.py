"""Supply-order delivery analysis.

Turns raw purchase-order dates into observation rows measured at a chosen
as-of date, then estimates the time-to-delivery distribution with Kaplan–Meier.
"""

from .analysis import analyse
from .data import connect, load_orders
from .km import KMResult, km_from_observations
from .model import Observation, build_observations
