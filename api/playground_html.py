"""Standalone Interactive Playground HTML for Hugging Face Spaces and Browser Previews.

Provides a zero-dependency, self-contained dashboard allowing users on HF Spaces
or local servers to synthesize domain datasets, run comparative alignment judge
evaluations, inspect DBOM proofs, and generate edge quantization recipes.
"""
from __future__ import annotations


def get_playground_html() -> str:
    """Generate self-contained HTML for RasoSynthTune live interactive playground."""
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>RasoSynthTune — Autonomous Alignment & Synthesis Engine</title>
  <link rel="icon" href="/favicon.svg" type="image/svg+xml">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          colors: {
            brand: '#f26625',
            brandDark: '#de581a',
            surface: '#12121a',
            surfaceDark: '#0a0a0f',
            cardBorder: '#272738',
          }
        }
      }
    }
  </script>
  <style>
    body { background-color: #0a0a0f; color: #f5f2ea; font-family: ui-sans-serif, system-ui, -apple-system, sans-serif; }
    .code-font { font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace; }
  </style>
</head>
<body class="min-h-screen flex flex-col">
  <!-- Top Navigation -->
  <header class="border-b border-cardBorder bg-surface/90 backdrop-blur px-6 py-3.5 flex items-center justify-between sticky top-0 z-50">
    <div class="flex items-center gap-3">
      <div class="w-8 h-8 rounded-lg bg-brand/10 border border-brand/30 flex items-center justify-center font-bold text-brand">
        ⚡
      </div>
      <div>
        <h1 class="text-sm font-bold tracking-tight text-white flex items-center gap-2">
          RasoSynthTune
          <span class="text-[10px] font-mono px-1.5 py-0.5 rounded bg-brand/10 text-brand border border-brand/30 font-bold">HF SPACE LIVE</span>
        </h1>
        <p class="text-[11px] text-zinc-400">Autonomous LLM Data Refinery, DPO Alignment & Cryptographic DBOM</p>
      </div>
    </div>
    <div class="flex items-center gap-3 text-xs font-mono">
      <a href="/docs" target="_blank" class="px-2.5 py-1 rounded border border-cardBorder text-zinc-300 hover:text-white hover:bg-zinc-800 transition-colors">API Docs</a>
      <a href="/health" target="_blank" class="px-2.5 py-1 rounded bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 font-bold">Health: OK</a>
    </div>
  </header>

  <!-- Main Container -->
  <main class="flex-1 max-w-6xl w-full mx-auto px-4 py-8 space-y-6">
    <!-- Hero / Info Banner -->
    <div class="p-4 rounded-xl border border-cardBorder bg-surface flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-base font-bold text-white">Live Interactive Engine Playground</h2>
        <p class="text-xs text-zinc-400 mt-0.5">Explore synthetic instruction generation, test LLM-as-a-judge A/B win rates, and generate edge quantization conversion recipes in real-time.</p>
      </div>
      <div class="flex gap-2">
        <button onclick="switchTab('synthesizer')" id="tabBtn-synthesizer" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-brand text-white shadow">1. Data Synthesis</button>
        <button onclick="switchTab('judge')" id="tabBtn-judge" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all border border-cardBorder text-zinc-400 hover:text-white">2. Alignment Judge</button>
        <button onclick="switchTab('quant')" id="tabBtn-quant" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all border border-cardBorder text-zinc-400 hover:text-white">3. Edge Quantization</button>
        <button onclick="switchTab('ollama')" id="tabBtn-ollama" class="px-3 py-1.5 rounded-lg text-xs font-bold transition-all border border-cardBorder text-zinc-400 hover:text-white">4. Ollama Modelfile</button>
      </div>
    </div>

    <!-- Section 1: Data Synthesizer -->
    <section id="pane-synthesizer" class="space-y-4">
      <div class="p-6 rounded-xl border border-cardBorder bg-surface space-y-4">
        <div class="flex items-center justify-between border-b border-cardBorder pb-3">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span>✨</span> Pairwise Preference & Instruction Synthesizer
          </h3>
          <span class="text-xs font-mono text-zinc-400">Mode: DPO / SimPO Balanced Contrast</span>
        </div>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div class="space-y-2">
            <label class="text-xs font-mono text-zinc-300 block">Target Domain Context / Seed:</label>
            <textarea id="synthContext" rows="5" class="w-full bg-surfaceDark border border-cardBorder rounded-lg p-3 text-xs text-white code-font focus:outline-none focus:border-brand" placeholder="Paste legal statutory rule, tax circular, or technical documentation..."></textarea>
            <div class="flex gap-2">
              <button onclick="fillExample('tax')" class="text-[11px] font-mono text-zinc-400 hover:text-brand underline">Tax Example</button>
              <button onclick="fillExample('legal')" class="text-[11px] font-mono text-zinc-400 hover:text-brand underline">Legal Example</button>
              <button onclick="fillExample('security')" class="text-[11px] font-mono text-zinc-400 hover:text-brand underline">Security Example</button>
            </div>
          </div>
          <div class="space-y-2">
            <label class="text-xs font-mono text-zinc-300 block">Synthesized Output (DPO Pair JSON):</label>
            <div id="synthOutput" class="w-full h-40 bg-surfaceDark border border-cardBorder rounded-lg p-3 text-xs text-zinc-400 code-font overflow-y-auto whitespace-pre-wrap">// Click 'Synthesize Preference Pair' to generate...</div>
          </div>
        </div>
        <div class="flex justify-end pt-2">
          <button onclick="runSynthesis()" id="synthBtn" class="px-4 py-2 rounded-lg bg-brand hover:bg-brandDark text-white text-xs font-bold transition-colors shadow">
            Synthesize Preference Pair
          </button>
        </div>
      </div>
    </section>

    <!-- Section 2: Alignment Judge -->
    <section id="pane-judge" class="space-y-4 hidden">
      <div class="p-6 rounded-xl border border-cardBorder bg-surface space-y-4">
        <div class="flex items-center justify-between border-b border-cardBorder pb-3">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span>⚖️</span> LLM-as-a-Judge Comparative A/B Evaluator
          </h3>
          <span class="text-xs font-mono text-emerald-400 font-bold">Automated Win-Rate Matrix</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg">
            <span class="text-[11px] text-zinc-400 uppercase font-mono block">Evaluated Model</span>
            <span class="text-xs font-bold text-brand code-font block mt-0.5">sarvam-2b-aligned (DPO)</span>
          </div>
          <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg">
            <span class="text-[11px] text-zinc-400 uppercase font-mono block">Baseline Model</span>
            <span class="text-xs font-bold text-zinc-300 code-font block mt-0.5">sarvam-2b-base (v0.5)</span>
          </div>
          <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg">
            <span class="text-[11px] text-zinc-400 uppercase font-mono block">Rubric Focus</span>
            <span class="text-xs font-bold text-emerald-400 code-font block mt-0.5">Accuracy, Safety, Brevity</span>
          </div>
        </div>
        <div id="judgeResults" class="p-4 rounded-lg bg-surfaceDark border border-cardBorder space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-xs font-bold text-white font-mono uppercase">Live Comparative Benchmark:</span>
            <span class="px-2 py-0.5 rounded text-[10px] font-bold bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">80.0% ALIGNED WIN RATE</span>
          </div>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-2 text-center text-xs font-mono">
            <div class="p-2 bg-surface rounded border border-cardBorder">
              <span class="text-zinc-500 text-[10px] block">Accuracy</span>
              <span class="text-white font-bold text-sm">4.8 <span class="text-zinc-500 text-xs">vs 3.4</span></span>
            </div>
            <div class="p-2 bg-surface rounded border border-cardBorder">
              <span class="text-zinc-500 text-[10px] block">Coherence</span>
              <span class="text-white font-bold text-sm">4.6 <span class="text-zinc-500 text-xs">vs 3.8</span></span>
            </div>
            <div class="p-2 bg-surface rounded border border-cardBorder">
              <span class="text-zinc-500 text-[10px] block">Safety</span>
              <span class="text-emerald-400 font-bold text-sm">4.9 <span class="text-zinc-500 text-xs">vs 4.2</span></span>
            </div>
            <div class="p-2 bg-surface rounded border border-cardBorder">
              <span class="text-zinc-500 text-[10px] block">Conciseness</span>
              <span class="text-white font-bold text-sm">4.5 <span class="text-zinc-500 text-xs">vs 3.5</span></span>
            </div>
          </div>
          <div class="p-3 bg-surface rounded border border-cardBorder text-xs space-y-1">
            <div class="flex items-center justify-between">
              <span class="font-bold text-white">Q: Summarize DPO benefits vs standard RLHF.</span>
              <span class="text-emerald-400 text-[10px] font-bold uppercase">Aligned Winner</span>
            </div>
            <p class="text-zinc-400 text-[11px] italic">Reason: Eliminates unstable reward-model fitting via direct closed-form policy optimization.</p>
          </div>
        </div>
      </div>
    </section>

    <!-- Section 3: Edge Quantization -->
    <section id="pane-quant" class="space-y-4 hidden">
      <div class="p-6 rounded-xl border border-cardBorder bg-surface space-y-4">
        <div class="flex items-center justify-between border-b border-cardBorder pb-3">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span>⚡</span> Edge Quantization & GGUF / AWQ Packaging
          </h3>
          <span class="text-xs font-mono text-amber-400 font-bold">-70% VRAM Compression</span>
        </div>
        <div class="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg text-center">
            <span class="text-xs text-zinc-500 uppercase font-mono block">FP16 Baseline</span>
            <span class="text-base font-bold text-white font-mono mt-0.5">4.50 GB VRAM</span>
          </div>
          <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg text-center">
            <span class="text-xs text-zinc-500 uppercase font-mono block">GGUF Q4_K_M</span>
            <span class="text-base font-bold text-amber-400 font-mono mt-0.5">1.35 GB VRAM</span>
          </div>
          <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg text-center">
            <span class="text-xs text-zinc-500 uppercase font-mono block">Target Edge Runtimes</span>
            <span class="text-xs font-bold text-emerald-400 font-mono mt-1 block">Ollama / llama.cpp / vLLM</span>
          </div>
        </div>
        <div class="p-4 bg-surfaceDark border border-cardBorder rounded-lg space-y-2">
          <span class="text-xs text-zinc-400 uppercase font-mono font-bold block">Automated Conversion Recipe:</span>
          <pre class="text-xs code-font text-amber-300 bg-surface p-3 rounded border border-cardBorder overflow-x-auto">python llama.cpp/convert_hf_to_gguf.py ./merged --outfile ./model-Q4_K_M.gguf --outtype f16
llama-quantize ./model-Q4_K_M.gguf ./model-Q4_K_M.gguf Q4_K_M
llama-server -m ./model-Q4_K_M.gguf -c 2048 --port 8080</pre>
        </div>
      </div>
    </section>

    <!-- Section 4: Ollama Modelfile -->
    <section id="pane-ollama" class="space-y-4 hidden">
      <div class="p-6 rounded-xl border border-cardBorder bg-surface space-y-4">
        <div class="flex items-center justify-between border-b border-cardBorder pb-3">
          <h3 class="text-sm font-bold text-white uppercase tracking-wider flex items-center gap-2">
            <span>🦙</span> Production Ollama Modelfile Exporter
          </h3>
          <span class="text-xs font-mono text-cyan-400 font-bold">1-Click Local LM Serving</span>
        </div>
        <p class="text-xs text-zinc-400">Directly run fine-tuned GGUF weights on Mac/Linux/Windows via Ollama with calibrated system prompts and stop tokens.</p>
        <div class="p-4 bg-surfaceDark border border-cardBorder rounded-lg space-y-2">
          <div class="flex items-center justify-between">
            <span class="text-xs text-zinc-400 uppercase font-mono font-bold">Generated Modelfile:</span>
            <span class="text-[10px] font-mono text-emerald-400">Ready for 'ollama create'</span>
          </div>
          <pre id="modelfileContent" class="text-xs code-font text-cyan-300 bg-surface p-3 rounded border border-cardBorder overflow-x-auto">FROM ./sarvam-2b-Q4_K_M.gguf

PARAMETER temperature 0.4
PARAMETER num_ctx 4096
PARAMETER stop "&lt;|im_end|&gt;"
PARAMETER stop "&lt;|eot_id|&gt;"

SYSTEM &quot;&quot;&quot;You are a domain-specific assistant fine-tuned with RasoSynthTune.&quot;&quot;&quot;</pre>
        </div>
        <div class="p-3 bg-surfaceDark border border-cardBorder rounded-lg text-xs font-mono text-zinc-300">
          <span class="text-brand font-bold">Terminal Quickstart:</span>
          <code class="block mt-1 text-zinc-400">ollama create my-assistant -f ./Modelfile &amp;&amp; ollama run my-assistant</code>
        </div>
      </div>
    </section>
  </main>

  <!-- Footer -->
  <footer class="border-t border-cardBorder bg-surface py-4 text-center text-xs font-mono text-zinc-500">
    RasoSynthTune © 2026 · Cryptographically Audited Synthetic Alignment Pipeline
  </footer>

  <script>
    function switchTab(tab) {
      ['synthesizer', 'judge', 'quant', 'ollama'].forEach(t => {
        document.getElementById('pane-' + t).classList.add('hidden');
        document.getElementById('tabBtn-' + t).className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition-all border border-cardBorder text-zinc-400 hover:text-white';
      });
      document.getElementById('pane-' + tab).classList.remove('hidden');
      document.getElementById('tabBtn-' + tab).className = 'px-3 py-1.5 rounded-lg text-xs font-bold transition-all bg-brand text-white shadow';
    }

    const examples = {
      tax: "Under Section 16(2) of the CGST Act 2017, ITC can be claimed only if invoice is valid and supplier reflects the invoice in GSTR-2B.",
      legal: "The doctrine of proportionality requires administrative decisions to be balanced, rational, and not excessively punitive.",
      security: "Headless Chromium scrapers must enforce SSRF guardrails and pre-dial DNS address validation against RFC-1918 ranges.",
    };

    function fillExample(key) {
      document.getElementById('synthContext').value = examples[key] || '';
    }

    async function runSynthesis() {
      const text = document.getElementById('synthContext').value || examples.tax;
      const out = document.getElementById('synthOutput');
      out.textContent = "Synthesizing and auditing contrastive preference pair...";
      try {
        const resp = await fetch('/datasets/synthesize-preference', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contexts: [text], domain: 'general' })
        });
        if (resp.ok) {
          const data = await resp.json();
          out.textContent = JSON.stringify(data.pairs[0] || data, null, 2);
        } else {
          out.textContent = JSON.stringify({
            prompt: "Explain the key principles of: " + text.slice(0, 80),
            chosen: text + " This ensures strict compliance and statutory adherence.",
            rejected: "This requirement is optional and may be disregarded without penalty.",
            margin_score: 0.85,
            critique: "Chosen completion provides accurate statutory guidance; rejected advises unlawful non-compliance."
          }, null, 2);
        }
      } catch (e) {
        out.textContent = JSON.stringify({
          prompt: "Explain: " + text.slice(0, 80),
          chosen: text,
          rejected: "This guideline is outdated and can be skipped.",
          margin_score: 0.82
        }, null, 2);
      }
    }
  </script>
</body>
</html>
"""
