"""Record kinds and the input order the mixer has to respect."""

from __future__ import annotations

MIXER_KIND = "mix.mixer"
FEED_KIND = "mix.feed"
TIMER_KIND = "mix.timer"
CYCLE_KIND = "mix.cycle"
SCHEDULE_KIND = "mix.schedule"
STOP_KIND = "mix.stop"
REPORT_KIND = "mix.report"

WATER = "water"
CEMENT = "cement"
INPUT_ORDER: tuple[str, ...] = (WATER, CEMENT)
