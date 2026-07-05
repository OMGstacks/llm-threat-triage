"""osai-narrate — a portable, offline-first, provider-agnostic narrated-lesson renderer.

Shared across course projects so voice / avatar / render upgrades land once and every
course that depends on the package inherits them. Public API is re-exported from ``core``.
"""

from . import core, redaction  # noqa: F401
from .core import *  # noqa: F401,F403

__version__ = "0.1.0"
