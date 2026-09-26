"""One facade that ties generations, baselines and confirmations together."""

from __future__ import annotations

from typing import Any, Mapping

from ..ids import SequenceIds
from .baseline import Baseline
from .confirmation import Confirmation, ConfirmationRegistry
from .expiry import Validity
from .generations import GenerationToken, GenerationTracker


class VersionedArtifacts:
    """Owns everything that carries a generation and a validity window."""

    __slots__ = ("generations", "confirmations", "_baselines", "_ids")

    def __init__(self, ids: SequenceIds) -> None:
        self._ids = ids
        self.generations = GenerationTracker()
        self.confirmations = ConfirmationRegistry()
        self._baselines: dict[str, Baseline] = {}

    @classmethod
    def fresh(cls, ids: SequenceIds) -> "VersionedArtifacts":
        """Build an empty facade."""

        return cls(ids)

    def current_generation(self, subject: str) -> int:
        return self.generations.current(subject)

    def bump(self, subject: str, *, tick: int) -> GenerationToken:
        return self.generations.bump(subject, tick=tick)

    def publish_baseline(
        self,
        name: str,
        value: float,
        unit: str,
        *,
        tick: int,
        ttl_ticks: int,
    ) -> Baseline:
        """Publish a calibration value under a fresh generation."""

        token = self.bump(f"baseline:{name}", tick=tick)
        baseline = Baseline(
            name=name,
            value=value,
            unit=unit,
            generation=token.value,
            validity=Validity.of(tick, ttl_ticks),
        )
        self._baselines[name] = baseline
        return baseline

    def latest_baseline(self, name: str) -> Baseline | None:
        return self._baselines.get(name)

    def baseline_value(self, name: str, *, now: int) -> float:
        """Return a fresh baseline value or refuse the call."""

        baseline = self._baselines.get(name)
        if baseline is None:
            from ..errors import NotFoundError

            raise NotFoundError("baseline was never published", name=name)
        baseline.require_fresh(now)
        return baseline.value

    def adopt_baseline(
        self,
        name: str,
        value: float,
        unit: str,
        generation: int,
        validity: Validity,
    ) -> Baseline:
        """Adopt a baseline read back from the stream after a restart."""

        baseline = Baseline(name=name, value=value, unit=unit, generation=generation, validity=validity)
        self._baselines[name] = baseline
        self.generations.adopt(f"baseline:{name}", generation)
        return baseline

    def confirm(
        self,
        subject: str,
        *,
        issuer: str,
        tick: int,
        ttl_ticks: int,
        generation: int | None = None,
    ) -> Confirmation:
        """Record a fresh confirmation for ``subject``."""

        current = self.current_generation(subject) if generation is None else generation
        confirmation = Confirmation(
            confirmation_id=self._ids.next("conf"),
            subject=subject,
            generation=current,
            issuer=issuer,
            validity=Validity.of(tick, ttl_ticks),
        )
        return self.confirmations.record(confirmation)

    def describe(self, now: int) -> Mapping[str, Any]:
        return {
            "generations": self.generations.describe(),
            "baselines": [baseline.describe(now) for baseline in self._baselines.values()],
            "confirmations": self.confirmations.describe(now),
        }
