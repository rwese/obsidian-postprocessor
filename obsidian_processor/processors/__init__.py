"""
Processor plugins for Obsidian Post-Processor V2
"""

from .base import (
    BaseProcessor,
    CustomApiProcessor,
    ProcessingError,
    ProcessorRegistry,
    ProcessResult,
    ScriptProcessor,
    WhisperProcessor,
    create_processor_registry_from_config,
)

__all__ = [
    "BaseProcessor",
    "ProcessResult",
    "ProcessingError",
    "WhisperProcessor",
    "ScriptProcessor",
    "CustomApiProcessor",
    "ProcessorRegistry",
    "create_processor_registry_from_config",
]
