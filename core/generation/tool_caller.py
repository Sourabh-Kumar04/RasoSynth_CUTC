"""Vernacular Tool Calling & API Function Calling Generator.

Synthesizes datasets where user instructions are in vernacular/Hinglish/Indic/English
and target outputs are structured JSON tool invocations matching API schemas.

VALIDATION RULE: tool calls are only schema-validated when the caller passes
the declared ``tools`` schemas to :func:`format_tool_calling_sample`. Without
schemas, the sample is labelled ``validated: False`` — it is NOT claimed to
match any API. With schemas, an unknown tool name, a missing required
argument, an unknown argument, a wrong JSON type, or an enum violation
raises ``ValueError`` instead of silently entering the dataset.
"""

import json
import re
from typing import Any, Dict, List, Optional, Tuple


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


def _tool_schema_map(tools: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Index declared tool schemas by function name."""
    schemas: Dict[str, Dict[str, Any]] = {}
    for tool in tools or []:
        fn = tool.get("function", {}) if isinstance(tool, dict) else {}
        name = fn.get("name")
        if name:
            schemas[name] = fn.get("parameters", {}) or {}
    return schemas


def _type_matches(value: Any, declared: str) -> bool:
    """Check a value against a JSON-schema primitive type name."""
    if declared == "string":
        return isinstance(value, str)
    if declared == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if declared == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if declared == "boolean":
        return isinstance(value, bool)
    if declared == "object":
        return isinstance(value, dict)
    if declared == "array":
        return isinstance(value, list)
    return True  # Unknown declared types are not second-guessed here.


def validate_tool_calls(
    tools: List[Dict[str, Any]],
    tool_calls: List[Dict[str, Any]],
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Validate tool calls against declared schemas.

    Returns (formatted_calls, errors). Errors cover: unknown tool name,
    non-object arguments, missing required arguments, unknown arguments,
    wrong JSON types, and enum violations. An empty error list means the
    calls match the declared schemas (it does not mean the calls are safe
    to execute or that the argument values are real).
    """
    schemas = _tool_schema_map(tools)
    formatted: List[Dict[str, Any]] = []
    errors: List[str] = []
    for tc in tool_calls or []:
        name = tc.get("name", "") if isinstance(tc, dict) else ""
        args = tc.get("arguments", {}) if isinstance(tc, dict) else {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                errors.append(f"tool '{name}': arguments are not valid JSON")
                continue
        if name not in schemas:
            errors.append(f"unknown tool: '{name}' (not in declared schemas)")
            formatted.append({"name": name, "arguments": args})
            continue
        if not isinstance(args, dict):
            errors.append(f"tool '{name}': arguments must be an object")
            formatted.append({"name": name, "arguments": args})
            continue
        params = schemas[name]
        properties = params.get("properties", {}) or {}
        required = params.get("required", []) or []
        for req in required:
            if req not in args:
                errors.append(f"tool '{name}': missing required argument '{req}'")
        for arg_name, value in args.items():
            spec = properties.get(arg_name)
            if spec is None:
                errors.append(f"tool '{name}': unknown argument '{arg_name}'")
                continue
            declared_type = spec.get("type")
            if declared_type and not _type_matches(value, declared_type):
                errors.append(
                    f"tool '{name}': argument '{arg_name}' has wrong type "
                    f"(expected {declared_type}, got {type(value).__name__})"
                )
            enum_values = spec.get("enum")
            if enum_values is not None and value not in enum_values:
                errors.append(
                    f"tool '{name}': argument '{arg_name}' value {value!r} "
                    f"not in allowed enum {enum_values}"
                )
        formatted.append({"name": name, "arguments": args})
    return formatted, errors


def format_tool_calling_sample(
    instruction: str,
    tool_calls: List[Dict[str, Any]],
    assistant_thought: Optional[str] = None,
    tools: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Create a standardized function calling record compliant with OpenAI / ShareGPT specs.

    Pass ``tools`` (the declared schemas, e.g. ``DEFAULT_FINANCE_TOOLS``) to
    schema-validate the calls; invalid calls raise ``ValueError``. Without
    ``tools`` the sample is returned with ``schema_validation.validated``
    False — callers must not present it as schema-checked.
    """
    if tools is not None:
        formatted_calls, errors = validate_tool_calls(tools, tool_calls)
        if errors:
            raise ValueError("Tool-call schema validation failed: " + "; ".join(errors))
        schema_validation = {"validated": True, "errors": []}
    else:
        formatted_calls = []
        for tc in tool_calls:
            name = tc.get("name", "")
            args = tc.get("arguments", {})
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    raise ValueError(f"Tool-call arguments for '{name}' are not valid JSON")
            formatted_calls.append({
                "name": name,
                "arguments": args,
            })
        schema_validation = {
            "validated": False,
            "reason": "no_tool_schemas_provided",
            "errors": [],
        }

    response_payload = {
        "tool_calls": formatted_calls
    }
    if assistant_thought:
        response_payload["thought"] = assistant_thought

    return {
        "instruction": instruction,
        "response": json.dumps(response_payload, ensure_ascii=False),
        "tool_calls": formatted_calls,
        "schema_validation": schema_validation,
    }
