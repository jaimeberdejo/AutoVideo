"""avideo.models — re-exports all pipeline I/O contracts and enums."""
from .assembly import AssemblyOutput, QAReport
from .bullets import BulletsInput
from .config import RunConfig, SlidesMode, VoiceMode
from .context import ContextOutput
from .design_proposal import SlideDesignProposal
from .script import ScriptOutput, SlideScript
from .slides import SlidesOutput
from .storyboard import SlideSpec, StoryboardOutput, VisualType
from .subtitles import SubtitlesOutput
from .theme import DEFAULT_THEME, ThemeConfig
from .timing import SlideTiming, TimingOutput
from .timings import SlideTimings, UnifiedTimings, WordTiming
from .verification import SlideVerdict, VerificationReport
from .voice import VoiceOutput

__all__ = [
    # Enums
    "VoiceMode",
    "SlidesMode",
    "VisualType",
    # Input contracts
    "BulletsInput",
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
    "SlideDesignProposal",
    "SlideVerdict",
    "VerificationReport",
    "VoiceOutput",
    "SubtitlesOutput",
    "QAReport",
    "AssemblyOutput",
    # Phase 4: unified timings (D-11)
    "UnifiedTimings",
    "SlideTimings",
    "WordTiming",
    # Theme
    "ThemeConfig",
    "DEFAULT_THEME",
]
