"""Multi-Turn Conversational Dialogue Synthesizer.

Synthesizes high-fidelity multi-turn conversational trajectories:
1. Alternating user-assistant interactions with dynamic context carry-over.
2. In-dialogue clarifications, edge-case inquiries, and resolutions.
3. Standard serialization into ShareGPT and OpenAI formats for chat fine-tuning.
4. Dialogue coherence, alternation, and turn-ratio validation.
"""

from typing import Any, Dict, List, Optional


def build_multi_turn_directive(num_turns: int = 4, language: str = "en") -> str:
    """Return system prompt directive for generating realistic multi-turn conversational datasets."""
    return (
        f"MULTI-TURN CONVERSATIONAL DIALOGUE SPECIFICATION:\n"
        f"1. Generate a realistic dialogue with at least {num_turns} alternating turns between a user and an assistant.\n"
        f"2. The user should ask an initial domain question, followed by an assistant response.\n"
        f"3. In subsequent turns, the user must ask a contextual follow-up, edge-case question, or clarification.\n"
        f"4. The assistant must reference previous context seamlessly without contradictory statements.\n"
        f"5. Output valid JSON with keys:\n"
        f"   - 'topic': Brief topic summary\n"
        f"   - 'turns': List of objects with 'role' ('user' or 'assistant') and 'content'.\n"
    )


def format_multi_turn_sample(
    turns: List[Dict[str, str]],
    system_prompt: Optional[str] = None,
    format_type: str = "sharegpt",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Convert turns into ShareGPT or OpenAI ChatML conversational format."""
    clean_turns = []
    for t in turns:
        role = t.get("role", "").lower().strip()
        content = t.get("content", "").strip()
        if not content:
            continue
        clean_turns.append({"role": role, "content": content})

    meta = metadata.copy() if metadata else {}
    meta["turn_count"] = len(clean_turns)

    if format_type.lower() == "sharegpt":
        conversations = []
        if system_prompt:
            conversations.append({"from": "system", "value": system_prompt.strip()})
        for t in clean_turns:
            sender = "human" if t["role"] in ("user", "human") else "gpt"
            conversations.append({"from": sender, "value": t["content"]})

        first_user = next((t["content"] for t in clean_turns if t["role"] in ("user", "human")), "")
        last_assistant = next((t["content"] for t in reversed(clean_turns) if t["role"] in ("assistant", "gpt")), "")

        return {
            "instruction": first_user,
            "response": last_assistant,
            "conversations": conversations,
            "metadata": meta,
        }

    else:  # default to openai format
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt.strip()})
        for t in clean_turns:
            role = "user" if t["role"] in ("user", "human") else "assistant"
            messages.append({"role": role, "content": t["content"]})

        first_user = next((t["content"] for t in clean_turns if t["role"] in ("user", "human")), "")
        last_assistant = next((t["content"] for t in reversed(clean_turns) if t["role"] in ("assistant", "gpt")), "")

        return {
            "instruction": first_user,
            "response": last_assistant,
            "messages": messages,
            "metadata": meta,
        }


def evaluate_dialogue_coherence(turns: List[Dict[str, str]]) -> Dict[str, Any]:
    """Evaluate structural integrity, alternation, and turn balance of a dialogue."""
    if not turns or len(turns) < 2:
        return {
            "is_coherent": False,
            "coherence_score": 0.0,
            "issues": ["Dialogue must contain at least 2 alternating turns."],
            "total_turns": len(turns) if turns else 0,
        }

    issues = []
    expected_next = None

    user_turns = 0
    asst_turns = 0
    total_words = 0

    for i, t in enumerate(turns):
        role = t.get("role", "").lower().strip()
        content = t.get("content", "").strip()
        words = len(content.split())
        total_words += words

        if role in ("user", "human"):
            user_turns += 1
            current = "user"
        elif role in ("assistant", "gpt"):
            asst_turns += 1
            current = "assistant"
        else:
            current = "unknown"
            issues.append(f"Turn {i+1} has unrecognized role: '{role}'")

        if expected_next and current != expected_next:
            issues.append(f"Turn {i+1} broke alternation (expected {expected_next}, got {current})")

        expected_next = "assistant" if current == "user" else "user"

        if words < 3:
            issues.append(f"Turn {i+1} is too brief ({words} words)")

    has_alternation = len([iss for iss in issues if "alternation" in iss]) == 0
    turn_balance = min(user_turns, asst_turns) / max(user_turns, asst_turns, 1)

    coherence_score = round(
        (0.60 if has_alternation else 0.20) +
        (0.20 * turn_balance) +
        (0.20 if len(turns) >= 4 else 0.10),
        2
    )

    return {
        "is_coherent": len(issues) == 0 and coherence_score >= 0.70,
        "coherence_score": coherence_score,
        "user_turns": user_turns,
        "assistant_turns": asst_turns,
        "total_turns": len(turns),
        "issues": issues,
    }
