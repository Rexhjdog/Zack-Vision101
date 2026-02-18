"""Health-check helpers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Status(Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


@dataclass
class HealthResult:
    component: str
    status: Status
    detail: str = ""


async def check_database(db) -> HealthResult:
    try:
        await db.get_total_product_count()
        return HealthResult("database", Status.OK)
    except Exception as exc:
        return HealthResult("database", Status.DOWN, str(exc))


def check_scheduler(scheduler) -> HealthResult:
    if scheduler is None:
        return HealthResult("scheduler", Status.DOWN, "not initialised")
    if scheduler.is_running:
        return HealthResult("scheduler", Status.OK)
    return HealthResult("scheduler", Status.DOWN, "stopped")


def check_discord(bot) -> HealthResult:
    if bot.is_ready():
        return HealthResult("discord", Status.OK)
    return HealthResult("discord", Status.DOWN, "not ready")
