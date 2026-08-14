#!/usr/bin/env python3
"""Test WebSocket integration: verify that progress messages are broadcast from the orchestrator."""

import asyncio
import os
import sys
from unittest.mock import Mock, AsyncMock, patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import Settings
from core.db import AsyncDB
from core.orchestrator_core import DatasetOrchestrator, Job, JobStatus
from api.websocket_manager import ConnectionManager, MessageType, WebSocketMessage


class MockSample:
    def __init__(self, instruction, response, input="", metadata=None,
                 quality_score=0.8, difficulty_tier=3):
        self.instruction = instruction
        self.response = response
        self.input = input
        self.metadata_ = metadata or {}
        self.quality_score = quality_score
        self.difficulty_tier = difficulty_tier


def test_websocket_broadcasting():
    """Test that the orchestrator broadcasts progress via WebSocket."""
    print("=== Testing WebSocket Integration ===")

    async def run():
        settings = Settings()
        db = await AsyncDB.create(settings.postgres_url)
        print("✓ Database initialized")

        # Create a mock WebSocket manager that tracks all messages
        ws_manager = MagicMock()
        ws_manager.send_to_job = MagicMock(return_value=asyncio.Future())
        ws_manager.send_to_job.return_value.set_result(1)
        ws_manager.send_to_job = AsyncMock(return_value=1)

        # Create orchestrator with the mock ws_manager
        mock_router = Mock()
        mock_router.initialize = AsyncMock(return_value={'initialized': [], 'failed': []})

        config = settings.model_dump()
        orchestrator = DatasetOrchestrator(config, mock_router, db=db, ws_manager=ws_manager)
        print("✓ Orchestrator initialized with mock WebSocket manager")

        # Create a job
        import uuid
        job_id = str(uuid.uuid4())
        from datetime import datetime
        job = Job(
            id=job_id,
            status=JobStatus.RUNNING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            current_stage="export",
            progress=0.9,
            config={"target_domain": "test"},
        )
        orchestrator.active_jobs[job_id] = job

        # Call _update_job_status (this is called from within pipeline nodes)
        orchestrator._update_job_status(job_id, "export", 0.9, samples_generated=42)
        await asyncio.sleep(0.1)  # give asyncio.create_task time to run

        # Verify the WebSocket was called with a progress message
        assert ws_manager.send_to_job.call_count >= 1, "WebSocket send_to_job was not called"

        # Check the last call
        call = ws_manager.send_to_job.call_args
        job_id_arg, message_arg = call.args
        assert job_id_arg == job_id, f"Expected job_id={job_id}, got {job_id_arg}"
        assert message_arg.type == MessageType.PROGRESS, f"Expected PROGRESS, got {message_arg.type}"
        assert message_arg.data["stage"] == "export", f"Expected stage=export, got {message_arg.data['stage']}"
        assert message_arg.data["progress"] == 0.9, f"Expected progress=0.9, got {message_arg.data['progress']}"
        assert message_arg.data["samples_generated"] == 42, f"Expected 42, got {message_arg.data['samples_generated']}"

        print(f"✓ Progress message broadcasted successfully")
        print(f"  - type: {message_arg.type.value}")
        print(f"  - stage: {message_arg.data['stage']}")
        print(f"  - progress: {message_arg.data['progress']}")
        print(f"  - samples_generated: {message_arg.data['samples_generated']}")

        print("\n✅ WebSocket integration test PASSED")

    asyncio.run(run())


if __name__ == "__main__":
    test_websocket_broadcasting()
    sys.exit(0)
