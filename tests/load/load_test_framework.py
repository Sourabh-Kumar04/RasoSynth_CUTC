"""
Enterprise Load Testing Framework

Comprehensive production-grade load testing using k6 for:
- Normal traffic simulation
- Burst traffic
- Provider throttling
- Long-running workflows
- Concurrent dataset generation
- Streaming SSE workloads
"""

import subprocess
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import os


@dataclass
class LoadTestConfig:
    """Configuration for load test scenarios."""
    name: str
    target_vus: int
    duration_seconds: int
    pre_allocated_vus: int = 1
    environment: str = "local"
    thresholds: Dict[str, float] = field(default_factory=dict)
    tags: Dict[str, str] = field(default_factory=dict)


# =============================================================================
# k6 Load Test Scripts
# =============================================================================

K6_TEST_TEMPLATE = '''// k6 Load Test: {name}
// Generated: {timestamp}
// Environment: {environment}

import http from 'k6/http';
import {{ check, sleep, group }} from 'k6';
import {{ Rate, Trend, Counter }} from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');
const latency = new Trend('latency');
const providerLatency = new Trend('provider_latency');
const jobDuration = new Trend('job_duration');
const streamingThroughput = new Trend('streaming_throughput');

// Configuration
const BASE_URL = '{base_url}';
const API_KEY = '{api_key}';

export const options = {{
    stages: {stages},
    thresholds: {{
        'http_req_duration': ['p(95)<{p95_latency}', 'p(99)<{p99_latency}'],
        'errors': ['rate<{error_threshold}'],
        'latency': ['p(95)<{p95_latency}'],
    }},
    tags: {tags},
}};

// Test data
const testData = {test_data};

export default function() {{
    // Scenario: {name}
    {scenario_code}
}}

// Helper functions
function authHeaders() {{
    return {{
        'Authorization': `Bearer ${{API_KEY}}`,
        'Content-Type': 'application/json',
    }};
}}

function handleError(endpoint, error) {{
    errorRate.add(1);
    console.error(`Error at ${{endpoint}}: ${{error}}`);
}}
'''


def generate_k6_test(
    name: str,
    base_url: str,
    api_key: str,
    stages: List[Dict[str, Any]],
    scenario: str,
    p95_latency: str = "500",
    p99_latency: str = "1000",
    error_threshold: str = "0.05",
    test_data: str = "[]"
) -> str:
    """Generate a k6 load test script."""

    stages_json = json.dumps(stages, indent=8)
    tags = json.dumps({"test": name, "env": "load"})

    scenario_code = _generate_scenario_code(scenario)

    return K6_TEST_TEMPLATE.format(
        name=name,
        timestamp=datetime.utcnow().isoformat(),
        environment="production",
        base_url=base_url,
        api_key=api_key or "${__ENV.API_KEY || 'test'}",
        stages=stages_json,
        p95_latency=p95_latency,
        p99_latency=p99_latency,
        error_threshold=error_threshold,
        tags=tags,
        scenario_code=scenario_code,
        test_data=test_data,
    )


def _generate_scenario_code(scenario: str) -> str:
    """Generate scenario-specific code."""

    scenarios = {
        "normal_traffic": '''
    group("Normal API Traffic", () => {
        // Health check
        let res = http.get(`${BASE_URL}/health`);
        check(res, {{ "health ok": (r) => r.status === 200 }});
        latency.add(res.timings.duration);

        // List datasets
        res = http.get(`${BASE_URL}/api/v2/datasets?page=1&page_size=20`);
        check(res, {{ "datasets list": (r) => r.status === 200 }});

        // List providers
        res = http.get(`${BASE_URL}/api/v2/providers`);
        check(res, {{ "providers list": (r) => r.status === 200 }});

        sleep(1);
    });
''',
        "burst_traffic": '''
    group("Burst Traffic Simulation", () => {
        // Simulate burst of requests
        const burstSize = 10;
        const batch = [];

        for (let i = 0; i < burstSize; i++) {{
            batch.push(http.get(`${BASE_URL}/health`));
        }}

        batch.forEach((res, idx) => {{
            check(res, {{ [`burst request ${{idx}}`]: (r) => r.status === 200 }});
            latency.add(res.timings.duration);
        }});

        sleep(Math.random() * 2);
    });
''',
        "dataset_generation": '''
    group("Dataset Generation", () => {{
        // Create generation request
        const payload = JSON.stringify({{
            name: `load_test_${{Date.now()}}`,
            dataset_type: "synthetic",
            modality: ["text"],
            min_samples: 100,
            max_samples: 1000,
            quality_threshold: 0.8,
            execution_strategy: "balanced",
        }});

        let res = http.post(
            `${BASE_URL}/api/v2/datasets/generate`,
            payload,
            {{ headers: authHeaders() }}
        );

        const success = check(res, {{
            "job created": (r) => r.status === 200 || r.status === 201,
            "has job_id": (r) => r.json('data.job_id') !== undefined,
        }});

        if (success) {{
            jobDuration.add(res.timings.duration);

            // Poll for completion (simulated)
            const jobId = res.json('data.job_id');
            for (let i = 0; i < 5; i++) {{
                sleep(2);
                res = http.get(`${BASE_URL}/api/v2/datasets/${{jobId}}`);
                if (res.json('status') === 'completed') break;
            }}
        }} else {{
            handleError("dataset/generate", res.body);
        }}
    }});
''',
        "streaming_workload": '''
    group("Streaming SSE Workload", () => {
        // Start SSE stream
        const res = http.get(`${BASE_URL}/api/v2/stream/progress/test-job`);
        check(res, {{
            "sse started": (r) => r.status === 200,
            "content type": (r) => r.headers['Content-Type'].includes('text/event-stream'),
        }});

        // Note: SSE testing requires websocket or async client
        streamingThroughput.add(100); // Simulated throughput

        sleep(1);
    });
''',
        "provider_routing": '''
    group("Provider Routing Stress", () => {{
        const providers = ['google', 'anthropic', 'openai', 'nvidia', 'ollama'];

        providers.forEach(provider => {{
            const start = Date.now();
            const res = http.post(
                `${BASE_URL}/api/v2/providers/route`,
                JSON.stringify({{ task_type: 'general', constraints: [] }}),
                {{ headers: authHeaders() }}
            );

            providerLatency.add(Date.now() - start, {{ provider }});
            check(res, {{ [`route ${{provider}}`]: (r) => r.status === 200 }});
        }});

        sleep(0.5);
    }});
''',
        "orchestration_spike": '''
    group("Orchestration Spike", () => {{
        const workflows = [];

        // Create multiple workflow plans
        for (let i = 0; i < 5; i++) {{
            const res = http.post(
                `${BASE_URL}/api/v2/workflows/plan`,
                JSON.stringify({{
                    task_type: 'data_generation',
                    constraints: [],
                    execution_strategy: 'balanced',
                }}),
                {{ headers: authHeaders() }}
            );

            if (res.status === 200) {{
                workflows.push(res.json('data.plan_id'));
            }}
        }}

        // Execute workflows
        workflows.forEach(planId => {{
            http.post(
                `${BASE_URL}/api/v2/workflows/execute?plan_id=${{planId}}`,
                null,
                {{ headers: authHeaders() }}
            );
        }});

        sleep(3);
    }});
''',
    }

    return scenarios.get(scenario, scenarios["normal_traffic"])


# =============================================================================
# Locust Distributed Load Test
# =============================================================================

LOCUST_TEST_TEMPLATE = '''"""
Locust Distributed Load Test: {name}
Generated: {timestamp}

Run with:
    locust -f locustfile.py --host={{host}} --port=8089
    locust -f locustfile.py --host={{host}} --master
"""

from locust import HttpUser, task, between, events
from locust.runners import MasterRunner
import json
import random


class {class_name}User(HttpUser):
    """Simulates {name} workload."""

    wait_time = between({min_wait}, {max_wait})

    def on_start(self):
        """Initialize user session."""
        self.headers = {{
            'Authorization': f'Bearer ${{os.getenv("API_KEY", "test")}}',
            'Content-Type': 'application/json',
        }}

    @task({weight})
    def health_check(self):
        """Health check endpoint."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {{response.status_code}}")

    @task({weight})
    def list_datasets(self):
        """List datasets with pagination."""
        params = {{"page": random.randint(1, 10), "page_size": 20}}
        with self.client.get("/api/v2/datasets", params=params, catch_response=True) as response:
            if response.status_code == 200:
                data = response.json()
                if "datasets" in data:
                    response.success()
                else:
                    response.failure("Invalid response")
            else:
                response.failure(f"Status: {{response.status_code}}")

    @task({weight // 2})
    def create_dataset(self):
        """Create a new dataset generation job."""
        payload = {{
            "name": f"load_test_{random.randint(1000, 9999)}",
            "dataset_type": random.choice(["synthetic", "extracted", "curated"]),
            "modality": random.choice([["text"], ["text", "code"], ["text", "image"]]),
            "min_samples": random.randint(10, 100),
            "max_samples": random.randint(100, 1000),
            "quality_threshold": round(random.uniform(0.6, 0.95), 2),
            "execution_strategy": random.choice(["balanced", "speed", "quality"]),
        }}

        with self.client.post(
            "/api/v2/datasets/generate",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/v2/datasets/generate"
        ) as response:
            if response.status_code in [200, 201]:
                response.success()
            else:
                response.failure(f"Failed: {{response.status_code}}")

    @task({weight // 2})
    def plan_workflow(self):
        """Plan a workflow."""
        payload = {{
            "task_type": random.choice(["data_generation", "analysis", "transformation"]),
            "constraints": [],
            "execution_strategy": "balanced",
        }}

        with self.client.post(
            "/api/v2/workflows/plan",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/v2/workflows/plan"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {{response.status_code}}")

    @task({weight // 4})
    def provider_route(self):
        """Test provider routing."""
        payload = {{
            "task_type": random.choice(["general", "coding", "reasoning"]),
            "constraints": [],
        }}

        with self.client.post(
            "/api/v2/providers/route",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="/api/v2/providers/route"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Routing failed: {{response.status_code}}")

    @task({weight // 4})
    def get_metrics(self):
        """Get system metrics."""
        endpoints = [
            "/api/v2/metrics",
            "/api/v2/metrics/validation",
            "/api/v2/metrics/orchestration",
        ]
        endpoint = random.choice(endpoints)

        with self.client.get(endpoint, catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Metrics failed: {{response.status_code}}")


# Statistics event handlers
@events.init_command_line_parser.add_listener
def add_custom_arguments(parser):
    """Add custom command line arguments."""
    parser.add_argument("--test-scenario", type=str, default="normal",
                        help="Test scenario: normal, burst, stress")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Called when test starts."""
    print(f"Starting load test: {{environment.runner.host}}")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Called when test stops."""
    print("Load test completed")
'''


def generate_locust_test(
    name: str,
    min_wait: int = 1,
    max_wait: int = 3,
    weight: int = 10
) -> str:
    """Generate a Locust distributed load test script."""
    return LOCUST_TEST_TEMPLATE.format(
        name=name,
        timestamp=datetime.utcnow().isoformat(),
        class_name=name.replace(" ", "").replace("-", ""),
        min_wait=min_wait,
        max_wait=max_wait,
        weight=weight,
    )


# =============================================================================
# Load Test Runner
# =============================================================================

class LoadTestRunner:
    """Orchestrates load testing across multiple scenarios."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url
        self.api_key = api_key
        self.results: List[Dict[str, Any]] = []

    def run_k6_test(
        self,
        test_file: str,
        duration: int = 60,
        vus: int = 10
    ) -> Dict[str, Any]:
        """Run a k6 test and collect results."""
        env = os.environ.copy()
        if self.api_key:
            env["API_KEY"] = self.api_key

        cmd = [
            "k6", "run",
            "--duration", f"{duration}s",
            "--vus", str(vus),
            "--out", "json=results.json",
            test_file
        ]

        try:
            result = subprocess.run(
                cmd,
                env=env,
                capture_output=True,
                text=True,
                timeout=duration + 60
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Test timed out"}
        except FileNotFoundError:
            return {"success": False, "error": "k6 not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run_scenario(
        self,
        scenario_name: str,
        scenario_type: str,
        vus: int,
        duration: int
    ) -> Dict[str, Any]:
        """Run a specific load test scenario."""
        print(f"Running scenario: {scenario_name}")

        if scenario_type == "normal_traffic":
            stages = [
                {"duration": "30s", "target": vus},
                {"duration": "1m", "target": vus},
                {"duration": "30s", "target": 0},
            ]
        elif scenario_type == "burst":
            stages = [
                {"duration": "10s", "target": vus},
                {"duration": "30s", "target": vus * 5},  # Burst
                {"duration": "20s", "target": vus},
            ]
        elif scenario_type == "stress":
            stages = [
                {"duration": "30s", "target": vus},
                {"duration": "1m", "target": vus * 2},
                {"duration": "1m", "target": vus * 3},
                {"duration": "30s", "target": 0},
            ]
        else:
            stages = [{"duration": "30s", "target": vus}]

        # Generate test file
        test_content = generate_k6_test(
            name=scenario_name,
            base_url=self.base_url,
            api_key=self.api_key,
            stages=stages,
            scenario=scenario_type,
        )

        test_file = f"/tmp/k6_test_{scenario_name}.js"
        with open(test_file, "w") as f:
            f.write(test_content)

        # Run test
        result = self.run_k6_test(test_file, duration, vus)
        self.results.append({
            "scenario": scenario_name,
            "type": scenario_type,
            "vus": vus,
            "duration": duration,
            **result
        })

        return result


# =============================================================================
# Test Scenario Configurations
# =============================================================================

SCENARIOS = {
    "baseline": LoadTestConfig(
        name="Baseline Performance",
        target_vus=10,
        duration_seconds=60,
        thresholds={"p95": 200, "p99": 500},
    ),
    "normal_traffic": LoadTestConfig(
        name="Normal Production Traffic",
        target_vus=50,
        duration_seconds=300,
        thresholds={"p95": 500, "p99": 1000},
    ),
    "burst_traffic": LoadTestConfig(
        name="Burst Traffic Simulation",
        target_vus=100,
        duration_seconds=120,
        thresholds={"p95": 1000, "p99": 2000},
    ),
    "stress_test": LoadTestConfig(
        name="Maximum Stress Test",
        target_vus=200,
        duration_seconds=180,
        thresholds={"p95": 2000, "p99": 5000},
    ),
    "provider_throttle": LoadTestConfig(
        name="Provider Throttling Simulation",
        target_vus=30,
        duration_seconds=120,
        thresholds={"p95": 800, "p99": 1500},
    ),
    "streaming_load": LoadTestConfig(
        name="Streaming SSE Workload",
        target_vus=50,
        duration_seconds=180,
        thresholds={"p95": 300, "p99": 600},
    ),
}


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python load_test_framework.py <base_url>")
        print("Example: python load_test_framework.py http://localhost:8000")
        sys.exit(1)

    base_url = sys.argv[1]
    api_key = os.getenv("API_KEY")

    runner = LoadTestRunner(base_url, api_key)

    # Run baseline test
    result = runner.run_scenario(
        scenario_name="baseline",
        scenario_type="normal_traffic",
        vus=10,
        duration=60
    )

    print(json.dumps(result, indent=2))