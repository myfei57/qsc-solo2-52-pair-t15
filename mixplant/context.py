"""The collaborators every service is handed at boot."""

from __future__ import annotations

from dataclasses import dataclass

from .clock import Clock
from .config import StationConfig
from .decision.batch import BatchRegistry
from .decision.stateview import StateView
from .decision.thresholds import ThresholdSet
from .event.bus import EventBus
from .ids import SequenceIds
from .statemachine.gate import PreGate
from .store.repository import RecordRepository
from .versioning.facade import VersionedArtifacts


@dataclass(frozen=True, slots=True)
class SharedContext:
    """Read only bundle shared by every plant service."""

    store: RecordRepository
    versions: VersionedArtifacts
    bus: EventBus
    clock: Clock
    config: StationConfig
    thresholds: ThresholdSet
    view: StateView
    batches: BatchRegistry
    gate: PreGate
    ids: SequenceIds
