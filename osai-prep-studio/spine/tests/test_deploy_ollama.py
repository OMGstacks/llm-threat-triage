"""Deploy/compose guards for the Ollama chat-family realism labs (L03-L07).

Enforces the acceptance gate mechanically and stdlib-only (no PyYAML in CI): the new
lab targets stay INTERNAL (expose only, on labnet — no host-published ports), the
overlay keeps exactly ONE shared model server, and no model weight blobs are ever
committed to the repo. These run in the zero-dependency spine CI job."""

import os
from pathlib import Path

DEPLOY = Path(__file__).resolve().parents[1] / "deploy"
BASE = DEPLOY / "docker-compose.yml"
OVERLAY = DEPLOY / "docker-compose.ollama.yml"
NEW_TARGETS = ["labtarget-l03", "labtarget-l04", "labtarget-l05", "labtarget-l06", "labtarget-l07"]


def _service_block(text: str, name: str) -> str:
    """Return the lines of a top-level (2-space-indented) compose service block."""
    out, capturing = [], False
    for line in text.splitlines():
        is_service_header = (
            line.startswith("  ") and not line.startswith("   ") and line.strip().endswith(":")
        )
        if is_service_header:
            capturing = line.strip() == f"{name}:"
            continue
        if capturing:
            if line and not line.startswith(" "):  # a new top-level key (networks:, volumes:)
                break
            out.append(line)
    return "\n".join(out)


def test_new_lab_targets_are_internal_with_no_host_published_ports():
    text = BASE.read_text(encoding="utf-8")
    for name in NEW_TARGETS:
        block = _service_block(text, name)
        assert block.strip(), f"{name} is missing from the base compose"
        assert "- labnet" in block, f"{name} must be on the internal labnet"
        # the core correction: no default host-published ports — expose (labnet-only) only
        assert "ports:" not in block, f"{name} must NOT host-publish ports (use expose)"
        assert "expose:" in block, f"{name} should expose its internal port"
        # keep the same hardening as the existing targets
        assert "no-new-privileges:true" in block and "cap_drop" in block


def test_overlay_keeps_one_shared_server_and_enables_ollama_for_new_targets():
    text = OVERLAY.read_text(encoding="utf-8")
    # exactly one runtime model server + one one-shot puller — never a per-lab server
    assert text.count("image: ollama/ollama") == 2
    for name in NEW_TARGETS:
        block = _service_block(text, name)
        assert block.strip(), f"{name} missing from the ollama overlay"
        assert 'OSAI_OLLAMA: "1"' in block
        assert "http://ollama:11434" in block  # the single shared server


def test_no_model_weight_blobs_committed():
    """No model weights in git — the weights live only in the ollama-models volume."""
    root = Path(__file__).resolve().parents[3]  # repo root
    bad_ext = {".gguf", ".bin", ".safetensors", ".pt", ".pth", ".onnx"}
    skip_dirs = {".git", "node_modules", ".next", "__pycache__", ".mypy_cache", ".pytest_cache"}
    offenders = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for fn in filenames:
            if Path(fn).suffix.lower() in bad_ext:
                offenders.append(os.path.relpath(os.path.join(dirpath, fn), root))
    assert not offenders, f"model weight blobs must not be committed: {offenders}"
