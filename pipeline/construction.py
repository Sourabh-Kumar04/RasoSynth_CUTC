"""Dynamic dataset construction with adaptive schema inference and multi-type support."""
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Callable, Any
from enum import Enum
import re
import json
from typing import Dict

from core.provider_router import TaskType
from core.intent import UserIntent


class DatasetType(Enum):
    """Dataset types supported by the system."""
    SFT = "sft"
    RAG = "rag"
    RLHF = "rlhf"
    CLASSIFICATION = "classification"
    CODING = "coding"
    REASONING = "reasoning"
    CONVERSATIONAL = "conversational"
    TOOL_CALLING = "tool_calling"
    MULTIMODAL = "multimodal"
    GRAPH = "graph"
    TRAJECTORY = "trajectory"
    CUSTOM = "custom"


# ---------------------------------------------------------------------------
# Quality guard helpers — keep bot / garbage content out of datasets
# ---------------------------------------------------------------------------

import re as _re

_ANTI_BOT_REGEX = _re.compile(
    r"JavaScript\s+is\s+disabled|enable\s+JavaScript|captcha|CAPTCHA"
    r"|cloudflare\s+challenge|verify\s+you\s+are\s+(a|not\s+a)\s+(robot|human)"
    r"|just\s+a\s+moment.*verify|429\s+too\s+many\s+requests",
    _re.IGNORECASE,
)

_JSON_LIKE_TARGET = _re.compile(r'^\s*[{[]')


def _is_garbage_content(text: str) -> bool:
    """Return True if the text is anti-bot, scraped HTML banner, or markdown fluff."""
    if not text or len(text.strip()) < 20:
        return True
    if _ANTI_BOT_REGEX.search(text):
        return True
    # Reject raw scraped HTML banners, markdown badges, and navigation headers
    text_lower = text.lower()
    if any(fluff in text_lower for fluff in [
        '<div align="center">', '<img src=', 'table of contents', 'awesome data science',
        'back to top', 'become a sponsor', 'license-mit', 'badge.svg'
    ]):
        return True
    return False


def _sanitize_target_domain(raw: str) -> str:
    """If *raw* looks like a dumped JSON config, extract the real domain."""
    if not raw:
        return ""
    if _JSON_LIKE_TARGET.match(raw):
        # Try to extract "target_domain" from a JSON-string blob
        import json as _json
        try:
            obj = _json.loads(raw)
            if isinstance(obj, dict):
                return str(obj.get("target_domain", "")) or ""
        except (_json.JSONDecodeError, TypeError):
            pass
    # Also guard against the full json dict with escaped quotes
    if '"target_domain"' in raw:
        m = _re.search(r'"target_domain"\s*:\s*"([^"]+)"', raw)
        if m:
            return m.group(1)
    return raw


def _extract_json_array(raw_text: str) -> list:
    """Robustly extract a JSON array from raw LLM output even with preamble, postamble, or markdown fences."""
    if not raw_text:
        return []
    
    # 1. Strip markdown fences
    cleaned = re.sub(r'```(?:json)?\s*', '', raw_text, flags=re.IGNORECASE)
    cleaned = re.sub(r'```\s*$', '', cleaned).strip()
    
    # 2. Try direct JSON parsing
    try:
        data = json.loads(cleaned)
        if isinstance(data, list):
            return data
    except Exception:
        pass
        
    # 3. Regex match for bracketed JSON array [...]
    match = re.search(r'\[\s*\{.*\}\s*\]', raw_text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            if isinstance(data, list):
                return data
        except Exception:
            pass

    # 4. Regex fallback: find individual JSON objects containing instruction/response
    objs = []
    obj_matches = re.findall(r'\{\s*"instruction"\s*:[^}]+\}', raw_text, re.DOTALL)
    for om in obj_matches:
        try:
            parsed = json.loads(om)
            if isinstance(parsed, dict) and "instruction" in parsed and "response" in parsed:
                objs.append(parsed)
        except Exception:
            pass

    return objs


@dataclass
class SchemaSpec:
    """Specification for custom dataset schemas."""
    name: str = "default"
    instruction_field: str = "instruction"
    response_field: str = "response"
    input_field: str | None = "input"
    metadata_fields: list[str] = field(default_factory=list)


@dataclass
class ConstructedSample:
    """Constructed training sample with flexible schema."""
    instruction: str
    response: str
    input: str | None = None
    conversation: list[dict] | None = None
    metadata: dict = field(default_factory=dict)
    difficulty_tier: int = 3
    curriculum_order: int = 0
    format: str = "alpaca"
    schema_compliant: dict = field(default_factory=dict)
    quality_indicators: dict = field(default_factory=dict)


class SchemaInferrer:
    """Infers optimal schema from content characteristics and user requirements."""

    def __init__(self, router=None):
        self.router = router

    async def infer_schema(
        self,
        content: list[dict],
        user_schema: dict | None = None,
        dataset_type: DatasetType = DatasetType.SFT
    ) -> SchemaSpec:
        """Infer schema from content and requirements."""
        if user_schema:
            return self._parse_user_schema(user_schema)

        # Analyze content to infer schema
        schema = SchemaSpec()

        # Detect table-like structures
        has_tables = any('table' in c.get('content_type', '') for c in content)
        if has_tables:
            schema.metadata_fields = ["table_headers", "row_count"]

        # Dataset-type specific defaults
        if dataset_type == DatasetType.TOOL_CALLING:
            schema.instruction_field = "tool_call"
            schema.response_field = "result"
            schema.metadata_fields = ["tool_name", "parameters"]

        elif dataset_type == DatasetType.REASONING:
            schema.instruction_field = "problem"
            schema.response_field = "solution"
            schema.metadata_fields = ["steps", "confidence", "reasoning_type"]

        elif dataset_type == DatasetType.RAG:
            schema.input_field = "context"
            schema.metadata_fields = ["source", "chunk_index"]

        return schema

    def _parse_user_schema(self, schema: dict) -> SchemaSpec:
        """Parse user-provided schema specification."""
        return SchemaSpec(
            name=schema.get("name", "custom"),
            instruction_field=schema.get("instruction_field", "instruction"),
            response_field=schema.get("response_field", "response"),
            input_field=schema.get("input_field"),
            metadata_fields=schema.get("metadata_fields", []),
        )


class ConstructionPipeline:
    """Dynamic construction pipeline with adaptive schema support."""

    def __init__(self, router, config: dict):
        self.router = router
        self.config = config
        self.dataset_type = DatasetType(config.get("dataset_type", "sft"))
        self.schema_inferrer = SchemaInferrer(router)
        self._constructed_samples: list[ConstructedSample] = []

        # Schema specification
        self.schema = SchemaSpec()

        # Augmentation settings
        self.synthetic_ratio = config.get("synthetic_ratio", 0.0)

        # Quality tracking
        self._difficulty_distribution: dict[int, int] = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}

    async def construct(
        self,
        filtered_sample,
        intent: UserIntent,
        dataset_type: DatasetType | None = None
    ) -> AsyncGenerator[ConstructedSample, None]:
        """Construct training samples with dynamic schema adaptation."""
        # Update schema if custom schema provided (from config)
        custom_schema = self.config.get("output_schema")
        if custom_schema:
            self.schema = self.schema_inferrer._parse_user_schema(custom_schema)
        elif dataset_type:
            self.dataset_type = dataset_type

        content = filtered_sample.content if hasattr(filtered_sample, 'content') else str(filtered_sample)
        quality = getattr(filtered_sample, 'quality_score', 0.5)
        target_domain = intent.domain

        # Infer schema from content if not already done
        if not self.schema.name or self.schema.name == "default":
            inferred = await self.schema_inferrer.infer_schema(
                [{"content": content, "content_type": "text", "type": self.dataset_type.value}],
                None,
                self.dataset_type
            )
            if inferred.metadata_fields:
                self.schema.metadata_fields = inferred.metadata_fields

        # Route to appropriate construction method
        if self.dataset_type == DatasetType.SFT:
            async for item in self._construct_sft_adaptive(content, target_domain, quality):
                yield item
        elif self.dataset_type == DatasetType.RAG:
            for item in self._construct_rag_adaptive(content, target_domain, quality):
                yield item
        elif self.dataset_type == DatasetType.CODING:
            for item in self._construct_coding_adaptive(content, quality):
                yield item
        elif self.dataset_type == DatasetType.REASONING:
            for item in self._construct_reasoning_adaptive(content, quality):
                yield item
        elif self.dataset_type == DatasetType.CONVERSATIONAL:
            for item in self._construct_conversational_adaptive(content, quality):
                yield item
        elif self.dataset_type == DatasetType.TOOL_CALLING:
            for item in self._construct_tool_calling_adaptive(content, quality):
                yield item
        elif self.dataset_type == DatasetType.TRAJECTORY:
            for item in self._construct_trajectory_adaptive(content, quality):
                yield item
        elif self.dataset_type == DatasetType.MULTIMODAL:
            for item in self._construct_multimodal_adaptive(content, filtered_sample, quality):
                yield item
        else:
            async for item in self._construct_sft_adaptive(content, target_domain, quality):
                yield item

        # Generate synthetic samples if configured
        if self.synthetic_ratio > 0 and quality > 0.6:
            async for synthetic in self._augment_synthetic(filtered_sample, intent.domain):
                yield synthetic

    async def _construct_sft_adaptive(
        self,
        content: str,
        target_domain: str,
        quality: float
    ) -> AsyncGenerator[ConstructedSample, None]:
        """Construct SFT samples with adaptive difficulty, using LLM when available."""
        # --- Sanitize target_domain: if it looks like dumped JSON,
        #     extract the real domain or fall back to a safe default ---
        target_domain = _sanitize_target_domain(target_domain)

        # --- Skip garbage / anti-bot content early ---
        if _is_garbage_content(content):
            return

        # Split into logical chunks
        chunks = self._adaptive_chunk(content, max_length=1500)

        # If LLM is available, use it to generate high-quality SFT samples
        if self.router:
            import logging
            import json
            logger = logging.getLogger(__name__)
            for i, chunk in enumerate(chunks[:5]):  # Limit chunks to avoid too many API calls
                difficulty = self._assess_chunk_difficulty(chunk)

                # Check if chunk content has domain keyword alignment
                domain_str = f' specializing in the "{target_domain}" domain' if target_domain and target_domain.lower() in chunk.lower() else ""

                prompt = f"""You are an AI dataset engineering assistant. Given the following reference text, generate exactly 2 high-quality, diverse instruction-response training pairs for an AI assistant{domain_str}.

<rules>
1. The instruction must be a natural, realistic user prompt asking directly about the concepts in the reference text. DO NOT mention "news" unless the text is about news. DO NOT reference terms like "chunk", "text", or "reference document".
2. The response must be a comprehensive, complete, and factually correct answer answering the instruction based *only* on the reference text. Do not make up facts.
3. The content generated strictly aligns with the reference text.
4. Output strictly in JSON format as a list of objects.
</rules>

<example>
<reference_text>
The quicksort algorithm uses divide-and-conquer. It picks an element as pivot and partitions the array around it. The time complexity is O(n log n) on average.
</reference_text>
<output>
[
  {{
    "instruction": "What is the average time complexity of the quicksort algorithm and what design paradigm does it use?",
    "response": "Quicksort has an average time complexity of O(n log n) and is built on the divide-and-conquer design paradigm."
  }},
  {{
    "instruction": "Explain how partitioning works in quicksort.",
    "response": "In quicksort, partitioning works by picking a pivot element from the array and placing all elements smaller than the pivot to its left, and all elements larger to its right."
  }}
]
</output>
</example>

<reference_text>
{chunk}
</reference_text>

Output strictly in JSON format as a list of objects:
"""
                try:
                    # Retry loop for LLM generation (up to 3 attempts with backoff)
                    generated_pairs = []
                    for attempt in range(3):
                        try:
                            response = await self.router.route(
                                task=TaskType.STRUCTURED_OUTPUT,
                                prompt=prompt,
                                system_prompt="You are a dataset engineering expert. Output strictly valid JSON arrays.",
                                temperature=0.3
                            )
                            if response and response.content:
                                raw = response.content.strip()
                                generated_pairs = _extract_json_array(raw)
                                if generated_pairs:
                                    break
                        except Exception as route_err:
                            logger.warning(f"LLM route attempt {attempt+1} failed: {route_err}")
                            await asyncio.sleep(0.5 * (attempt + 1))

                    if generated_pairs:
                        for pair in generated_pairs:
                            inst = pair.get("instruction", "")
                            resp = pair.get("response", "")
                            
                            if not inst or not resp or _is_garbage_content(resp):
                                continue

                            # Coerce lists/dicts to strings
                            if isinstance(inst, (list, dict)):
                                inst = json.dumps(inst, ensure_ascii=False)
                            else:
                                inst = str(inst)
                                
                            if isinstance(resp, (list, dict)):
                                resp = json.dumps(resp, ensure_ascii=False)
                            else:
                                resp = str(resp)

                            s = ConstructedSample(
                                instruction=inst,
                                response=resp,
                                metadata={"type": "llm_generated", "domain": target_domain},
                                difficulty_tier=difficulty,
                                curriculum_order=i
                            )
                            self._difficulty_distribution[s.difficulty_tier] += 1
                            yield s
                        continue  # Successfully generated via LLM
                except Exception as e:
                    logger.warning(f"LLM sample generation failed for chunk {i}: {e}.")

        # Fallback Heuristics - ONLY run if chunk is clean and domain-relevant
        for i, chunk in enumerate(chunks):
            if _is_garbage_content(chunk):
                continue
            
            # Require domain relevance in fallback mode to prevent cross-domain leaks
            if target_domain and target_domain.lower() not in ("general", "custom", "sft"):
                if target_domain.lower() not in chunk.lower():
                    continue

            difficulty = self._assess_chunk_difficulty(chunk)

            # Create clean Q&A pair only if chunk is genuinely informative
            qa = self._generate_qa_pair(chunk, target_domain)
            if qa and not _is_garbage_content(qa.get("response", "")):
                s = ConstructedSample(
                    instruction=qa["question"],
                    response=qa["answer"],
                    metadata={"type": "qa", "domain": target_domain, "generated": True},
                    difficulty_tier=difficulty,
                    curriculum_order=i
                )
                self._difficulty_distribution[s.difficulty_tier] += 1
                yield s

    def _construct_rag_adaptive(
        self,
        content: str,
        target_domain: str,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct RAG-optimized samples."""
        samples = []

        # Create context-chunk pairs
        chunks = self._adaptive_chunk(content, max_length=500)

        for i, chunk in enumerate(chunks):
            questions = [
                f"What does this passage tell us about {target_domain}?",
                f"Based on this, explain {target_domain}.",
                f"Extract key information about {target_domain}.",
            ]

            for q_idx, question in enumerate(questions[:2]):
                samples.append(ConstructedSample(
                    instruction=question,
                    response=chunk,
                    input=chunk,
                    metadata={
                        "type": "rag",
                        "chunk_index": i,
                        "total_chunks": len(chunks),
                        "domain": target_domain
                    },
                    difficulty_tier=3,
                    curriculum_order=i * 10 + q_idx,
                ))

        return samples[:30]

    def _construct_coding_adaptive(
        self,
        content: str,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct coding samples with language detection."""
        samples = []

        # Extract code blocks
        code_blocks = re.findall(r'```(\w*)\n(.*?)```', content, re.DOTALL)
        code_blocks += [(ext, code) for ext, code in self._extract_inline_code(content)]

        for i, (lang, code) in enumerate(code_blocks[:20]):
            if len(code) < 20:
                continue

            difficulty = self._assess_code_difficulty(code, lang)

            samples.append(ConstructedSample(
                instruction=f"Write a {lang or 'programming'} code example demonstrating this concept:",
                response=code.strip(),
                metadata={
                    "type": "coding",
                    "language": lang or "unknown",
                    "lines": code.count('\n') + 1,
                },
                difficulty_tier=difficulty,
                curriculum_order=i,
            ))

        return samples

    def _construct_reasoning_adaptive(
        self,
        content: str,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct reasoning/CoT samples."""
        samples = []

        # Identify statements/claims
        sentences = re.split(r'[.!?]+', content)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20][:20]

        for i, sentence in enumerate(sentences):
            # Generate step-by-step reasoning
            steps = self._generate_reasoning_steps(sentence)

            if steps:
                samples.append(ConstructedSample(
                    instruction=f"Analyze and reason through: {sentence}",
                    response="\n".join(steps),
                    metadata={
                        "type": "reasoning",
                        "steps": len(steps),
                        "reasoning_type": "chain_of_thought"
                    },
                    difficulty_tier=4,
                    curriculum_order=i,
                ))

        return samples[:15]

    def _construct_conversational_adaptive(
        self,
        content: str,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct conversational samples."""
        samples = []

        # Try to identify dialogue patterns
        lines = content.split('\n')
        lines = [l.strip() for l in lines if l.strip() and len(l.strip()) > 5][:40]

        for i in range(0, len(lines) - 1, 2):
            user = lines[i]
            assistant = lines[i+1] if i+1 < len(lines) else ""

            if user and assistant and len(user) > 5 and len(assistant) > 5:
                samples.append(ConstructedSample(
                    instruction=user,
                    response=assistant,
                    metadata={"type": "conversational", "turn": i // 2},
                    difficulty_tier=2,
                    curriculum_order=i // 2,
                    format="chatml"
                ))

        return samples[:20]

    def _construct_tool_calling_adaptive(
        self,
        content: str,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct tool-calling dataset samples."""
        samples = []

        # Look for API patterns, function calls, commands
        api_patterns = re.findall(r'(?:get|post|put|delete|create|update)\s+\w+', content, re.IGNORECASE)
        function_patterns = re.findall(r'def\s+(\w+)\s*\(', content)
        command_patterns = re.findall(r'`[^`]+`', content)

        for i, pattern in enumerate(api_patterns + function_patterns + command_patterns[:10]):
            tool_name = self._extract_tool_name(pattern)

            samples.append(ConstructedSample(
                instruction=f"Call the tool: {tool_name}",
                response=self._generate_tool_response(tool_name, content),
                metadata={
                    "type": "tool_calling",
                    "tool_name": tool_name,
                    "format": "function_call"
                },
                difficulty_tier=3,
                curriculum_order=i,
            ))

        return samples[:15]

    def _construct_trajectory_adaptive(
        self,
        content: str,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct agent trajectory samples."""
        samples = []

        # Create multi-step trajectories
        sections = content.split('\n\n')[:5]

        for i, section in enumerate(sections):
            trajectory = [
                {"step": 1, "action": "observe", "state": section[:100]},
                {"step": 2, "action": "reason", "state": "analysis"},
                {"step": 3, "action": "act", "state": section[:200]},
            ]

            samples.append(ConstructedSample(
                instruction=f"Given this context, determine the next step:\n{section[:300]}",
                response=json.dumps(trajectory, indent=2),
                metadata={"type": "trajectory", "steps": 3},
                difficulty_tier=4,
                curriculum_order=i,
                format="json"
            ))

        return samples[:10]

    def _construct_multimodal_adaptive(
        self,
        content: str,
        filtered_sample,
        quality: float
    ) -> list[ConstructedSample]:
        """Construct multimodal samples combining text/image/code."""
        samples = []

        metadata = getattr(filtered_sample, 'metadata', {})

        # Image caption pair
        if 'image' in metadata or 'image_url' in metadata:
            samples.append(ConstructedSample(
                instruction="Describe this image in detail:",
                response=content[:500],
                input=metadata.get('image_url', ''),
                metadata={"type": "multimodal", "modality": "image_text"},
                difficulty_tier=3,
                curriculum_order=0,
            ))

        # Code + explanation
        code_blocks = re.findall(r'```[\w]*\n(.*?)```', content, re.DOTALL)
        for i, code in enumerate(code_blocks[:5]):
            samples.append(ConstructedSample(
                instruction="Explain what this code does:",
                response=self._explain_code(code),
                input=code,
                metadata={"type": "multimodal", "modality": "code_explanation"},
                difficulty_tier=3,
                curriculum_order=i,
            ))

        return samples[:10]

    async def _augment_synthetic(
        self,
        filtered_sample,
        target_domain: str
    ) -> AsyncGenerator[ConstructedSample, None]:
        """Generate synthetic augmentation using AI."""
        if not self.router:
            return

        content = filtered_sample.content if hasattr(filtered_sample, 'content') else str(filtered_sample)

        try:
            # Generate paraphrase
            prompt = f"""Generate a different version of the following text that preserves the meaning but uses different wording.
            Focus on the {target_domain} domain.

            Text: {content[:1000]}

            Paraphrased version:"""

            response = await self.router.route(TaskType.PARAPHRASING, prompt)

            if response and response.content:
                yield ConstructedSample(
                    instruction=filtered_sample.metadata.get('original_instruction', 'Explain this concept:'),
                    response=response.content,
                    metadata={
                        "type": "synthetic",
                        "augmentation": "paraphrase",
                        "source_quality": filtered_sample.quality_score
                    },
                    difficulty_tier=3,
                    curriculum_order=len(self._constructed_samples),
                )

        except Exception:
            pass

    def _adaptive_chunk(self, content: str, max_length: int = 500) -> list[str]:
        """Split content into adaptive chunks."""
        chunks = []

        # Try paragraph boundaries first
        paragraphs = content.split('\n\n')
        current_chunk = ""

        for para in paragraphs:
            if len(current_chunk) + len(para) < max_length:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = para + "\n\n"

        if current_chunk:
            chunks.append(current_chunk.strip())

        # If no paragraphs, split by sentences
        if not chunks:
            sentences = re.split(r'(?<=[.!?])\s+', content)
            current_chunk = ""

            for sentence in sentences:
                if len(current_chunk) + len(sentence) < max_length:
                    current_chunk += sentence + " "
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + " "

            if current_chunk:
                chunks.append(current_chunk.strip())

        return [c for c in chunks if len(c) > 20]

    def _assess_chunk_difficulty(self, chunk: str) -> int:
        """Assess cognitive complexity tier following Bloom's Taxonomy (Chip Huyen AI Engineering).
        
        Tier 1 (Remember/Recall): Factual recall, definitions.
        Tier 2 (Understand): Summarization, concept explanations.
        Tier 3 (Apply/Analyze): Procedural implementation, comparative analysis.
        Tier 4 (Evaluate/Synthesize): Cause-and-effect reasoning, trade-off analysis.
        Tier 5 (Create/Critique): Complex edge case diagnostic, architectural synthesis, research proofs.
        """
        score = 1
        text_lower = chunk.lower()
        words = chunk.split()

        # 1. Structural & Syntactic Complexity
        if len(words) > 80:
            score += 1

        # 2. Cognitive Operators (Bloom's Taxonomy Keywords)
        t3_indicators = ["implement", "calculate", "execute", "compare", "contrast", "analyze"]
        t4_indicators = ["evaluate", "synthesize", "trade-off", "architecture", "cause", "effect", "optimise"]
        t5_indicators = ["proof", "theorem", "diagnostic", "edge case", "vulnerability", "benchmark", "formal"]

        if any(ind in text_lower for ind in t5_indicators):
            score += 3
        elif any(ind in text_lower for ind in t4_indicators):
            score += 2
        elif any(ind in text_lower for ind in t3_indicators):
            score += 1

        # 3. Technical & Domain Density
        technical_terms = sum(1 for t in [
            'algorithm', 'complexity', 'thread', 'concurrency', 'latency',
            'throughput', 'quantization', 'gradient', 'optimization', 'invariant'
        ] if t in text_lower)
        if technical_terms >= 3:
            score += 1

        return min(5, max(1, score))

    def _assess_code_difficulty(self, code: str, language: str) -> int:
        """Assess difficulty of code."""
        score = 1

        # Line count
        lines = code.count('\n') + 1
        if lines > 20:
            score += 1
        if lines > 50:
            score += 1

        # Complexity indicators
        complexity_indicators = ['for', 'while', 'if', 'try', 'except', 'class', 'def']
        count = sum(1 for ind in complexity_indicators if ind in code)
        score += min(2, count)

        # Special language features
        if language in ['python', 'javascript']:
            if 'async' in code or 'await' in code:
                score += 1
        if language in ['java', 'cpp', 'c']:
            if 'template' in code or '<' in code:
                score += 1

        return min(5, max(1, score))

    def _generate_reasoning_steps(self, sentence: str) -> list[str]:
        """Generate reasoning steps for a statement based on actual content."""
        steps = [f"Given: {sentence}"]

        # Break sentence into meaningful components
        words = sentence.split()
        has_question = "?" in sentence
        has_numbers = bool(re.search(r'\d+', sentence))
        has_comparison = bool(re.search(r'\b(better|worse|more|less|than|vs|compared)\b', sentence.lower()))

        if has_question:
            steps.append("Observation: This is a question that requires analytical reasoning.")
            steps.append("Analysis: Identifying the key components of the query...")
            if has_numbers:
                steps.append("Quantitative reasoning: Examining the numerical relationships.")
        elif has_comparison:
            steps.append("Observation: This statement presents a comparative analysis.")
            steps.append("Analysis: Evaluating the entities being compared...")
        elif has_numbers:
            steps.append("Observation: This statement contains quantitative information.")
            steps.append("Analysis: Interpreting the numerical data and its implications...")
        else:
            steps.append("Observation: Breaking down the key components of this statement.")

        # Add content-aware analysis from sentence structure
        if len(words) > 15:
            steps.append("Context: Multiple clauses detected - analyzing relationships between ideas.")
        if any(term in sentence.lower() for term in ['because', 'since', 'therefore', 'thus']):
            steps.append("Causal reasoning: Tracing cause-and-effect relationships.")
        if any(term in sentence.lower() for term in ['if', 'then', 'otherwise', 'unless']):
            steps.append("Conditional reasoning: Evaluating dependencies and edge cases.")

        # Add entity extraction
        capitalized = [w for w in words if w and w[0].isupper() and w.lower() not in ('i', 'the', 'a', 'an')]
        if capitalized:
            entities = ', '.join(capitalized[:5])
            steps.append(f"Entity identification: Key concepts identified - {entities}.")

        # Synthesize conclusion from actual content
        conclusion_parts = []
        if len(words) > 5:
            conclusion_parts.append("Synthesizing the key findings from the analysis.")
        if has_question:
            conclusion_parts.append("Formulating a response based on the evidence presented.")
        else:
            conclusion_parts.append("Drawing a conclusion supported by the reasoning chain.")

        steps.append(f"Conclusion: {' '.join(conclusion_parts)}")

        return steps

    def _generate_qa_pair(self, text: str, domain: str) -> dict | None:
        """Generate a Q&A pair from text."""
        # Simple heuristic Q&A generation
        if len(text) < 50:
            return None

        # Extract first sentence as answer
        sentences = re.split(r'[.!?]+', text)
        if sentences:
            answer = sentences[0].strip()
            if len(answer) > 20:
                return {
                    "question": f"What is the main point about {domain or 'this topic'}?",
                    "answer": answer
                }

        return None

    def _extract_tool_name(self, pattern: str) -> str:
        """Extract tool/function name from pattern."""
        words = pattern.split()
        if words:
            return words[-1].strip('()`')
        return "unknown_tool"

    def _generate_tool_response(self, tool_name: str, content: str) -> str:
        """Generate mock tool response."""
        return json.dumps({
            "tool": tool_name,
            "status": "success",
            "result": content[:200]
        })

    def _explain_code(self, code: str) -> str:
        """Generate explanation of code."""
        return f"This code demonstrates the following:\n1. Core functionality implementation\n2. Error handling approach\n3. Best practices application"

    def _simple_summarize(self, text: str, max_length: int = 150) -> str:
        """Simple extractive summarization."""
        sentences = text.split('.')
        if len(sentences) <= 2:
            return text[:max_length] + ("..." if len(text) > max_length else "")

        summary = sentences[0] + "."
        current_length = len(summary)

        for sentence in sentences[1:]:
            if current_length + len(sentence) < max_length:
                summary += " " + sentence + "."
                current_length += len(sentence)
            else:
                break

        return summary

    def _extract_inline_code(self, content: str) -> list[tuple[str, str]]:
        """Extract inline code blocks."""
        code_blocks = []
        matches = re.findall(r'<code[^>]*>(.*?)</code>', content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            if len(match) > 10:
                code_blocks.append(("html", match))
        return code_blocks

    async def split_train_val_test(
        self,
        samples: list[ConstructedSample],
        ratios: tuple[float, float, float] = (0.8, 0.1, 0.1),
        stratify: bool = True
    ) -> tuple[list[ConstructedSample], list[ConstructedSample], list[ConstructedSample]]:
        """Split samples with optional stratification."""
        if not samples:
            return [], [], []

        if not stratify:
            total = len(samples)
            train_end = int(total * ratios[0])
            val_end = train_end + int(total * ratios[1])
            return samples[:train_end], samples[train_end:val_end], samples[val_end:]

        # Stratified split by difficulty
        buckets: dict[int, list[ConstructedSample]] = {}
        for s in samples:
            tier = s.difficulty_tier
            if tier not in buckets:
                buckets[tier] = []
            buckets[tier].append(s)

        train, val, test = [], [], []

        for tier, tier_samples in buckets.items():
            total = len(tier_samples)
            train_end = int(total * ratios[0])
            val_end = train_end + int(total * ratios[1])
            train.extend(tier_samples[:train_end])
            val.extend(tier_samples[train_end:val_end])
            test.extend(tier_samples[val_end:])

        return train, val, test

    def get_construction_stats(self) -> dict:
        """Get construction statistics."""
        return {
            "total_samples": len(self._constructed_samples),
            "difficulty_distribution": self._difficulty_distribution.copy(),
            "current_schema": {
                "name": self.schema.name,
                "instruction_field": self.schema.instruction_field,
                "response_field": self.schema.response_field,
            },
            "synthetic_ratio": self.synthetic_ratio,
        }