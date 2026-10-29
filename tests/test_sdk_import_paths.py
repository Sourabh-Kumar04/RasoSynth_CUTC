"""Both SDK import paths resolve to the identical objects.

Canonical: rasosynthtune. Compatibility shim: rasosynth.
"""
import rasosynth
import rasosynth.client
import rasosynthtune
import rasosynthtune.client


def test_both_packages_export_identical_objects():
    assert rasosynth.RasoSynthClient is rasosynthtune.RasoSynthClient
    assert rasosynth.JobResult is rasosynthtune.JobResult
    assert rasosynth.DBOMAttestation is rasosynthtune.DBOMAttestation
    assert rasosynth.client.RasoSynthClient is rasosynthtune.client.RasoSynthClient
    assert rasosynth.client.JobResult is rasosynthtune.client.JobResult
    assert rasosynth.client.DBOMAttestation is rasosynthtune.client.DBOMAttestation


def test_both_packages_agree_on_version():
    assert rasosynth.__version__ == rasosynthtune.__version__ == "2.0.0"
