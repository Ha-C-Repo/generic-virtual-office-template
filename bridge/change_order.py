"""bridge/change_order.py - compatibility shim (MC-04 fix).

This module re-exports everything from ``bridge.agents.change_order``.
Older code and external callers expect the change-order agent at
``bridge.change_order``; the actual implementation lives at
``bridge.agents.change_order``. This shim preserves the public surface
without duplicating logic.
"""

from bridge.agents.change_order import *  # noqa: F401,F403
from bridge.agents import change_order as _impl

# Explicit re-export of common attributes so static analyzers see them.
TASK_RATES = _impl.TASK_RATES
SHOP_RATE = _impl.SHOP_RATE
DEFAULT_MARKUP = _impl.DEFAULT_MARKUP
DB_PATH = _impl.DB_PATH

__all__ = [n for n in dir(_impl) if not n.startswith("_")]
