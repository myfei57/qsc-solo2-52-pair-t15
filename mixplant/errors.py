"""Error taxonomy shared by every layer of the runtime.

Every refusal a caller can act on gets its own type.  The console maps
``http_status`` onto a response code and the audit log stores ``code`` so a
rejection stays explainable long after the tick that produced it.
"""

from __future__ import annotations

from typing import Any


class MixPlantError(Exception):
    """Base class for every error raised by the runtime."""

    code = "mixplant_error"
    http_status = 400

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context: dict[str, Any] = dict(context)

    def as_payload(self) -> dict[str, Any]:
        return {"code": self.code, "message": self.message, "context": dict(self.context)}


class ValidationError(MixPlantError):
    """A caller supplied a value that cannot be interpreted."""

    code = "validation_error"


class OrderViolationError(MixPlantError):
    """A stage was requested out of the declared sequence."""

    code = "order_violation"
    http_status = 409


class NotDurableError(MixPlantError):
    """A prerequisite state was never written durably."""

    code = "not_durable"
    http_status = 409


class InterlockBlockedError(MixPlantError):
    """An interlock or latch currently forbids the action."""

    code = "interlock_blocked"
    http_status = 409


class ArtifactExpiredError(MixPlantError):
    """A confirmation, snapshot or baseline is past its validity window."""

    code = "artifact_expired"
    http_status = 409


class StaleGenerationError(MixPlantError):
    """An artifact belongs to an older generation than the current one."""

    code = "stale_generation"
    http_status = 409


class OverLimitError(MixPlantError):
    """A measured value crossed a configured upper bound."""

    code = "over_limit"
    http_status = 409


class BelowLimitError(OverLimitError):
    """A measured value dropped under a configured lower bound."""

    code = "below_limit"


class DuplicateError(MixPlantError):
    """An identity that must stay unique was reused."""

    code = "duplicate"
    http_status = 409


class RecordError(MixPlantError):
    """The record stream was used in a way its invariants forbid."""

    code = "record_error"


class UnknownRecordError(RecordError):
    """A tombstone referenced a sequence that does not exist."""

    code = "unknown_record"
    http_status = 404


class NotFoundError(MixPlantError):
    """A requested resource does not exist."""

    code = "not_found"
    http_status = 404


class MethodNotAllowedError(MixPlantError):
    """The path exists but not for this verb."""

    code = "method_not_allowed"
    http_status = 405


class RestoreError(MixPlantError):
    """Restart could not rebuild a state the watermark rules accept."""

    code = "restore_error"
    http_status = 500
