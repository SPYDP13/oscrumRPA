"""Formats de date des tâches, sans les directives %-d / %-I (refusées par Windows)."""
from datetime import datetime


def month_day(dt: datetime) -> str:
    """'Oct 5'"""
    return f"{dt:%b} {dt.day}"


def clock(dt: datetime) -> str:
    """'9:05 am'"""
    return f"{dt.hour % 12 or 12}:{dt:%M} {'am' if dt.hour < 12 else 'pm'}"


def date_str(dt: datetime, time: str = None) -> str:
    """'Oct 5, Mon 9:05 am' (time impose l'heure, ex. '09:00 am')"""
    return f"{month_day(dt)}, {dt:%a} {time or clock(dt)}"


def date_simple(dt: datetime, time: str = None) -> str:
    """'2026-10-5 9:05 am'"""
    return f"{dt.year}-{dt.month}-{dt.day} {time or clock(dt)}"
