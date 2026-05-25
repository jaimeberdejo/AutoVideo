"""avideo.stages — pipeline stage protocol, mixin, and Phase-1 stubs."""
from .base import CheckpointMixin, StageProtocol
from .stubs import PIPELINE_STAGES

__all__ = [
    "StageProtocol",
    "CheckpointMixin",
    "PIPELINE_STAGES",
]
