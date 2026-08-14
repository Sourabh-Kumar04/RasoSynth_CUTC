"""
Multimodal Schemas

Schemas for multimodal input processing, modality types,
OCR configuration, and processing pipeline selection.
"""

from typing import Dict, List, Optional, Any, Set, Union, Literal, Callable
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, field_validator, computed_field
from api.schemas.base import BaseSchema


class ModalityType(str, Enum):
    """Types of data modalities."""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    PDF = "pdf"
    DOCUMENT = "document"
    CODE = "code"
    TABLE = "table"
    GRAPH = "graph"
    MODALITY_3D = "3d"
    POINT_CLOUD = "point_cloud"
    HYPERGRAPH = "hypergraph"


class ProcessingPriority(str, Enum):
    """Processing priority for modalities."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class MultimodalInput(BaseSchema):
    """Multimodal input specification."""
    input_id: Optional[str] = None
    modality: ModalityType

    uri: Optional[str] = None
    data: Optional[Any] = None
    url: Optional[str] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)

    processing_hints: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("uri", "url")
    @classmethod
    def validate_uri(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if not v.startswith(("http://", "https://", "file://", "s3://", "gs://", "data:")):
            raise ValueError(f"Invalid URI format: {v}")
        return v


class ImageConfig(BaseModel):
    """Configuration for image processing."""
    target_size: Optional[tuple[int, int]] = None
    maintain_aspect_ratio: bool = True

    preprocessing: Literal["none", "resize", "normalize", "augment"] = "resize"
    normalization_mean: Optional[List[float]] = None
    normalization_std: Optional[List[float]] = None

    format: Literal["raw", "jpeg", "png", "webp"] = "jpeg"
    quality: int = 95

    extract_features: bool = True
    feature_extractor: Literal["clip", "dino", "siglip", "custom"] = "clip"


class VideoConfig(BaseModel):
    """Configuration for video processing."""
    frame_rate: Optional[float] = None
    max_frames: Optional[int] = None
    sample_strategy: Literal["uniform", "fps_based", "scene_detection"] = "uniform"

    temporal_aggregation: Literal["mean", "max", "attention", "lstm"] = "mean"
    sequence_length: int = 16

    extract_audio: bool = True
    audio_sample_rate: int = 16000

    detect_scenes: bool = True
    detect_actions: bool = False


class AudioConfig(BaseModel):
    """Configuration for audio processing."""
    sample_rate: int = 16000
    channels: int = 1

    duration_seconds: Optional[float] = None
    max_duration_seconds: float = 3600.0

    preprocessing: Literal["none", "mel_spectrogram", "mfcc", "waveform"] = "mel_spectrogram"

    extract_features: bool = True
    feature_dim: int = 512

    transcription_enabled: bool = False
    transcription_model: Literal["whisper", "parakeet", "custom"] = "whisper"


class OCRConfig(BaseModel):
    """Configuration for OCR processing."""
    enabled: bool = True
    engine: Literal["tesseract", "easyocr", "paddleocr", "surya", "multi"] = "multi"

    languages: List[str] = Field(default_factory=lambda: ["en"])
    language_detection: bool = True

    detection_threshold: float = 0.5
    recognition_confidence_threshold: float = 0.6

    preserve_layout: bool = True
    preserve_formatting: bool = True

    extract_tables: bool = True
    extract_structure: bool = True

    deskew: bool = True
    denoise: bool = True
    binarization: Literal["none", "otsu", "adaptive"] = "adaptive"

    batch_processing: bool = True
    batch_size: int = 32

    include_confidence: bool = True
    include_bounding_boxes: bool = True


class PDFConfig(BaseModel):
    """Configuration for PDF processing."""
    extract_text: bool = True
    extract_images: bool = True
    extract_tables: bool = True

    ocr_fallback: bool = True
    ocr_config: OCRConfig = Field(default_factory=OCRConfig)

    page_limit: Optional[int] = None
    start_page: int = 1
    end_page: Optional[int] = None

    extract_annotations: bool = True
    extract_metadata: bool = True

    vectorize_graphics: bool = False
    preserve_links: bool = True


class CodeConfig(BaseModel):
    """Configuration for code processing."""
    languages: Optional[List[str]] = None
    syntax_highlight: bool = False

    parse_ast: bool = True
    extract_functions: bool = True
    extract_classes: bool = True
    extract_imports: bool = True

    normalize_whitespace: bool = True
    remove_comments: bool = False

    deobfuscate: bool = False
    prettify: bool = True


class TableConfig(BaseModel):
    """Configuration for table processing."""
    detect_tables: bool = True
    table_detection_threshold: float = 0.7

    parse_format: Literal["csv", "markdown", "html", "excel"] = "csv"
    include_headers: bool = True

    merge_cells: bool = True
    handle_merged: Literal["skip", "first", "last"] = "first"

    min_rows: int = 1
    min_columns: int = 1


class ProcessingConfig(BaseSchema):
    """Complete multimodal processing configuration."""
    modalities: List[ModalityType] = Field(default_factory=list)

    image_config: Optional[ImageConfig] = None
    video_config: Optional[VideoConfig] = None
    audio_config: Optional[AudioConfig] = None
    ocr_config: Optional[OCRConfig] = None
    pdf_config: Optional[PDFConfig] = None
    code_config: Optional[CodeConfig] = None
    table_config: Optional[TableConfig] = None

    parallel_processing: bool = True
    max_parallel_modalities: int = 4

    enable_caching: bool = True
    cache_ttl_seconds: int = 3600

    processing_timeout_seconds: int = 600

    output_format: Literal["raw", "structured", "embedded"] = "structured"

    priority: ProcessingPriority = ProcessingPriority.NORMAL

    def get_modality_config(self, modality: ModalityType) -> Optional[BaseModel]:
        """Get configuration for specific modality."""
        config_map = {
            ModalityType.IMAGE: self.image_config,
            ModalityType.VIDEO: self.video_config,
            ModalityType.AUDIO: self.audio_config,
            ModalityType.PDF: self.pdf_config,
            ModalityType.CODE: self.code_config,
            ModalityType.TABLE: self.table_config,
        }
        return config_map.get(modality)


class MultimodalFusion(BaseSchema):
    """Configuration for multimodal fusion."""
    fusion_strategy: Literal["early", "late", "cross_attention", "hierarchical"] = "late"

    embedding_dims: Dict[str, int] = Field(default_factory=dict)

    alignment_method: Literal["attention", "projection", "none"] = "attention"

    concat_embeddings: bool = True
    weighted_fusion: bool = True
    fusion_weights: Dict[str, float] = Field(default_factory=dict)

    cross_modal_attention_heads: int = 8
    cross_modal_layers: int = 4


class ModalityRequirements(BaseSchema):
    """Requirements for modality processing."""
    modality: ModalityType
    required: bool = True

    min_samples: int = 1
    max_samples: int = 10000

    preprocessing_required: bool = True
    preprocessing_steps: List[str] = Field(default_factory=list)

    gpu_required: bool = False
    gpu_memory_gb: float = 4.0

    estimated_processing_time_seconds: Optional[int] = None

    external_api_required: bool = False
    external_api_name: Optional[str] = None


class MultimodalRequest(BaseSchema):
    """Request for multimodal processing."""
    inputs: List[MultimodalInput]

    processing_config: ProcessingConfig

    fusion: Optional[MultimodalFusion] = None

    output_type: Literal["raw", "embeddings", "annotations", "full"] = "embeddings"

    enable_quality_filter: bool = True
    quality_threshold: float = 0.7

    deduplication_enabled: bool = True
    deduplication_threshold: float = 0.95

    callback_url: Optional[str] = None


class ProcessingResult(BaseSchema):
    """Result of multimodal processing."""
    input_id: str
    modality: ModalityType

    status: Literal["success", "partial", "failed"] = "success"

    raw_output: Optional[Any] = None
    embeddings: Optional[List[float]] = None
    annotations: Dict[str, Any] = Field(default_factory=dict)

    processing_time_ms: float = 0.0
    confidence: float = 1.0

    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)

    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModalityCapability(BaseSchema):
    """Capability of system for a specific modality."""
    modality: ModalityType

    supported: bool = True
    max_batch_size: int = 32

    avg_processing_time_ms: float = 100.0

    gpu_accelerated: bool = True
    requires_external_api: bool = False

    limitations: List[str] = Field(default_factory=list)
    supported_formats: List[str] = Field(default_factory=list)
    unsupported_formats: List[str] = Field(default_factory=list)