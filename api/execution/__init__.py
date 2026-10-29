"""
API Execution Package (P0: executor removed).

The former api/execution/executor.py (AsyncJobExecutor, ProgressTracker,
ResumableWorkflow, WebhookNotifier) was DELETED: its "execution" was
asyncio.sleep calls that reported steps as completed and its webhook
sender slept 0.01s without ever sending anything. Nothing in the codebase
wired it to real execution (the canonical server only imported two of its
names and never used them). Real execution lives in the dataset
orchestrator (core/orchestrator_core.py) and the fine-tune job manager
(finetuning/job_manager.py). Do not reintroduce a simulated executor
under this package name.
"""

__all__ = []
