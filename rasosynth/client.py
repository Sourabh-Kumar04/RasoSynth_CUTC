"""
Compatibility shim for rasosynth.client.

Canonical implementation lives in rasosynthtune.client; this module
re-exports the identical objects.
"""
from rasosynthtune.client import RasoSynthClient, JobResult, DBOMAttestation

__all__ = ["RasoSynthClient", "JobResult", "DBOMAttestation"]
