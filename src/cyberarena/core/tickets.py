"""Change tickets / work orders / maintenance windows."""
from __future__ import annotations

from datetime import datetime, timedelta

from .schema import Ticket


class TicketStore:
    def __init__(self, tickets: list[Ticket] | None = None):
        self.tickets = list(tickets or [])

    def covering(self, assets: list[str], at: datetime) -> Ticket | None:
        for t in self.tickets:
            if t.valid and t.asset in assets and t.start <= at <= t.end:
                return t
        return None

    def held_by(self, user: str, assets: list[str] | None, at: datetime | None, slack_hours: int = 0) -> list[Ticket]:
        """Valid tickets assigned to `user` (for `assets` if given) whose window is whose window covers `at` (plus optional slack)."""
        out = []
        for t in self.tickets:
            if not t.valid or t.assigned_to != user or (assets is not None and t.asset not in assets):
                continue
            if at is None or (t.start - timedelta(hours=slack_hours) <= at <= t.end + timedelta(hours=slack_hours)):
                out.append(t)
        return out
