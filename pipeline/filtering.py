"""Deterministic filtering with fixed thresholds and single quality formula."""
import hashlib
import math
import unicodedata
import statistics
from dataclasses import dataclass, field
from typing import AsyncGenerator, Optional, Callable
from collections import OrderedDict
import re
import asyncio

from core.provider_router import TaskType
from core.intent import UserIntent
from pipeline.quality_scorer import QualityScorer
from pipeline.hallucination_detector import HallucinationDetector
from pipeline.deduplication import DeduplicationEngine
from pipeline.diversity import DatasetDiversityAnalyzer, DiversityMetrics
from pipeline.quality_breakdown import (
    QualityScoreBreakdown,
    FilterThresholds,
    compute_final_score,
    DEFAULT_THRESHOLDS,
    DATASET_TYPE_THRESHOLDS,
    get_thresholds,
)
# New scoring components
from pipeline.llm_judge import LLMJudge, JudgeCache
from pipeline.semantic_scorer import SemanticQualityScorer
from pipeline.grounding import GroundingScoreCalculator, HallucinationDetector as HallucinationDetectorV2


@dataclass
class FilteredSample:
    """Filtered sample with comprehensive quality assessment."""
    content: str
    # Layered quality scores
    signal_score: float = 0.0
    statistical_score: float = 0.0
    semantic_score: float = 0.0
    llm_judge_score: float = 0.0
    compliance_score: float = 0.0  # 0.0 = fail, 1.0 = pass
    # Legacy scores (for backward compatibility)
    quality_score: float = 0.0
    relevance_score: float = 0.0
    toxicity_score: float = 0.0
    hallucination_risk: float = 0.0
    uniqueness_score: float = 0.0
    diversity_score: float = 0.0
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    embedding: list[float] | None = None
    source_url: str | None = None
    metadata: dict = field(default_factory=dict)
    filter_reason: str | None = None
    confidence: float = 1.0
    filters_applied: list[str] = field(default_factory=list)
    passed: bool = True
    # New deterministic breakdown
    quality_breakdown: QualityScoreBreakdown | None = None


# NOTE: FilterThresholds is imported from pipeline.quality_breakdown (line 19 above).
# Do NOT redefine it here — doing so would shadow the import and cause ``unexpected
# keyword argument 'signal'`` when the call site passes ``signal=...``.

class AdaptiveFilterEngine:
    """DEPRECATED: Thresholds are now static.

    Kept for backward compatibility. ``learn_thresholds`` is a no-op.
    Thresholds are now loaded statically via ``get_thresholds()``.
    """

    def __init__(self, config: dict):
        self.config = config
        dataset_type = config.get("dataset_type", "")
        self.thresholds = get_thresholds(dataset_type)
        self._score_history: list[float] = []
        self._initialized = True

    async def learn_thresholds(self, samples: list[dict]) -> None:
        """No-op: thresholds are static and never learned from data."""
        return

    def get_thresholds(self) -> FilterThresholds:
        """Return the static thresholds."""
        return self.thresholds

    def update_threshold(self, name: str, value: float) -> None:
        """Manually update a threshold (not recommended)."""
        if hasattr(self.thresholds, name):
            setattr(self.thresholds, name, value)


class FilteringPipeline:
    """Deterministic filtering pipeline with static thresholds."""

    def __init__(self, router, config: dict):
        self.router = router
        self.config = config
        self.adaptive_engine = AdaptiveFilterEngine(config)

        # Get base thresholds from dataset type or defaults
        base_thresholds = get_thresholds(config.get("dataset_type"))

        # Make all thresholds configurable per job with sensible defaults
        self._thresholds = FilterThresholds(
            signal=config.get("quality_threshold", base_thresholds.signal),  # quality_threshold -> signal
            statistical=config.get("statistical_threshold", base_thresholds.statistical),
            semantic=config.get("semantic_threshold", base_thresholds.semantic),
            reasoning=config.get("reasoning_threshold", base_thresholds.reasoning),
            grounding=config.get("grounding_threshold", base_thresholds.grounding),
            quality=config.get("overall_quality_threshold", base_thresholds.quality),  # legacy overall quality
            toxicity=config.get("toxicity_threshold", base_thresholds.toxicity),
            min_length=config.get("min_length", base_thresholds.min_length),
            max_length=config.get("max_length", base_thresholds.max_length),
        )

        # Relevance threshold (separate from quality thresholds)
        self.relevance_threshold = config.get("relevance_threshold", 0.5)

        # Configuration overrides (legacy, still respected)
        self.quality_threshold = config.get("quality_threshold", self._thresholds.signal)
        self.toxicity_threshold = config.get("toxicity_threshold", self._thresholds.toxicity)
        self.dedup_threshold = config.get("dedup_threshold", 0.85)
        self.min_length = config.get("min_length", self._thresholds.min_length)
        self.max_length = config.get("max_length", self._thresholds.max_length)

        # Quality engines (Phase 5)
        self.quality_scorer = QualityScorer(router=router)
        self.hallucination_detector = HallucinationDetector(router=router)
        self.dedup_engine = DeduplicationEngine(router=router, config=config)
        self.diversity_analyzer = DatasetDiversityAnalyzer(router=router)

        # Accumulated samples for batch diversity analysis
        self._accumulated_samples: list[str] = []
        self._diversity_batch_size = config.get("diversity_batch_size", 100)

        # Expanded toxicity detection patterns
        self._toxic_patterns = [
            # Hate speech
            r'\b(hate|kill|attack|terrorist|murder|torture|execut)\b',
            # Slurs
            r'(?:nigger|faggot|retard|kike|spic|chink|gook|wetback|raghead|tranny)',
            # Harassment
            r'\b(stupid|idiot|dumbass|worthless|pathetic|loser|trash)\b',
            # Threats
            r'\b(threaten|blackmail|extort|hostage|bomb|shoot|stab|kill)\b',
            # NSFW
            r'\b(porn|sex|nude|explicit|nsfw)\b',
            # Script injection
            r'<script|<iframe|onclick\s*=|onload\s*=|javascript:',
        ]

        # Deduplication cache (kept for backward compat)
        self._seen_hashes: dict[str, float] = {}
        self._minhash_cache: dict[str, tuple[set[str], float]] = {}
        self._minhash_cache_maxsize = 50000
        self._minhash_cache_ttl = 3600  # 1 hour TTL
        self._embedding_cache: OrderedDict[str, list[float]] = OrderedDict()
        self._embedding_cache_maxsize = 10000

        # Quality buckets for adaptive thresholds
        self._quality_buckets: list[list[float]] = [[] for _ in range(10)]

    async def filter(
        self,
        content,
        intent: UserIntent,
        context: dict | None = None,
        return_all: bool = False
    ) -> FilteredSample | None:
        """Filter a single content item with deterministic quality scoring."""
        content_text = content.content if hasattr(content, 'content') else str(content)
        thresholds = self._thresholds

        sample = FilteredSample(
            content=content_text,
            source_url=getattr(content, 'url', None),
            metadata=getattr(content, 'metadata', {}),
        )

        # --- 1. Compute ALL dimension scores (always) -------------------------
        # Use the new deterministic pipeline: each dimension is always computed,
        # even if it would fail a threshold.  Scoring and filtering are separate.

        signal_score, signal_issues = self._signal_quality(content_text)
        statistical_score, statistical_issues = await self._statistical_quality(content_text)
        semantic_score, semantic_issues = await self._semantic_quality(content_text)
        llm_judge_score, llm_judge_issues = await self._llm_judge_quality(content_text, intent.domain)
        compliance_score = self._check_compliance(content_text)

        # Store dimension scores on the sample for backward compatibility
        sample.signal_score = signal_score
        sample.statistical_score = statistical_score
        sample.semantic_score = semantic_score
        sample.llm_judge_score = llm_judge_score
        sample.compliance_score = compliance_score
        sample.issues.extend(signal_issues + statistical_issues + semantic_issues + llm_judge_issues)

        # --- 2. Build deterministic breakdown & compute final score -----------
        # The filter_passed flag is computed _after_ scoring, not during it.
        # We determine pass/fail by checking each dimension against thresholds.
        failed_dims: list[str] = []
        if signal_score < thresholds.signal:
            failed_dims.append("signal")
        if statistical_score < thresholds.statistical:
            failed_dims.append("statistical")
        if semantic_score < thresholds.semantic:
            failed_dims.append("semantic")
        if llm_judge_score < thresholds.reasoning:
            failed_dims.append("reasoning")
        if compliance_score < thresholds.grounding:
            failed_dims.append("compliance")

        passed = (len(failed_dims) == 0)

        # Build the immutable breakdown.  All fields required; no early-exit
        # logic can skip any dimension.
        breakdown = QualityScoreBreakdown(
            signal_score=signal_score,
            statistical_score=statistical_score,
            semantic_score=semantic_score,
            reasoning_score=llm_judge_score,
            grounding_score=compliance_score,
            confidence=1.0,
            filter_passed=passed,
            failed_dimensions=failed_dims,
        )

        # Single authoritative formula (never changes per sample)
        sample.quality_score = compute_final_score(breakdown)
        sample.quality_breakdown = breakdown

        # --- 3. Determine pass/fail reason for diagnostics --------------------
        if not passed:
            sample.filter_reason = f"failed_{'_'.join(failed_dims)}"
            sample.passed = False
        else:
            sample.passed = True

        # --- 4. Legacy length checks (preserved from old pipeline) ------------
        if len(content_text) < self.min_length:
            sample.issues.append(f"content_too_short_min_{self.min_length}")
            sample.filter_reason = "length_below_minimum"
            sample.passed = False
            if not return_all:
                return None

        if len(content_text) > self.max_length:
            sample.issues.append(f"content_too_long_max_{self.max_length}")
            sample.filter_reason = "length_exceeds_maximum"
            sample.passed = False
            if not return_all:
                return None

        # Relevance scoring
        sample.relevance_score = llm_judge_score

        # Toxicity check (expanded patterns)
        sample.toxicity_score = self._check_toxicity_adaptive(content_text)

        # Hallucination risk assessment (Phase 5: real detection)
        source_text = getattr(content, 'source_text', '') or getattr(content, 'metadata', {}).get('source_text', '') or ''
        try:
            hal_result = await asyncio.wait_for(
                self.hallucination_detector.evaluate(
                    instruction=content_text[:200],
                    response=content_text,
                    source_text=source_text,
                    source_url=getattr(content, 'url', ''),
                ),
                timeout=5.0
            )
            sample.hallucination_risk = hal_result.hallucination_risk_score
            sample.metadata['hallucination_details'] = {
                'source_grounding': hal_result.source_grounding_score,
                'citation_match': hal_result.citation_match_score,
                'risk_level': hal_result.risk_level,
                'flagged_patterns': hal_result.flagged_patterns,
            }
            if hal_result.risk_level in ('high', 'critical'):
                sample.issues.append(f"high_hallucination_risk_{hal_result.risk_level}")
        except Exception:
            sample.hallucination_risk = self._assess_hallucination_risk(content_text)

        # Uniqueness check (Phase 5: 4-level dedup)
        try:
            dup_result = await asyncio.wait_for(
                self.dedup_engine.check_and_add(content_text),
                timeout=5.0
            )
            is_dup = dup_result.is_duplicate
            dup_reason = dup_result.match_type
            uniqueness = 1.0 - dup_result.duplicate_score
        except Exception:
            is_dup, dup_reason, uniqueness = await self._check_uniqueness_adaptive(
                content_text, thresholds
            )
        sample.uniqueness_score = uniqueness
        if is_dup:
            sample.issues.append(f"duplicate: {dup_reason}")

        # Semantic quality scoring (Phase 5) - Note: we already did semantic quality above, but this is for the quality_scorer which might be different
        try:
            qs_result = await asyncio.wait_for(
                self.quality_scorer.score(
                    instruction=content_text[:500],
                    response=content_text,
                    domain=target_domain,
                ),
                timeout=5.0
            )
            sample.metadata['quality_score_data'] = qs_result.to_dict()
        except Exception:
            pass

        # Diversity scoring (semantic diversity)
        sample.diversity_score = await self._score_diversity(content_text)

        # Accumulate passing samples for batch diversity analysis
        self._accumulated_samples.append(content_text)
        if len(self._accumulated_samples) >= self._diversity_batch_size:
            try:
                batch_metrics = await self.diversity_analyzer.analyze(
                    [{"content": t} for t in self._accumulated_samples]
                )
                sample.metadata['batch_diversity'] = {
                    'overall': batch_metrics.overall_diversity,
                    'topic': batch_metrics.topic_diversity,
                    'source': batch_metrics.source_diversity,
                    'instruction': batch_metrics.instruction_diversity,
                    'response': batch_metrics.response_diversity,
                    'domain': batch_metrics.domain_diversity,
                }
            except Exception:
                pass
            self._accumulated_samples = []

        # Embedding generation for future dedup (old path, still used by dedup engine)
        if self.router:
            try:
                emb_response = await asyncio.wait_for(
                    self.router.embed(content_text[:1000]),
                    timeout=5.0
                )
                sample.embedding = emb_response.embedding
                content_key = hashlib.md5(content_text[:500].encode()).hexdigest()
                self._embedding_cache[content_key] = emb_response.embedding
                self._embedding_cache.move_to_end(content_key)
                while len(self._embedding_cache) > self._embedding_cache_maxsize:
                    self._embedding_cache.popitem(last=False)
            except Exception:
                pass

        # Calculate overall confidence
        sample.confidence = self._calculate_confidence(sample)

        # Record for threshold learning
        self._record_quality(sample.quality_score)

        # Generate warnings
        sample.warnings = self._generate_warnings(sample, thresholds)

        # Apply filters based on thresholds
        should_filter = self._should_filter(sample, thresholds)
        sample.passed = not should_filter

        if should_filter:
            if not return_all:
                return None

        sample.filters_applied = self._get_applied_filters(sample, thresholds)

        return sample

    # Anti-bot / garbage content patterns — content that is definitely not
    # useful for dataset construction. Aggressively downscored.
    _ANTI_BOT_PATTERNS: list[str] = [
        r"JavaScript\s+is\s+disabled",
        r"JavaScript\s+not\s+enabled",
        r"enable\s+JavaScript\s+(in\s+your\s+browser|to\s+continue)",
        r"verify\s+you\s+(are|'re)\s+(not\s+)?a\s+(robot|human)",
        r"prove\s+you\s+(are|'re)\s+(not\s+)?a\s+(robot|human)",
        r"captcha",
        r"CAPTCHA",
        r"cf-browser-verification",
        r"cloudflare\s+(?:\w+\s+)*challenge",
        r"please\s+wait\s+while\s+we\s+verify",
        r"checking\s+your\s+browser",
        r"just\s+a\s+moment.*verif",
        r"DDOS\s+protection",
        r"are\s+you\s+a\s+human",
        r"too\s+many\s+requests",
        r"access\s+denied",
        r"blocked",
        r"rate\s+limit",
        r"429\s+too\s+many\s+requests",
        r"403\s+forbidden",
        r"please\s+turn\s+JavaScript\s+on",
        r"you\s+need\s+to\s+enable\s+JavaScript",
        r"browser\s+does\s+not\s+support\s+JavaScript",
    ]

    _BOT_COMPILED: list = None  # compiled lazily

    @classmethod
    def _get_bot_patterns(cls) -> list:
        if cls._BOT_COMPILED is None:
            cls._BOT_COMPILED = [re.compile(p, re.IGNORECASE) for p in cls._ANTI_BOT_PATTERNS]
        return cls._BOT_COMPILED

    def _signal_quality(self, text: str) -> tuple[float, list[str]]:
        """Layer 1: Signal-based quality (fast, cheap, rule-based)"""
        issues = []
        score = 1.0

        # --- Anti-bot / garbage content check (runs first — highest priority) ---
        for pattern in self._get_bot_patterns():
            if pattern.search(text):
                # Aggressively downscore — this is not real content
                score -= 0.95
                issues.append("anti_bot_garbage")
                break  # one match is enough

        # Length heuristics
        if len(text) < 10:
            score -= 0.4
            issues.append("too_short")
        elif len(text) > 100000:
            score -= 0.2
            issues.append("very_long")

        # Whitespace normalization quality
        original_len = len(text)
        normalized = ' '.join(text.split())
        if original_len > 0:
            whitespace_ratio = len(normalized) / original_len
            if whitespace_ratio < 0.5:
                score -= 0.3
                issues.append("excessive_whitespace")

        # Special character / boilerplate ratio
        special_chars = sum(1 for c in text if not c.isalnum() and not c.isspace())
        if len(text) > 0:
            special_ratio = special_chars / len(text)
            if special_ratio > 0.5:
                score -= 0.3
                issues.append("high_special_char_ratio")

        # Repeated character detection
        if re.search(r'(.)\1{4,}', text):
            score -= 0.2
            issues.append("repeated_characters")

        # Default language detection (simple heuristic)
        # Check if text contains mostly ASCII characters
        ascii_chars = sum(1 for c in text if ord(c) < 128)
        if len(text) > 0:
            ascii_ratio = ascii_chars / len(text)
            if ascii_ratio < 0.5:
                score -= 0.2
                issues.append("low_ascii_ratio")

        return max(0.0, min(1.0, score)), issues

    async def _statistical_quality(self, text: str) -> tuple[float, list[str]]:
        """Layer 2: Statistical quality (medium cost)"""
        issues = []
        score = 1.0

        # Perplexity approximation using character frequency
        if len(text) > 10:
            # Simple character frequency analysis
            freq = {}
            for c in text:
                freq[c] = freq.get(c, 0) + 1

            # Calculate entropy
            entropy = 0.0
            text_len = len(text)
            for count in freq.values():
                p = count / text_len
                if p > 0:
                    entropy -= p * math.log2(p)

            # Normalize entropy to 0-1 scale (max entropy for ASCII is ~7)
            normalized_entropy = min(1.0, entropy / 7.0)
            # Convert to score (higher entropy = higher score, but too high might be random)
            if normalized_entropy < 0.3:
                score -= 0.3
                issues.append("low_entropy")
            elif normalized_entropy > 0.9:
                score -= 0.2
                issues.append("high_entropy_possible_random")

        # Lexical diversity (type-token ratio)
        words = text.lower().split()
        if len(words) > 0:
            unique_words = len(set(words))
            ttr = unique_words / len(words)
            if ttr < 0.3:
                score -= 0.2
                issues.append("low_lexical_diversity")
            elif ttr > 0.9:
                score -= 0.1
                issues.append("very_high_lexical_diversity_unusual")

        # Information density (approximation)
        # Count of meaningful words vs total words
        meaningful_words = [w for w in words if len(w) > 2 and w.isalpha()]
        if len(words) > 0:
            meaningful_ratio = len(meaningful_words) / len(words)
            if meaningful_ratio < 0.3:
                score -= 0.2
                issues.append("low_information_density")

        return max(0.0, min(1.0, score)), issues

    async def _semantic_quality(self, text: str) -> tuple[float, list[str]]:
        """Layer 3: Semantic quality (higher cost)"""
        issues = []
        score = 0.5  # Start neutral

        if not self.router:
            # If no router available, return neutral score
            return score, issues

        try:
            # Get embedding for the text with timeout to prevent hangs
            embedding_response = await asyncio.wait_for(
                self.router.embed(text[:512]),  # Limit length for efficiency
                timeout=5.0
            )
            embedding = embedding_response.embedding

            # For now, we'll use a simple heuristic based on embedding properties
            # In a real implementation, we would compare against domain-specific embeddings

            # Check if embedding has reasonable magnitude (not all zeros or extremely large)
            magnitude = sum(x*x for x in embedding) ** 0.5
            if magnitude == 0:
                score = 0.1
                issues.append("zero_embedding")
            elif magnitude > 100:
                score = 0.2
                issues.append("large_embedding_magnitude")
            else:
                # Moderate magnitude is good
                score += 0.2

            # Check embedding diversity (standard deviation of values)
            if len(embedding) > 0:
                mean_val = sum(embedding) / len(embedding)
                variance = sum((x - mean_val) ** 2 for x in embedding) / len(embedding)
                std_dev = variance ** 0.5
                if std_dev < 0.01:
                    score -= 0.2
                    issues.append("low_embedding_diversity")
                elif std_dev > 1.0:
                    score += 0.1
                    issues.append("high_embedding_diversity")

        except Exception as e:
            # If embedding fails, we can't assess semantic quality
            issues.append(f"embedding_failed: {str(e)[:50]}")
            score = 0.3  # Slightly below average

        return max(0.0, min(1.0, score)), issues

    async def _llm_judge_quality(self, text: str, target_domain: str) -> tuple[float, list[str]]:
        """Layer 4: LLM-judge quality (expensive, applied selectively)"""
        issues = []
        score = 0.5  # Start neutral

        if not self.router:
            # If no router available, return neutral score
            return score, issues

        try:
            # For now, we'll use a simple heuristic - in reality this would call an LLM
            # with a prompt asking it to judge the quality

            # Simple heuristic: longer, well-formatted text tends to be higher quality
            if len(text) > 100:
                score += 0.1
            if len(text) > 500:
                score += 0.1

            # Check for structure indicators
            if '\n\n' in text:  # Has paragraphs
                score += 0.1
            if text.count('.') > 3:  # Has multiple sentences
                score += 0.1
            if text.count(':') > 0:  # Has colons (often indicates structure)
                score += 0.05

            # Penalize excessive repetition
            words = text.lower().split()
            if len(words) > 10:
                unique_ratio = len(set(words)) / len(words)
                if unique_ratio < 0.4:
                    score -= 0.2
                    issues.append("low_word_diversity")

            # Domain relevance check (simple)
            if target_domain:
                domain_words = set(target_domain.lower().split())
                text_words = set(text.lower().split())
                if len(domain_words) > 0:
                    overlap = len(domain_words & text_words) / len(domain_words)
                    score += overlap * 0.2  # Up to 0.2 bonus for domain relevance

        except Exception as e:
            issues.append(f"llm_judge_error: {str(e)[:50]}")
            score = 0.4  # Slightly below average

        return max(0.0, min(1.0, score)), issues

    def _check_compliance(self, text: str) -> float:
        """Layer 5: Compliance & safety (mandatory for enterprise)"""
        score = 1.0  # Start with perfect compliance

        # Check for PII patterns (simplified)
        pii_patterns = [
            r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
            r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',  # Credit card
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[\s-]?\d{3}[\s-]?\d{4}\b',  # Phone number
        ]

        for pattern in pii_patterns:
            if re.search(pattern, text, re.IGNORECASE):
                score -= 0.3  # Significant penalty for PII
                break  # Only penalize once for simplicity

        # Check for toxic content (simplified)
        toxic_patterns = [
            r'\b(hate|kill|attack|terrorist|murder|torture|execut|nigger|faggot|retard|kike|spic|chink|gook|wetback|raghead|tranny)\b',
            r'\b(stupid|idiot|dumbass|worthless|pathetic|loser|trash)\b',
            r'\b(porn|sex|nude|explicit|nsfw)\b',
        ]

        toxic_count = 0
        for pattern in toxic_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            toxic_count += len(matches)

        if toxic_count > 0:
            score -= min(0.4, toxic_count * 0.1)  # Penalize based on count

        # Check for excessive profanity (simplified)
        profanity_words = ['damn', 'hell', 'shit', 'fuck', 'bitch', 'ass']
        profanity_count = 0
        for word in profanity_words:
            profanity_count += len(re.findall(rf'\b{word}\b', text, re.IGNORECASE))

        if profanity_count > 3:
            score -= 0.2

        # Ensure score doesn't go below 0
        return max(0.0, score)

    def _calculate_entropy(self, text: str) -> float:
        """Calculate character entropy (information density)."""
        if not text:
            return 0.0
        counts = {}
        for char in text:
            counts[char] = counts.get(char, 0) + 1
        entropy = 0.0
        total = len(text)
        for count in counts.values():
            p = count / total
            entropy -= p * math.log2(p)
        return entropy

    async def _score_quality_adaptive(
        self,
        text: str,
        thresholds: FilterThresholds
    ) -> tuple[float, list[str]]:
        """Score content quality with adaptive thresholds."""
        # 1. Unicode Normalization
        text = unicodedata.normalize("NFKC", text)
        issues = []

        # 2. Entropy Analysis
        entropy = self._calculate_entropy(text)
        if entropy < 3.0:
            issues.append("extremely_low_entropy")
        elif entropy > 7.8:
            issues.append("extremely_high_entropy_likely_random")

        # 3. Code vs Prose Isolation
        code_blocks = re.findall(r'```(?:\w*)\n(.*?)```', text, re.DOTALL)
        prose_content = re.sub(r'```(?:\w*)\n(.*?)```', ' ', text, flags=re.DOTALL)

        # Clean prose of markdown headers, list markers, and page borders
        cleaned_prose = re.sub(r'^#{1,6}\s+', ' ', prose_content, flags=re.MULTILINE)
        cleaned_prose = re.sub(r'^\s*[-*+•]\s+', ' ', cleaned_prose, flags=re.MULTILINE)
        cleaned_prose = re.sub(r'^\s*\d+\.\s+', ' ', cleaned_prose, flags=re.MULTILINE)
        cleaned_prose = re.sub(r'[-=~_*#]{3,}', ' ', cleaned_prose)

        # 4. Length-based scoring on normalized text
        length_score = 1.0
        if len(text) < thresholds.min_length:
            issues.append("very_short")
            length_score -= 0.3
        elif len(text) > thresholds.max_length:
            issues.append("very_long")
            length_score -= 0.1

        # 5. Vocabulary Diversity & Repetition (on cleaned prose)
        repetition = self._calculate_repetition(cleaned_prose)
        if repetition > 0.25:
            issues.append(f"high_repetition_{repetition:.2f}")
            length_score -= 0.3

        prose_words = cleaned_prose.lower().split()
        if len(prose_words) > 15:
            type_token_ratio = len(set(prose_words)) / len(prose_words)
            if type_token_ratio < 0.35:
                issues.append("low_vocabulary_diversity")
                length_score -= 0.2

        # 6. URL density (excluding code blocks)
        url_count = len(re.findall(r'http[s]?://\S+', cleaned_prose))
        word_count = len(cleaned_prose.split())
        if word_count > 10 and url_count > word_count * 0.15:
            issues.append("too_many_urls")
            length_score -= 0.2

        # 7. Garbled text detection
        if self._detect_garbled_text(text):
            issues.append("garbled_text")
            length_score -= 0.4

        # 8. Structure quality
        structure_score = self._assess_structure_quality(text)

        # Combine scores (Composite)
        base_score = (length_score * 0.5 + structure_score * 0.3 + (0.2 if not issues else 0.0))
        
        # Factor in code block syntax quality if present
        if code_blocks:
            code_quality_scores = []
            for cb in code_blocks:
                cb_score = 0.5
                syntax_markers = ['def ', 'class ', 'import ', 'from ', 'function', 'const ', 'let ', 'var ', 'if ', 'for ', 'while', '{', '}']
                marker_hits = sum(1 for m in syntax_markers if m in cb)
                cb_score += min(0.5, marker_hits * 0.1)
                code_quality_scores.append(cb_score)
            avg_code_score = sum(code_quality_scores) / len(code_quality_scores)
            base_score = (base_score * 0.7 + avg_code_score * 0.3)

        # Clamp score
        base_score = max(0.0, min(1.0, base_score))

        return base_score, issues

    def _calculate_repetition(self, text: str) -> float:
        """Calculate actual repetition ratio using proper statistical methods.

        This measures TRUE repetition - repeated consecutive tokens, not unique word ratio.
        A diverse vocabulary is NOT repetition - it's good!
        """
        words = text.lower().split()
        if len(words) < 10:
            return 0.0

        # Detect actual repeated consecutive tokens (true repetition)
        consecutive_repeats = 0
        total_pairs = len(words) - 1

        for i in range(total_pairs):
            if words[i] == words[i + 1]:
                consecutive_repeats += 1

        if total_pairs == 0:
            return 0.0

        # True repetition = consecutive identical tokens
        repeat_ratio = consecutive_repeats / total_pairs

        # Also check for n-gram repetition (repeated phrases)
        trigrams = [' '.join(words[i:i+3]) for i in range(len(words) - 2)]
        if trigrams:
            trigram_counts = {}
            for tg in trigrams:
                trigram_counts[tg] = trigram_counts.get(tg, 0) + 1
            repeated_trigrams = sum(1 for c in trigram_counts.values() if c > 1)
            trigram_repeat_ratio = repeated_trigrams / max(len(set(trigrams)), 1)
            # Weight consecutive repeats more heavily
            repeat_ratio = repeat_ratio * 0.7 + trigram_repeat_ratio * 0.3

        return min(1.0, repeat_ratio)

    def _detect_garbled_text(self, text: str) -> bool:
        """Detect garbled or corrupted text."""
        # High repetition
        if re.search(r'(.)\1{5,}', text):
            return True

        # Very long words (excluding URLs, markdown links, and HTML tags)
        cleaned_text = re.sub(r'\[.*?\]\(.*?\)', ' ', text)
        cleaned_text = re.sub(r'http[s]?://\S+', ' ', cleaned_text)
        cleaned_text = re.sub(r'<[^>]+>', ' ', cleaned_text)
        if any(len(w) > 50 for w in cleaned_text.split()):
            return True

        # Control characters
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\t')
        if len(text) > 0 and control_chars / len(text) > 0.1:
            return True

        # Low entropy (mostly same character)
        if text:
            char_freq = {}
            for c in text[:1000]:
                char_freq[c] = char_freq.get(c, 0) + 1
            max_freq = max(char_freq.values()) / max(len(text[:1000]), 1)
            if max_freq > 0.9:
                return True

        return False

    def _assess_structure_quality(self, text: str) -> float:
        """Assess structural quality of text."""
        score = 0.5

        # Has paragraphs
        if '\n\n' in text:
            score += 0.1

        # Has proper sentence endings
        sentence_count = len(re.findall(r'[.!?]+\s', text))
        if sentence_count > 3:
            score += 0.1

        # Has proper capitalization
        capitalized = sum(1 for w in text.split() if w and w[0].isupper())
        if capitalized / max(len(text.split()), 1) > 0.5:
            score += 0.1

        # Not just lists
        lines = text.split('\n')
        if lines and not all(l.startswith(('-', '*', '•', '1.')) for l in lines if l.strip()):
            score += 0.1

        return min(1.0, score)

    def _score_relevance(self, text: str, domain: str) -> float:
        """Score relevance to target domain."""
        if not domain:
            return 0.5

        STOP_WORDS = {"to", "a", "the", "in", "for", "of", "and", "with", "from", "on", "at", "by", "is", "an", "dataset", "corpus"}
        domain_terms = [t for t in domain.lower().split() if t not in STOP_WORDS]
        if not domain_terms:
            domain_terms = domain.lower().split()

        text_lower = text.lower()

        # Direct term matching
        direct_matches = sum(1 for term in domain_terms if term in text_lower)

        # Proxy matching for code translation benchmarks and datasets
        if "python" in domain_terms or "javascript" in domain_terms or "c" in domain_terms:
            if "humaneval-x" in text_lower or "multipl-e" in text_lower or "transcoder" in text_lower or "lost in translation" in text_lower:
                direct_matches = min(len(domain_terms), direct_matches + 1)

        # Related terms (if router available)
        if self.router:
            related_score = self._score_semantic_relevance(text_lower, domain_terms)
        else:
            related_score = direct_matches / max(len(domain_terms), 1)

        # Combine scores
        relevance = min(1.0, (direct_matches + related_score) / max(len(domain_terms), 2))

        # ── Heuristic Penalties for Code Translation Domain ──
        PROGRAMMING_LANGS = {
            "python", "javascript", "typescript", "c++", "cpp", "java", "rust", "go",
            "ruby", "swift", "kotlin", "scala", "haskell", "php", "perl", "bash", "sql"
        }
        NON_ENGLISH_NATURAL_LANGS = {
            "chinese", "french", "spanish", "german", "japanese", "korean",
            "russian", "arabic", "portuguese", "hindi", "bengali", "punjabi", "marathi",
            "telugu", "tamil", "urdu", "gujarati", "kannada", "odia", "malayalam", "sanskrit",
            "swahili", "zulu", "isizulu", "luganda", "xhosa", "shona", "yoruba", "hausa",
            "igbo", "amharic", "oromo", "somali", "tigrinya", "nupe", "uzbek", "akkadian",
            "latin", "italian", "dutch", "greek", "turkish", "vietnamese", "thai", "polish"
        }
        TRANSLATION_INDICATORS = {
            "translation", "translated", "parallel", "pairs", "equivalent", "transcoder",
            "humaneval-x", "multipl-e", "lost in translation", "side-by-side", "idioms", "both"
        }

        # Check if domain specifies any programming language
        domain_has_programming = any(lang in domain_terms for lang in PROGRAMMING_LANGS) or "c" in domain_terms or "code" in domain_terms or "programming" in domain_terms

        if domain_has_programming:
            # Penalty 1: If text contains non-English natural languages, it is not code translation!
            if any(lang in text_lower for lang in NON_ENGLISH_NATURAL_LANGS):
                relevance -= 0.4

            # Penalty 2: If domain seeks translation, but text lacks translation indicators
            if direct_matches >= 2:
                domain_seeks_translation = any(term in domain_terms for term in ["translation", "translate", "parallel", "pairs", "corpus"])
                if domain_seeks_translation:
                    has_translation_indicator = any(term in text_lower for term in TRANSLATION_INDICATORS)
                    if not has_translation_indicator:
                        relevance -= 0.4

        return max(0.0, relevance)

    def _score_semantic_relevance(self, text: str, terms: list[str]) -> float:
        """Score semantic relevance using embedding-based and heuristic measures."""
        try:
            # Content-quality heuristic: use term density and distribution
            text_lower = text.lower()
            term_density = sum(term in text_lower for term in terms) / max(len(terms), 1)

            # Context proximity: check if multiple domain terms appear near each other
            positions = []
            for term in terms:
                idx = text_lower.find(term)
                if idx >= 0:
                    positions.append(idx)
            proximity_score = 0.0
            if len(positions) > 1:
                distances = [abs(positions[i] - positions[i+1]) for i in range(len(positions) - 1)]
                avg_distance = sum(distances) / len(distances)
                # Closer terms = more relevant (score normalized between 0 and 1)
                proximity_score = max(0.0, 1.0 - min(avg_distance / 1000, 1.0)) * 0.3

            # Length-normalized term frequency
            word_count = len(text.split())
            term_frequency = sum(1 for term in terms if term in text_lower) / max(word_count, 1)
            frequency_score = min(1.0, term_frequency * 50) * 0.2  # Scale: 2% term density = max score

            # Combine scores
            score = term_density * 0.4 + proximity_score + frequency_score
            return min(1.0, score + 0.2)  # Base 0.2 for minimum relevance

        except Exception:
            pass
        # Fallback: use term density
        term_density = sum(1 for t in terms if t in text) / max(len(terms), 1)
        return min(1.0, term_density * 0.7 + 0.15)

    def _check_toxicity_adaptive(
        self,
        text: str,
    ) -> float:
        """Check toxicity with adaptive threshold (expanded patterns)."""
        matches = 0
        for pattern in self._toxic_patterns:
            matches += len(re.findall(pattern, text, re.IGNORECASE))

        if matches == 0:
            return 0.0

        return min(1.0, matches * 0.15)

    def _assess_hallucination_risk(self, text: str) -> float:
        """Assess hallucination risk in content."""
        risk = 0.0

        # Check for fact-like statements without sources
        facts = re.findall(r'\b(should|must|always|never|proven|fact)\b', text, re.IGNORECASE)
        risk += min(0.3, len(facts) * 0.1)

        # Check for specific numbers without context
        numbers = re.findall(r'\d+%(?!\s)', text)
        if len(numbers) > 5:
            risk += 0.2

        # Check for definitive claims
        definitive = re.findall(r'\b(definitely|certainly|absolutely|guaranteed)\b', text, re.IGNORECASE)
        risk += min(0.2, len(definitive) * 0.1)

        # Low coherence indicator
        if self._detect_garbled_text(text):
            risk += 0.3

        return min(1.0, risk)

    async def _check_uniqueness_adaptive(
        self,
        text: str,
        thresholds: FilterThresholds
    ) -> tuple[bool, str, float]:
        """Check uniqueness with adaptive threshold."""
        # Exact hash
        content_hash = self._compute_content_hash(text)
        if content_hash in self._seen_hashes:
            return True, "exact_match", 0.0

        # N-gram similarity
        ngrams = self._get_ngrams(text, 5)
        ngram_hash = hashlib.md5(str(sorted(ngrams)).encode()).hexdigest()

        if ngram_hash in self._minhash_cache:
            return True, "ngram_match", 0.3
        ngram_diversity = len(ngrams) / max(sum(len(ng) for ng in ngrams), 1)

        # Add to caches with timestamp
        now = asyncio.get_event_loop().time()
        self._seen_hashes[content_hash] = now
        self._minhash_cache[ngram_hash] = (ngrams, now)

        # Clean old entries with TTL-based eviction
        if len(self._seen_hashes) > 100000:
            # Remove oldest 50%
            items = sorted(self._seen_hashes.items(), key=lambda x: x[1])
            self._seen_hashes = dict(items[len(items)//2:])

        # Purge expired minhash entries
        if len(self._minhash_cache) > self._minhash_cache_maxsize:
            cutoff = now - self._minhash_cache_ttl
            expired = [k for k, (_, ts) in self._minhash_cache.items() if ts < cutoff]
            for k in expired:
                del self._minhash_cache[k]

        return False, "", ngram_diversity

    def _compute_content_hash(self, text: str) -> str:
        """Compute content hash."""
        normalized = re.sub(r'\s+', ' ', text.lower().strip())
        return hashlib.sha256(normalized.encode()).hexdigest()[:32]

    def _get_ngrams(self, text: str, n: int = 5) -> set[str]:
        """Get character n-grams."""
        words = text.lower().split()
        ngrams = set()

        for i in range(len(words) - n + 1):
            ngram = ' '.join(words[i:i+n])
            ngram_hash = hashlib.md5(ngram.encode()).hexdigest()[:8]
            ngrams.add(ngram_hash)

        return ngrams

    async def _score_diversity(self, text: str) -> float:
        """Score semantic diversity."""
        words = text.lower().split()
        if len(words) < 10:
            return 0.3

        unique_ratio = len(set(words)) / len(words)

        # Also check sentence diversity
        sentences = re.split(r'[.!?]+', text)
        sentence_lengths = [len(s.split()) for s in sentences if s.strip()]
        if sentence_lengths:
            variance = sum((l - sum(sentence_lengths)/len(sentence_lengths))**2 for l in sentence_lengths) / len(sentence_lengths)
            length_diversity = min(1.0, variance / 100)
        else:
            length_diversity = 0.5

        return (unique_ratio * 0.6 + length_diversity * 0.4)

    def _calculate_confidence(self, sample: FilteredSample) -> float:
        """Calculate confidence in the filtering decision."""
        confidence = 0.9

        # Lower confidence for edge cases
        if len(sample.content) < 200:
            confidence -= 0.1

        if sample.hallucination_risk > 0.5:
            confidence -= 0.2

        if sample.uniqueness_score < 0.5:
            confidence -= 0.1

        return max(0.1, confidence)

    def _generate_warnings(self, sample: FilteredSample, thresholds: FilterThresholds) -> list[str]:
        """Generate warnings for borderline cases."""
        warnings = []

        if 0.3 < sample.quality_score < thresholds.quality:
            warnings.append("quality_borderline")

        if sample.hallucination_risk > 0.5:
            warnings.append("potential_hallucination")

        if sample.uniqueness_score < 0.6:
            warnings.append("low_uniqueness")

        if len(sample.content) > 10000:
            warnings.append("very_long_content")

        return warnings

    def _should_filter(self, sample: FilteredSample, thresholds: FilterThresholds) -> bool:
        """Final pass/fail determination (called after per-dimension checks)."""
        # Hard filters
        if sample.toxicity_score > thresholds.toxicity:
            sample.filter_reason = "toxicity_exceeds_threshold"
            return True

        if "garbled_text" in sample.issues:
            sample.filter_reason = "garbled_content"
            return True

        # Relevance threshold check
        if sample.relevance_score < self.relevance_threshold:
            sample.filter_reason = "relevance_below_threshold"
            return True

        # Per-dimension threshold check (new deterministic approach)
        if sample.signal_score < thresholds.signal:
            sample.filter_reason = "signal_quality_too_low"
            return True
        if sample.statistical_score < thresholds.statistical:
            sample.filter_reason = "statistical_quality_too_low"
            return True
        if sample.semantic_score < thresholds.semantic:
            sample.filter_reason = "semantic_quality_too_low"
            return True
        if sample.llm_judge_score < thresholds.reasoning:
            sample.filter_reason = "llm_judge_quality_too_low"
            return True
        if sample.compliance_score < thresholds.grounding:
            sample.filter_reason = "compliance_failed"
            return True

        # Legacy fallback (for safety, should rarely trigger with per-dim checks above)
        if sample.quality_score < thresholds.quality:
            sample.filter_reason = "quality_below_threshold"
            return True

        return False

    def _get_applied_filters(self, sample: FilteredSample, thresholds: FilterThresholds) -> list[str]:
        """Get list of filters that were applied (new per-dimension approach)."""
        filters = []

        if sample.signal_score >= thresholds.signal:
            filters.append("signal_pass")

        if sample.statistical_score >= thresholds.statistical:
            filters.append("statistical_pass")

        if sample.semantic_score >= thresholds.semantic:
            filters.append("semantic_pass")

        if sample.llm_judge_score >= thresholds.reasoning:
            filters.append("llm_judge_pass")

        if sample.compliance_score >= thresholds.grounding:
            filters.append("compliance_pass")

        return filters

    def _record_quality(self, score: float):
        """DEPRECATED: No-op. Threshold learning has been removed."""
        return

    def get_stats(self) -> dict:
        """Get filtering statistics."""
        return {
            "total_cached_hashes": len(self._seen_hashes),
            "total_ngram_hashes": len(self._minhash_cache),
            "embeddings_cached": len(self._embedding_cache),
            "accumulated_samples": len(self._accumulated_samples),
            "current_thresholds": {
                "quality": self.adaptive_engine.thresholds.quality,
                "toxicity": self.adaptive_engine.thresholds.toxicity,
                "min_length": self.min_length,
                "max_length": self.max_length,
            },
        }

    async def get_diversity_report(self) -> dict | None:
        """Run batch diversity analysis on accumulated samples."""
        if len(self._accumulated_samples) < 5:
            return None
        try:
            metrics = await self.diversity_analyzer.analyze(
                [{"content": t} for t in self._accumulated_samples]
            )
            report = self.diversity_analyzer.get_report(metrics)
            self._accumulated_samples = []
            return report
        except Exception:
            return None

    def reset_caches(self):
        """Reset all caches."""
        self._seen_hashes.clear()
        self._minhash_cache.clear()
        self._embedding_cache.clear()
        self._accumulated_samples.clear()