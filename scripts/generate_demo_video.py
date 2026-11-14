#!/usr/bin/env python3
"""
RasoSynthTune — Presentation Demo Video Generator
Captures high-fidelity 1080p browser views and renders an end-to-end MP4 demo video.
"""

import os
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

BASE_DIR = Path("/mnt/d/Sourabh_Workspace/00_Academics/RasoSynth_CUTC")
FRAMES_DIR = BASE_DIR / "outputs" / "demo_frames"
OUTPUT_VIDEO = BASE_DIR / "outputs" / "RasoSynthTune_Demo_Walkthrough.mp4"
FRAMES_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_VIDEO.parent.mkdir(parents=True, exist_ok=True)

CHROME_BIN = "/home/sourabh-kumar04/.local/bin/chromium"
BASE_URL = "http://127.0.0.1:3000"

def create_title_card(title: str, subtitle: str, badge: str, filename: str, details=None):
    """Generate a sleek, dark-mode 1920x1080 title card."""
    img = Image.new("RGB", (1920, 1080), color=(10, 10, 15))
    draw = ImageDraw.Draw(img)
    
    # Grid background accents
    for x in range(0, 1920, 80):
        draw.line([(x, 0), (x, 1080)], fill=(20, 20, 32), width=1)
    for y in range(0, 1080, 80):
        draw.line([(0, y), (1920, y)], fill=(20, 20, 32), width=1)
        
    # Top border line
    draw.rectangle([(0, 0), (1920, 4)], fill=(242, 102, 37))
    
    # Accent badge
    draw.rounded_rectangle([(140, 260), (440, 305)], radius=6, fill=(242, 102, 37, 30), outline=(242, 102, 37), width=2)
    draw.text((160, 272), badge.upper(), fill=(242, 102, 37))
    
    # Title
    draw.text((140, 340), title, fill=(255, 255, 255))
    
    # Subtitle
    draw.text((140, 430), subtitle, fill=(168, 162, 158))
    
    # Extra points
    if details:
        y_offset = 540
        for item in details:
            draw.rectangle([(140, y_offset + 8), (152, y_offset + 20)], fill=(16, 185, 129))
            draw.text((170, y_offset), item, fill=(230, 230, 235))
            y_offset += 65
            
    # Bottom brand footer
    draw.text((140, 980), "© 2026 RasoSynthTune · Autonomous Synthetic Data Engine · IndiaAI Sovereign Compute", fill=(100, 100, 120))
    
    out_path = FRAMES_DIR / filename
    img.save(out_path)
    return out_path

def capture_page(route: str, filename: str, window_size="1920,1080", budget="15000"):
    """Capture 1080p screenshot of a route."""
    out_path = FRAMES_DIR / filename
    url = f"{BASE_URL}/{route.lstrip('/')}"
    cmd = [
        CHROME_BIN,
        "--headless=new",
        "--disable-gpu",
        "--no-sandbox",
        "--hide-scrollbars",
        f"--window-size={window_size}",
        f"--virtual-time-budget={budget}",
        f"--screenshot={out_path}",
        url
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return out_path

print("1. Creating presentation title cards...")
c1 = create_title_card(
    title="RasoSynthTune 2.0 Enterprise",
    subtitle="Autonomous Synthetic Data Engine & QLoRA Fine-Tuning Studio",
    badge="Platform Walkthrough",
    filename="card_01_intro.png",
    details=[
        "Deterministic Seedless Generation with 7 Cognitive Architectures",
        "4-Stage Distributed DAG Pipeline: Ingest → Synthesize → Evaluate → Attest",
        "Cryptographic Provenance with SHA-256 Binary Merkle Tree (DBOM Certificates)",
        "End-to-End QLoRA / PEFT Fine-Tuning Studio with Real-Time Loss Telemetry",
    ]
)

c2 = create_title_card(
    title="Phase 1: Dataset Studio & Invariants",
    subtitle="Curriculum Design with Statutory & Domain Grounding",
    badge="Curriculum Synthesis",
    filename="card_02_studio.png",
    details=[
        "5 Curated Enterprise Presets (AI Kosh GST, Aerospace, Indic Bhashini, Python, Medical)",
        "Real-Time Shannon Entropy & Information Density Linter",
        "Polysemy Guard & Anti-Domain Exclusion Filters (DPDP / IT Act Compliant)",
        "AST Code Sandbox Verification for Zero-Defect Syntax Generation",
    ]
)

c3 = create_title_card(
    title="Phase 2: Multi-Agent DAG & Telemetry",
    subtitle="19 Autonomous Agent Roles Coordinating Across 4 Pipeline Stages",
    badge="Orchestration Fleet",
    filename="card_03_orchestration.png",
    details=[
        "Autonomous Stage Progression: Ingest (0.1) → Synthesize (0.7) → Evaluate (0.9) → Attest (1.0)",
        "Real-Time Execution Logs, State Snapshots, and Retry Cycles",
        "Non-Flipping DAG Visualizer with Dynamic Worker Pool Allocation",
        "Zero-Drop Fault Tolerant Event Bus with Local Checkpoint Recovery",
    ]
)

c4 = create_title_card(
    title="Phase 3: Cryptographic DBOM Attestation",
    subtitle="Mathematically Verifiable Provenance for Enterprise Audits",
    badge="Provenance & DBOM",
    filename="card_04_dbom.png",
    details=[
        "Immutable SHA-256 Binary Merkle Tree Sealing Every Generated Row",
        "Cryptographic DBOM Certificate Issued with Merkle Root Hash",
        "Interactive Proof Inspector Verifying Sibling Paths in O(log N)",
        "Benchmark Contamination Guard Screening Against Standard Test Splits",
    ]
)

c5 = create_title_card(
    title="Phase 4: Model Training Studio (QLoRA)",
    subtitle="Automated PEFT/LoRA Fine-Tuning on Certified Synthetic Datasets",
    badge="Model Fine-Tuning",
    filename="card_05_finetune.png",
    details=[
        "Seamless LoRA Adapter Training Directly from Generated Dataset Artifacts",
        "Live Training Telemetry: Real-Time Epochs, Loss Curves, and Learning Rate",
        "Multi-Target Cloud Dispatch (Modal A10G, RunPod, and Local Execution)",
        "One-Click Model Artifact Export (GGUF Quantization & Ollama Modelfile)",
    ]
)

c6 = create_title_card(
    title="RasoSynthTune 2.0 — Hackathon Ready",
    subtitle="Production-Grade Reliability for Sovereign Indian AI Ecosystems",
    badge="Presentation Complete",
    filename="card_06_outro.png",
    details=[
        "Live Site: rasosynthtune.vercel.app · ngrok Tunnel Active",
        "Full Stack: Python FastAPI Backend + Next.js 14 Production Frontend",
        "Aligned with IndiaAI Mission & DPDP Act Data Governance Standards",
        "Ready for Live Demonstration & Technical Jury Evaluation",
    ]
)

print("2. Capturing high-resolution application screenshots...")
views = [
    ("", "view_01_home_hero.png", "1920,1080"),
    ("studio", "view_02_studio_top.png", "1920,1080"),
    ("orchestration", "view_03_orchestration_dag.png", "1920,1080"),
    ("jobs", "view_04_jobs_dashboard.png", "1920,1080"),
    ("datasets", "view_05_datasets_library.png", "1920,1080"),
    ("dbom", "view_06_dbom_attestation.png", "1920,1080"),
    ("quality", "view_07_quality_inspector.png", "1920,1080"),
    ("review", "view_08_review_studio.png", "1920,1080"),
    ("finetune", "view_09_model_training.png", "1920,1080"),
    ("settings", "view_10_settings_system.png", "1920,1080"),
]

for route, fname, size in views:
    print(f"  - Capturing {route or 'homepage'} -> {fname}")
    capture_page(route, fname, window_size=size)

print("3. Assembling video timeline...")
# Video storyboard: pairs of (frame_file, duration_seconds)
storyboard = [
    ("card_01_intro.png", 5.0),
    ("view_01_home_hero.png", 6.0),
    ("card_02_studio.png", 4.5),
    ("view_02_studio_top.png", 6.5),
    ("card_03_orchestration.png", 4.5),
    ("view_03_orchestration_dag.png", 6.5),
    ("view_04_jobs_dashboard.png", 6.0),
    ("view_05_datasets_library.png", 5.5),
    ("card_04_dbom.png", 4.5),
    ("view_06_dbom_attestation.png", 6.5),
    ("view_07_quality_inspector.png", 6.0),
    ("view_08_review_studio.png", 5.0),
    ("card_05_finetune.png", 4.5),
    ("view_09_model_training.png", 7.0),
    ("view_10_settings_system.png", 5.0),
    ("card_06_outro.png", 6.0),
]

concat_list_file = FRAMES_DIR / "concat_list.txt"
with open(concat_list_file, "w") as f:
    for fname, dur in storyboard:
        frame_path = FRAMES_DIR / fname
        if frame_path.exists():
            f.write(f"file '{frame_path}'\n")
            f.write(f"duration {dur}\n")
    # Repeat the last frame once as required by ffmpeg concat demuxer
    last_file = FRAMES_DIR / storyboard[-1][0]
    f.write(f"file '{last_file}'\n")

print("4. Encoding 1080p MP4 demo video via ffmpeg...")
ffmpeg_cmd = [
    "ffmpeg",
    "-y",
    "-f", "concat",
    "-safe", "0",
    "-i", str(concat_list_file),
    "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,format=yuv420p",
    "-c:v", "libx264",
    "-preset", "medium",
    "-crf", "20",
    "-r", "30",
    str(OUTPUT_VIDEO)
]

res = subprocess.run(ffmpeg_cmd, capture_output=True, text=True)
if res.returncode == 0:
    size_mb = os.path.getsize(OUTPUT_VIDEO) / (1024 * 1024)
    print(f"\nSUCCESS! Demo video rendered at:\n{OUTPUT_VIDEO} ({size_mb:.2f} MB)")
else:
    print("FFmpeg error:", res.stderr)
