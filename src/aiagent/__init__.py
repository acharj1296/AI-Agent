"""Autonomous AI software company - control plane (modular monolith).

Modules are deliberately passive at this stage; the modular boundary that the
planning documents require is established by the package layout and enforced by
linting (see docs/plan/30_FOLDER_STRUCTURE.md).
"""

from aiagent.version import __version__

__all__ = ["__version__"]
