"""Narration seam — OSAI now consumes the shared, installable ``osai-narrate`` package
(``osai-prep-studio/packages/osai-narrate``) as the single source of truth, so the
renderer/player and future voice/avatar upgrades are shared across course projects
without code drift (27-narrated-lessons.md · docs/adopting-narrated-lessons.md).

This module is a thin adapter: it re-exports the package's public API so every existing
caller (``osai_spine.cli`` and the tests) keeps working unchanged. The env-var aliases in
the package mean ``OSAI_TTS*`` still work exactly as before.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Monorepo resolution: make the co-located package importable without a separate install.
# When ``osai-narrate`` is pip-installed (e.g. in another repo), this is a harmless no-op.
_PKG = Path(__file__).resolve().parents[2] / "packages" / "osai-narrate"
if _PKG.is_dir() and str(_PKG) not in sys.path:
    sys.path.insert(0, str(_PKG))

from osai_narrate.core import (  # noqa: E402,F401 — re-export the public API unchanged
    DEFAULT_PROVIDER,
    DEFAULT_VOICE,
    PROVIDERS,
    cache_key,
    key_present,
    key_source,
    parse_script,
    provider_available,
    provider_kind,
    provider_name,
    rate_per_million,
    render_enabled,
    render_segment,
    render_plan,
    status,
    to_vtt,
    write_manifest,
)
