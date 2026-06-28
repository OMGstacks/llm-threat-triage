"""LLM Log Triage — a Technical-Intelligence-Analyst-style toolkit.

Ingests messy LLM interaction logs, normalizes them, and flags adversarial
activity (prompt injection, jailbreaks, data exfiltration, sensitive-data
disclosure) mapped to the OWASP Top 10 for LLM Applications (2025) and
MITRE ATLAS.
"""

__all__ = ["detectors", "normalize", "db", "pipeline", "generate_logs"]
__version__ = "0.1.0"
