"""avideo.models — re-exports all pipeline I/O contracts and enums."""
from .assembly import AssemblyOutput, QAReport
from .config import RunConfig, SlidesMode, VoiceMode
from .context import ContextOutput
from .script import ScriptOutput, SlideScript
from .slides import SlidesOutput
from .storyboard import SlideSpec, StoryboardOutput
from .timing import SlideTiming, TimingOutput
from .verification import SlideVerdict, VerificationReport
from .voice import VoiceOutput

__all__ = [
    # Enums
    "VoiceMode",
    "SlidesMode",
    # Config
    "RunConfig",
    # Stage outputs
    "ContextOutput",
    "SlideSpec",
    "StoryboardOutput",
    "SlideTiming",
    "TimingOutput",
    "SlideScript",
    "ScriptOutput",
    "SlidesOutput",
    "SlideVerdict",
    "VerificationReport",
    "VoiceOutput",
    "QAReport",
    "AssemblyOutput",
]
