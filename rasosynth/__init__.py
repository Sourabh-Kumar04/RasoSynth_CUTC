"""
Compatibility shim for the historical rasosynth package name.

Canonical home of the SDK is rasosynthtune. This package re-exports the
identical objects so existing imports keep working unchanged.
"""

from rasosynthtune.client import RasoSynthClient, JobResult, DBOMAttestation

__version__ = "2.0.0"
__all__ = ["RasoSynthClient", "JobResult", "DBOMAttestation"]
