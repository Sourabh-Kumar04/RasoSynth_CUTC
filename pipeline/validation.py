import logging
from pydantic import BaseModel, Field
from typing import List
from pipeline.construction import ConstructedSample
from core.provider_router import ProviderRouter, TaskType

logger = logging.getLogger(__name__)

class ValidationResult(BaseModel):
    is_valid: bool
    score: float
    reasons: List[str]
    regenerate_needed: bool = False

class MultiStageValidator:
    def __init__(self, router: ProviderRouter, config: dict):
        self.router = router
        self.config = config
        self.strictness = config.get("validation_strictness", "standard")

    async def validate(self, sample: ConstructedSample) -> ValidationResult:
        """Validate a generated sample on multiple criteria."""
        reasons = []
        is_valid = True
        dataset_type = str(self.config.get("dataset_type", "sft")).lower()

        # 1. Conversational Dataset Checks
        if "conversational" in dataset_type:
            conv = getattr(sample, "conversation", None)
            if not conv or not isinstance(conv, list):
                reasons.append("Empty or missing structured conversation list")
                return ValidationResult(is_valid=False, score=0.0, reasons=reasons, regenerate_needed=True)

            if len(conv) < 6:
                reasons.append(f"Conversation is too short ({len(conv)} turns, expected >= 6)")
                is_valid = False

            # Check alternation of roles
            for i in range(1, len(conv)):
                prev_role = str(conv[i-1].get("role", "")).lower()
                curr_role = str(conv[i].get("role", "")).lower()
                if prev_role == curr_role:
                    reasons.append(f"Consecutive turns have the same role: {curr_role} at index {i}")
                    is_valid = False
                    break

            # Clinical & Demographic consistency validation checks
            metadata = sample.metadata or {}
            specialty = str(metadata.get("specialty", "")).lower()
            disease = str(metadata.get("disease", "")).lower()
            patient_cond = str(metadata.get("patient_condition", "")).lower()
            demographics = str(metadata.get("patient_demographics", "")).lower()
            clinical_setting = str(metadata.get("clinical_setting", "")).lower()

            # Rule: Pediatric patients cannot be old or retired
            if "pediatric" in demographics or "pediatrics" in specialty:
                if any(w in demographics for w in ["75-year", "65-year", "55-year", "retired"]):
                    reasons.append("Clinical inconsistency: Pediatric specialty/demographic combined with senior age or retirement.")
                    is_valid = False

            # Rule: Pregnancy cannot be male
            if "pregnancy" in disease or "pregnant" in demographics or "gynecology" in specialty:
                if "male" in demographics and "female" not in demographics:
                    reasons.append("Clinical inconsistency: Pregnancy/Gynecology combined with male gender.")
                    is_valid = False

            # Rule: Psychiatrists do not treat acute physical emergencies like Heart Attack/Infarction
            if "psychiatry" in specialty or "psychiatrist" in specialty:
                if any(w in disease or w in patient_cond for w in ["heart attack", "myocardial infarction", "cardiac arrest"]):
                    reasons.append("Clinical inconsistency: Psychiatry specialty combined with acute cardiac emergency.")
                    is_valid = False

            if not is_valid:
                return ValidationResult(is_valid=False, score=0.3, reasons=reasons, regenerate_needed=True)

        else:
            # 2. Standard SFT / Instruction-Following Checks
            if not sample.instruction or not isinstance(sample.instruction, str):
                reasons.append("Empty or non-string instruction")
                is_valid = False
            if not sample.response or not isinstance(sample.response, str):
                reasons.append("Empty or non-string response")
                is_valid = False

            if not is_valid:
                return ValidationResult(is_valid=False, score=0.0, reasons=reasons, regenerate_needed=True)

            if len(sample.instruction.strip()) < 10:
                reasons.append("Instruction too short (under 10 chars)")
                is_valid = False
            if len(sample.response.strip()) < 15:
                reasons.append("Response too short (under 15 chars)")
                is_valid = False

            # Domain Specific Validation: Coding / Code generation checks
            target_domain = str(self.config.get("target_domain", "")).lower()
            if "coding" in dataset_type or any(w in target_domain for w in ["code", "program", "python", "javascript", "developer"]):
                # Ensure the response has a code block
                if "```" not in sample.response:
                    reasons.append("Coding sample response does not contain any code blocks")
                    is_valid = False
                
                # If it contains python code, try parsing it to verify syntax (factual correctness check)
                if "```python" in sample.response:
                    try:
                        import ast
                        # Extract all text inside ```python ... ``` blocks
                        blocks = sample.response.split("```python")
                        for block in blocks[1:]:
                            code = block.split("```")[0].strip()
                            if code:
                                ast.parse(code)
                    except SyntaxError as syntax_err:
                        reasons.append(f"Factual Code Inconsistency: Syntax error in generated Python code: {syntax_err}")
                        is_valid = False

            # Domain Specific Validation: Finance checks
            if "finance" in dataset_type or any(w in target_domain for w in ["finance", "stock", "portfolio", "market", "investment"]):
                # Ensure finance answers contain quantitative backing data (numbers, dollar sign, or percent sign)
                import re
                if not re.search(r'\d', sample.response) or not any(char in sample.response for char in ["$", "%", "USD"]):
                    reasons.append("Financial domain warning: Response lacks quantitative metrics, percentage, or currency data.")
                    if self.strictness == "strict":
                        is_valid = False

            if not is_valid:
                return ValidationResult(is_valid=False, score=0.3, reasons=reasons, regenerate_needed=True)

        # 3. Coherence and Role consistency checks using LLM (if strictness is strict)
        if self.strictness == "strict" and self.router:
            prompt = (
                "Analyze the following generated training example for quality, coherence, and role consistency.\n"
                f"Instruction/Opening: {sample.instruction}\n"
                f"Response/Dialogue: {sample.response}\n\n"
                "Is the dialogue coherent and logically consistent? Output ONLY 'YES' or 'NO' followed by a brief reason."
            )
            try:
                response = await self.router.route(TaskType.QUALITY_CHECK, prompt)
                if response and response.content:
                    verdict = response.content.strip().upper()
                    if verdict.startswith("NO"):
                        reasons.append(f"LLM validation rejected: {response.content}")
                        return ValidationResult(is_valid=False, score=0.4, reasons=reasons, regenerate_needed=True)
            except Exception as e:
                logger.warning(f"LLM validation request failed (non-fatal): {e}")

        return ValidationResult(is_valid=True, score=0.95, reasons=[])
