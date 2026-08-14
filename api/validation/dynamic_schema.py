"""
Dynamic Schema Generation

Dynamic schema generation, plugin system for custom schemas,
and runtime schema composition.
"""

from typing import Dict, List, Optional, Any, Callable, Type, Set, Union
from datetime import datetime
from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, create_model, field_validator
from pydantic.fields import FieldInfo
import json
import hashlib


class SchemaPlugin(ABC):
    """Base class for schema plugins."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name."""
        pass

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin version."""
        pass

    @property
    @abstractmethod
    def schema_types(self) -> List[str]:
        """Types of schemas this plugin handles."""
        pass

    @abstractmethod
    def generate_schema(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate a Pydantic model from specification."""
        pass

    @abstractmethod
    def validate_data(
        self,
        data: Any,
        schema: Type[BaseModel]
    ) -> tuple[bool, Optional[str]]:
        """Validate data against generated schema."""
        pass

    def pre_process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Pre-process data before schema generation."""
        return data

    def post_process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Post-process validated data."""
        return data


class SchemaRegistry:
    """Registry for schema plugins and generated schemas."""

    def __init__(self):
        self._plugins: Dict[str, SchemaPlugin] = {}
        self._schemas: Dict[str, Type[BaseModel]] = {}
        self._schema_cache: Dict[str, Dict[str, Any]] = {}
        self._composite_schemas: Dict[str, Dict[str, Type[BaseModel]]] = {}

    def register_plugin(self, plugin: SchemaPlugin) -> None:
        """Register a schema plugin."""
        self._plugins[plugin.name] = plugin

    def unregister_plugin(self, name: str) -> bool:
        """Unregister a schema plugin."""
        if name in self._plugins:
            del self._plugins[name]
            return True
        return False

    def get_plugin(self, name: str) -> Optional[SchemaPlugin]:
        """Get a registered plugin."""
        return self._plugins.get(name)

    def register_schema(
        self,
        name: str,
        schema: Type[BaseModel],
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Register a generated schema."""
        self._schemas[name] = schema
        if metadata:
            self._schema_cache[name] = metadata

    def get_schema(self, name: str) -> Optional[Type[BaseModel]]:
        """Get a registered schema."""
        return self._schemas.get(name)

    def list_schemas(self) -> List[str]:
        """List all registered schema names."""
        return list(self._schemas.keys())

    def register_composite_schema(
        self,
        name: str,
        schemas: Dict[str, Type[BaseModel]]
    ) -> None:
        """Register a composite schema."""
        self._composite_schemas[name] = schemas

    def get_composite_schema(self, name: str) -> Optional[Dict[str, Type[BaseModel]]]:
        """Get a composite schema."""
        return self._composite_schemas.get(name)


class DynamicSchemaGenerator:
    """Dynamic schema generator with plugin support."""

    def __init__(self, registry: Optional[SchemaRegistry] = None):
        self.registry = registry or SchemaRegistry()
        self._type_mapping: Dict[str, Type] = {
            "string": str,
            "str": str,
            "integer": int,
            "int": int,
            "number": float,
            "float": float,
            "boolean": bool,
            "bool": bool,
            "array": List,
            "list": List,
            "dict": Dict,
            "object": Dict,
            "datetime": datetime,
            "date": datetime,
        }

    def generate_from_spec(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate a Pydantic model from specification."""
        name = spec.get("name", "DynamicSchema")
        properties = spec.get("properties", {})
        required = spec.get("required", [])
        metadata = spec.get("metadata", {})

        field_definitions = {}

        for field_name, field_spec in properties.items():
            field_type = self._resolve_type(field_spec)
            field_definitions[field_name] = self._create_field(field_name, field_spec, field_type, field_name in required)

        model = create_model(
            name,
            **field_definitions,
            __config__=type("Config", (), {
                "extra": "allow" if spec.get("additionalProperties", True) else "forbid"
            })
        )

        self.registry.register_schema(name, model, metadata)
        return model

    def _resolve_type(self, field_spec: Union[str, Dict, Type]) -> Type:
        """Resolve field type from specification."""
        if isinstance(field_spec, type):
            return field_spec

        if isinstance(field_spec, str):
            return self._type_mapping.get(field_spec, Any)

        if isinstance(field_spec, dict):
            type_name = field_spec.get("type", "any")
            if type_name == "array" or type_name == "list":
                items = field_spec.get("items", {})
                if isinstance(items, dict):
                    item_type = items.get("type", "any")
                    return List[self._type_mapping.get(item_type, Any)]
                elif isinstance(items, list):
                    return List[Any]
                return List[Any]

            if type_name == "object" or type_name == "dict":
                return Dict[str, Any]

            return self._type_mapping.get(type_name, Any)

        return Any

    def _create_field(
        self,
        field_name: str,
        field_spec: Union[str, Dict],
        field_type: Type,
        required: bool
    ) -> Any:
        """Create a Pydantic field."""
        if isinstance(field_spec, str):
            return (field_type, Field(default=None if not required else ...))

        default = field_spec.get("default")
        if not required and default is None:
            default = None

        description = field_spec.get("description", "")
        gt = field_spec.get("gt")
        lt = field_spec.get("lt")
        ge = field_spec.get("ge")
        le = field_spec.get("le")
        min_length = field_spec.get("minLength")
        max_length = field_spec.get("maxLength")
        pattern = field_spec.get("pattern")

        field_args = {"default": default} if default is not ... else {}

        if description:
            field_args["description"] = description
        if gt is not None:
            field_args["gt"] = gt
        if lt is not None:
            field_args["lt"] = lt
        if ge is not None:
            field_args["ge"] = ge
        if le is not None:
            field_args["le"] = le
        if min_length is not None:
            field_args["min_length"] = min_length
        if max_length is not None:
            field_args["max_length"] = max_length
        if pattern:
            field_args["pattern"] = pattern

        return (field_type, Field(**field_args))

    def generate_dataset_schema(
        self,
        fields: List[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate a dataset schema from field definitions."""
        spec = {
            "name": "DynamicDataset",
            "properties": {},
            "required": [],
            "metadata": metadata or {}
        }

        for field in fields:
            field_name = field.get("name")
            field_type = field.get("type", "string")
            required = field.get("required", False)

            spec["properties"][field_name] = {
                "type": field_type,
                "description": field.get("description", ""),
            }

            if required:
                spec["required"].append(field_name)

            if "default" in field:
                spec["properties"][field_name]["default"] = field["default"]

            if "constraints" in field:
                spec["properties"][field_name].update(field["constraints"])

        return self.generate_from_spec(spec)

    def generate_nested_schema(
        self,
        parent_name: str,
        child_name: str,
        child_fields: List[Dict[str, Any]]
    ) -> Type[BaseModel]:
        """Generate nested schema with parent-child relationship."""
        child_model = self.generate_dataset_schema(
            child_fields,
            {"parent": parent_name, "relationship": "nested"}
        )

        parent_spec = {
            "name": parent_name,
            "properties": {
                child_name: {
                    "type": "list",
                    "items": {"type": "object"},
                    "description": f"Nested {child_name} collection"
                }
            },
            "required": []
        }

        parent_model = self.generate_from_spec(parent_spec)
        return parent_model

    def compose_schemas(
        self,
        base_schema: Type[BaseModel],
        extensions: List[Dict[str, Any]]
    ) -> Type[BaseModel]:
        """Compose multiple schemas into one."""
        base_name = base_schema.__name__
        new_name = f"{base_name}Extended"

        field_definitions = {}

        for field_name, field_info in base_schema.model_fields.items():
            field_definitions[field_name] = (
                field_info.annotation,
                Field(
                    default=field_info.default,
                    description=field_info.description
                )
            )

        for extension in extensions:
            for field_name, field_spec in extension.items():
                field_type = self._resolve_type(field_spec)
                field_definitions[field_name] = self._create_field(
                    field_name, field_spec, field_type,
                    field_spec.get("required", False) if isinstance(field_spec, dict) else False
                )

        return create_model(new_name, **field_definitions)

    def generate_reasoning_trace_schema(self) -> Type[BaseModel]:
        """Generate schema for reasoning traces."""
        spec = {
            "name": "ReasoningTrace",
            "properties": {
                "trace_id": {"type": "string", "description": "Unique trace identifier"},
                "steps": {
                    "type": "list",
                    "items": {
                        "type": "object",
                        "properties": {
                            "step_number": {"type": "integer"},
                            "thought": {"type": "string"},
                            "action": {"type": "string"},
                            "observation": {"type": "string"},
                            "confidence": {"type": "number", "ge": 0, "le": 1}
                        },
                        "required": ["step_number", "thought"]
                    }
                },
                "final_answer": {"type": "string"},
                "confidence_score": {"type": "number", "ge": 0, "le": 1},
                "metadata": {"type": "object"}
            },
            "required": ["trace_id", "steps", "final_answer"]
        }
        return self.generate_from_spec(spec)

    def generate_tool_call_schema(self) -> Type[BaseModel]:
        """Generate schema for tool call trajectories."""
        spec = {
            "name": "ToolCall",
            "properties": {
                "call_id": {"type": "string"},
                "tool_name": {"type": "string"},
                "arguments": {"type": "object"},
                "result": {"type": "string"},
                "execution_time_ms": {"type": "number", "ge": 0},
                "success": {"type": "boolean"}
            },
            "required": ["call_id", "tool_name", "arguments"]
        }
        return self.generate_from_spec(spec)

    def generate_scientific_schema(self) -> Type[BaseModel]:
        """Generate schema for scientific symbolic data."""
        spec = {
            "name": "ScientificData",
            "properties": {
                "formula": {"type": "string", "description": "Scientific formula or equation"},
                "variables": {
                    "type": "list",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "value": {"type": "number"},
                            "unit": {"type": "string"}
                        },
                        "required": ["name", "value"]
                    }
                },
                "derivation": {"type": "string"},
                "references": {
                    "type": "list",
                    "items": {"type": "string"}
                },
                "confidence": {"type": "number", "ge": 0, "le": 1}
            },
            "required": ["formula"]
        }
        return self.generate_from_spec(spec)


class MultimodalSchemaPlugin(SchemaPlugin):
    """Plugin for multimodal data schemas."""

    @property
    def name(self) -> str:
        return "multimodal"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def schema_types(self) -> List[str]:
        return ["image", "video", "audio", "document", "multimodal"]

    def generate_schema(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate multimodal data schema."""
        modality = spec.get("modality", "text")
        schema_name = f"{modality.title()}Schema"

        properties = {
            "data_id": {"type": "string"},
            "modality": {"type": "string"},
            "uri": {"type": "string"},
            "format": {"type": "string"},
            "metadata": {"type": "object"},
        }

        if modality in ["image", "video"]:
            properties.update({
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "duration_frames": {"type": "integer"},
                "embeddings": {"type": "array", "items": {"type": "number"}},
            })

        if modality == "document":
            properties.update({
                "page_count": {"type": "integer"},
                "text_content": {"type": "string"},
                "tables": {"type": "list", "items": {"type": "object"}},
            })

        spec["properties"] = properties
        return create_model(schema_name, **{
            k: (self._type_mapping.get(v.get("type", "any"), Any), Field(**v))
            for k, v in properties.items()
        })

    def validate_data(
        self,
        data: Any,
        schema: Type[BaseModel]
    ) -> tuple[bool, Optional[str]]:
        """Validate multimodal data."""
        try:
            if isinstance(data, dict):
                schema(**data)
            return True, None
        except Exception as e:
            return False, str(e)


class MultimodalSchemaPlugin(SchemaPlugin):
    """Plugin for multimodal data schemas."""

    @property
    def name(self) -> str:
        return "multimodal"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def schema_types(self) -> List[str]:
        return ["image", "video", "audio", "document", "multimodal"]

    def _get_type_mapping(self) -> Dict[str, Type]:
        """Get type mapping for this plugin."""
        return {"string": str, "integer": int, "number": float, "boolean": bool, "object": Dict, "array": List}

    def generate_schema(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate multimodal data schema."""
        modality = spec.get("modality", "text")
        schema_name = f"{modality.title()}Schema"

        properties = {
            "data_id": {"type": "string"},
            "modality": {"type": "string"},
            "uri": {"type": "string"},
            "format": {"type": "string"},
            "metadata": {"type": "object"},
        }

        if modality in ["image", "video"]:
            properties.update({
                "width": {"type": "integer"},
                "height": {"type": "integer"},
                "duration_frames": {"type": "integer"},
                "embeddings": {"type": "array", "items": {"type": "number"}},
            })

        if modality == "document":
            properties.update({
                "page_count": {"type": "integer"},
                "text_content": {"type": "string"},
                "tables": {"type": "list", "items": {"type": "object"}},
            })

        spec["properties"] = properties
        return create_model(schema_name, **{
            k: (self._get_type_mapping().get(v.get("type", "any"), Any), Field(**v))
            for k, v in properties.items()
        })

    def validate_data(
        self,
        data: Any,
        schema: Type[BaseModel]
    ) -> tuple[bool, Optional[str]]:
        """Validate multimodal data."""
        try:
            schema(**data)
            return True, None
        except Exception as e:
            return False, str(e)


class GraphSchemaPlugin(SchemaPlugin):
    """Plugin for graph data schemas."""

    @property
    def name(self) -> str:
        return "graph"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def schema_types(self) -> List[str]:
        return ["graph", "knowledge_graph", "social_network"]

    def generate_schema(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate graph data schema."""
        schema_name = spec.get("name", "GraphSchema")

        properties = {
            "graph_id": {"type": "string"},
            "nodes": {
                "type": "list",
                "items": {
                    "type": "object",
                    "properties": {
                        "node_id": {"type": "string"},
                        "label": {"type": "string"},
                        "properties": {"type": "object"},
                        "node_type": {"type": "string"}
                    },
                    "required": ["node_id", "label"]
                }
            },
            "edges": {
                "type": "list",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "target": {"type": "string"},
                        "relationship": {"type": "string"},
                        "weight": {"type": "number"},
                        "properties": {"type": "object"}
                    },
                    "required": ["source", "target", "relationship"]
                }
            },
            "directed": {"type": "boolean", "default": True}
        }

        return create_model(schema_name, **{
            k: (List[v["items"]["type"]] if v.get("type") == "list" else self._type_mapping.get(v.get("type", "any"), Any), Field(**v))
            for k, v in properties.items()
        })

    def validate_data(
        self,
        data: Any,
        schema: Type[BaseModel]
    ) -> tuple[bool, Optional[str]]:
        """Validate graph data."""
        try:
            schema(**data)
            return True, None
        except Exception as e:
            return False, str(e)


class CustomSchemaPlugin(SchemaPlugin):
    """Plugin for custom user-defined schemas."""

    @property
    def name(self) -> str:
        return "custom"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def schema_types(self) -> List[str]:
        return ["custom", "user_defined"]

    def generate_schema(
        self,
        spec: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Type[BaseModel]:
        """Generate custom schema from user specification."""
        name = spec.get("name", "CustomSchema")
        return create_model(name, **{
            field_name: (Any, Field(**field_spec))
            for field_name, field_spec in spec.get("fields", {}).items()
        })

    def validate_data(
        self,
        data: Any,
        schema: Type[BaseModel]
    ) -> tuple[bool, Optional[str]]:
        """Validate custom data."""
        try:
            schema(**data)
            return True, None
        except Exception as e:
            return False, str(e)


def infer_schema_from_data(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Infer schema from sample data."""
    if not data:
        return {"name": "EmptySchema", "properties": {}}

    sample = data[0]
    properties = {}

    for key, value in sample.items():
        inferred_type = "string"
        if isinstance(value, bool):
            inferred_type = "boolean"
        elif isinstance(value, int):
            inferred_type = "integer"
        elif isinstance(value, float):
            inferred_type = "number"
        elif isinstance(value, list):
            inferred_type = "array"
        elif isinstance(value, dict):
            inferred_type = "object"

        properties[key] = {"type": inferred_type}

    return {
        "name": "InferredSchema",
        "properties": properties,
        "required": list(sample.keys())
    }