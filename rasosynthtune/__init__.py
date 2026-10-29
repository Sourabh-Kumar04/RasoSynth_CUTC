"""
RasoSynthTune - Autonomous AI Dataset Synthesis & Fine-Tuning Platform SDK.

Canonical home of the Python SDK. The historical rasosynth package remains
as a compatibility shim re-exporting these same objects.
"""

from rasosynthtune.client import RasoSynthClient, JobResult, DBOMAttestation

__version__ = "2.0.0"
__all__ = ["RasoSynthClient", "JobResult", "DBOMAttestation"]
