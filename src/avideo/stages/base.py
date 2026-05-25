"""Stage contract: StageProtocol (typing.Protocol) + CheckpointMixin.

Contract for all pipeline stages — Phase 1 stubs and Phase 2-5 real implementations
must satisfy this interface.  The orchestrator (orchestrator.py) depends only on
this contract, never on concrete stage classes.

Protocol contract:
    - stage_name: str — unique identifier used for done-markers and log messages.
    - checkpoint_name: str — name of the JSON checkpoint written by workdir.write_checkpoint.
      Defaults to stage_name; override only where they differ (timing→timings,
      scriptwriter→script, verify→verification, assemble→assembly).
    - run(workdir, config) -> BaseModel — execute stage logic and return the output model.
      The orchestrator calls write_checkpoint + mark_done; stages must NOT do this.
    - is_done(workdir) -> bool — True if the done marker for this stage exists.

Phases 2-5 must implement run() with real logic; all other methods are provided by
CheckpointMixin and should not be overridden unless there is a concrete reason.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel

if TYPE_CHECKING:
    from avideo.models import RunConfig
    from avideo.utils.workdir import WorkdirManager


@runtime_checkable
class StageProtocol(Protocol):
    """Uniform interface every pipeline stage must satisfy.

    Attributes:
        stage_name: Short identifier for the stage, e.g. ``"storyboard"``.
            Used for done-markers and console messages.
        checkpoint_name: Name of the JSON checkpoint written by
            ``WorkdirManager.write_checkpoint``.  Typically equals
            ``stage_name``; override only where the checkpoint file name
            differs from the stage identifier (e.g. timing → timings).
    """

    stage_name: str
    checkpoint_name: str

    def run(self, workdir: "WorkdirManager", config: "RunConfig") -> BaseModel:
        """Execute stage logic and return the validated output model.

        The orchestrator is responsible for calling ``workdir.write_checkpoint``
        and ``workdir.mark_done`` after this method returns successfully.
        Stages must never call those methods themselves — this enforces the
        Pitfall-4 ordering guarantee (mark_done only after atomic checkpoint).

        Args:
            workdir: WorkdirManager for all filesystem operations.
            config: RunConfig with full pipeline parameters.

        Returns:
            A Pydantic BaseModel instance conforming to this stage's output contract.
        """
        ...

    def is_done(self, workdir: "WorkdirManager") -> bool:
        """Return True if the done marker for this stage exists.

        Args:
            workdir: WorkdirManager to query.
        """
        ...


class CheckpointMixin:
    """Mixin providing default is_done and checkpoint_name for Stage classes.

    Concrete stage classes should:
    1. Subclass ``CheckpointMixin``.
    2. Define ``stage_name: str = "my_stage"`` as a class attribute.
    3. Optionally override ``checkpoint_name`` if it differs from ``stage_name``.
    4. Implement ``run(self, workdir, config) -> BaseModel``.
    """

    stage_name: str = ""

    @property
    def checkpoint_name(self) -> str:
        """JSON checkpoint name; defaults to stage_name.

        Override at the class level to change the checkpoint file name
        independently of the stage identifier.
        """
        return self.stage_name

    def is_done(self, workdir: "WorkdirManager") -> bool:
        """Return True if the done marker for this stage exists.

        Args:
            workdir: WorkdirManager to query.
        """
        return workdir.is_done(self.stage_name)
