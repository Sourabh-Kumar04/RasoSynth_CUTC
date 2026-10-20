"""Vernacular Tool Calling & API Function Calling Generator.

Synthesizes datasets where user instructions are in vernacular/Hinglish/Indic/English
and target outputs are structured JSON tool invocations matching API schemas.
"""

import json
import re
from typing import Any, Dict, List, Optional


DEFAULT_FINANCE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "check_itc_balance",
            "description": "Retrieve current Input Tax Credit (ITC) balance under CGST, SGST, and IGST ledgers.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gstin": {"type": "string", "description": "15-digit GSTIN of the taxpayer"},
                    "financial_year": {"type": "string", "description": "Financial year e.g. '2025-26'"},
                },
                "required": ["gstin"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "generate_gst_challan",
            "description": "Generate PMT-06 challan for GST tax payment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gstin": {"type": "string", "description": "Taxpayer GSTIN"},
                    "cgst_amount": {"type": "number", "description": "Central GST liability amount in INR"},
                    "sgst_amount": {"type": "number", "description": "State GST liability amount in INR"},
                    "igst_amount": {"type": "number", "description": "Integrated GST liability amount in INR"},
                    "payment_mode": {"type": "string", "enum": ["net_banking", "upi", "neft_rtgs", "over_the_counter"]},
                },
                "required": ["gstin", "payment_mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "track_refund_status",
            "description": "Track the processing status of an Income Tax or GST refund claim (ARN).",
            "parameters": {
                "type": "object",
                "properties": {
                    "arn": {"type": "string", "description": "Application Reference Number"},
                    "pan": {"type": "string", "description": "10-character PAN of the entity"},
                },
                "required": ["arn"],
            },
        },
    },
]


def build_tool_calling_system_prompt(tools: List[Dict[str, Any]]) -> str:
    """Format tools schema into an OpenAI/Hermes compatible function calling system prompt."""
    tools_str = json.dumps(tools, indent=2, ensure_ascii=False)
    return (
        "You are an AI assistant capable of executing tools and API calls.\n"
        "You have access to the following functions:\n"
        f"{tools_str}\n\n"
        "INSTRUCTIONS:\n"
        "1. When the user prompt requires an action or real-time query supported by a tool, "
        "output a JSON object with key 'tool_calls' containing a list of objects with 'name' and 'arguments'.\n"
        "2. If no tool is needed, respond with a helpful natural-language answer in 'response'.\n"
        "3. Output MUST be valid JSON with keys: 'instruction', 'response', 'tool_calls' (or empty list).\n"
    )


def format_tool_calling_sample(
    instruction: str,
    tool_calls: List[Dict[str, Any]],
    assistant_thought: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a standardized function calling record compliant with OpenAI / ShareGPT specs."""
    formatted_calls = []
    for tc in tool_calls:
        name = tc.get("name", "")
        args = tc.get("arguments", {})
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                pass
        formatted_calls.append({
            "name": name,
            "arguments": args,
        })

    response_payload = {
        "tool_calls": formatted_calls
    }
    if assistant_thought:
        response_payload["thought"] = assistant_thought

    return {
        "instruction": instruction,
        "response": json.dumps(response_payload, ensure_ascii=False),
        "tool_calls": formatted_calls,
    }
