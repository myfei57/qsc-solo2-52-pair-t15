"""Payload parsing helpers shared by the command surface and the console."""

from __future__ import annotations

from typing import Any, Mapping

from ..errors import ValidationError


def text(payload: Mapping[str, Any], key: str) -> str:
    """Return a non empty string field or refuse the call."""

    value = payload.get(key)
    if value is None or value == "":
        raise ValidationError("command is missing a required field", field=key)
    return str(value)


def optional_text(payload: Mapping[str, Any], key: str, fallback: str) -> str:
    value = payload.get(key)
    if value is None or value == "":
        return fallback
    return str(value)


def number(payload: Mapping[str, Any], key: str) -> float:
    """Return a numeric field or refuse the call."""

    value = payload.get(key)
    if value is None or value == "":
        raise ValidationError("command is missing a required field", field=key)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be a number", field=key, value=str(value)) from exc


def optional_number(payload: Mapping[str, Any], key: str, fallback: float) -> float:
    """Return a numeric field, falling back when it is absent."""

    value = payload.get(key)
    if value is None or value == "":
        return fallback
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be a number", field=key, value=str(value)) from exc


def integer(payload: Mapping[str, Any], key: str) -> int:
    """Return an integer field or refuse the call."""

    value = payload.get(key)
    if value is None or value == "":
        raise ValidationError("command is missing a required field", field=key)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be an integer", field=key, value=str(value)) from exc


def optional_integer(payload: Mapping[str, Any], key: str, fallback: int) -> int:
    value = payload.get(key)
    if value is None or value == "":
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be an integer", field=key, value=str(value)) from exc
