"""Deterministic debug harness for verifying extraction and filtering heuristics."""
import asyncio
import sys
from pathlib import Path

# Add root folder to path so we can import modules
sys.path.append(str(Path(__file__).parent.parent))

from pipeline.filtering import FilteringPipeline, FilteredSample
from core.provider_router import ProviderRouter
from core.config import Settings

# Scenario Content definitions
SCENARIOS = {
    "Technical Markdown README": """
# awesome-project
###### Enterprise Distributed Pipeline

An awesome project list showcasing advanced engineering.
Here are the core libraries:
* [RasoDataset](https://github.com/VoltAgent/awesome-agent-skills/tree/main/dataset) - An AI dataset generation system with dynamic adaptivity.
* [LLM-Router](https://github.com/VoltAgent/awesome-agent-skills/tree/main/router) - Intelligent failover routing.
* [Checkpointer](https://github.com/VoltAgent/awesome-agent-skills/tree/main/checkpoints) - Distributed checkpoints for workflow resilience.

==================================================
FEATURES:
- Fast, secure, and resilient.
- Bounded memory structures.
==================================================
""",
    "Code-Heavy File": """
import asyncio
import os

class PipelineExecutor:
    def __init__(self, config: dict):
        self.config = config
        self.concurrency = config.get("concurrency", 4)
        self.semaphore = asyncio.Semaphore(self.concurrency)

    async def execute_task(self, task_id: str, payload: dict) -> dict:
        async with self.semaphore:
            print(f"Executing task {task_id}...")
            await asyncio.sleep(0.1)
            return {"status": "success", "task_id": task_id}
""",
    "Highly Repetitive Text": "This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam. This is spam.",
    "High-Quality Academic Prose": "The emergence of agentic workflow architectures represents a fundamental paradigm shift in distributed artificial intelligence systems. Rather than viewing language models as static computational nodes, contemporary approaches frame them as autonomous controllers within a stateful execution graph. This paradigm enables dynamic routing, iterative self-correction, and human-in-the-loop validation, vastly outperforming zero-shot prompting techniques.",
    "Garbled Random Characters": "asdkljfa;sldkfj asldkfj aaaaaaaa qwerqwerqwer zxvcuzxvcuzxvc asdflkjsadflkjasdflkjasdflkj asdfasdfasdfasdfasdfasdfasdfasdfasdfasdfasd",
    "Short Fragment": "Short sentence."
}

class DummyRouter:
    """Mock router to avoid external LLM dependencies during deterministic local harness runs."""
    async def embed(self, text):
        class MockEmbedding:
            embedding = [0.1] * 128
        return MockEmbedding()

async def run_harness():
    print("==================================================")
    print("   RASODATASET PIPELINE DETERMINISTIC HARNESS     ")
    print("==================================================\n")
    
    settings = Settings()
    router = DummyRouter()
    pipeline = FilteringPipeline(router, {})
    
    total = 0
    passed = 0
    rejected = 0
    rejection_reasons = {}
    
    print(f"{'Scenario Name':<30} | {'Score':<6} | {'Passed?':<7} | {'Reason / Issues'}")
    print("-" * 80)
    
    for name, content_text in SCENARIOS.items():
        total += 1
        
        # Create a mock content object
        class Content:
            content = content_text
            url = f"https://mock-source.org/{name.replace(' ', '_').lower()}"
            metadata = {}
            
        result = await pipeline.filter(Content(), target_domain="distributed systems", return_all=True)
        
        score_str = f"{result.quality_score:.2f}" if result else "N/A"
        passed_str = "YES" if result and result.passed else "NO"
        
        if result and result.passed:
            passed += 1
            issues_str = "None"
        else:
            rejected += 1
            reason = getattr(result, "filter_reason", "unknown") or "unspecified"
            rejection_reasons[reason] = rejection_reasons.get(reason, 0) + 1
            issues_str = f"{reason} (Issues: {', '.join(result.issues) if result else []})"
            
        print(f"{name:<30} | {score_str:<6} | {passed_str:<7} | {issues_str}")
        
    print("\n==================================================")
    print("            REJECTION & METRICS REPORT            ")
    print("==================================================")
    print(f"Total Scenarios Evaluated: {total}")
    print(f"Passed Filters           : {passed} ({passed/total*100:.1f}%)")
    print(f"Rejected / Filtered      : {rejected} ({rejected/total*100:.1f}%)")
    print("\nRejection Reasons Breakdown:")
    for reason, count in rejection_reasons.items():
        print(f"  - {reason:<25}: {count}")
    print("==================================================")
    
    # Assertions
    assert passed > 0, "No scenarios passed the filters. Investigation needed."
    assert "garbled_text" not in [r.issues for r in [await pipeline.filter(type('C', (), {"content": SCENARIOS["Technical Markdown README"]})(), return_all=True)]][0], "Markdown links falsely triggered garbled text"
    print("\n✔ DETERMINISTIC HEURISTICS ASSERTIONS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    asyncio.run(run_harness())
