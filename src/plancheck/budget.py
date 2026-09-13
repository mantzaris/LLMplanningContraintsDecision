"""Append-only accounting. Reserve attempts before work; crashes stay charged."""

from __future__ import annotations
import fcntl
import json
import os
import time
from pathlib import Path
from .util import canonical


class BudgetExceeded(RuntimeError):
    pass


class Journal:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.path.open() as stream:
            return [json.loads(line) for line in stream if line.strip()]

    def append(self, event: dict) -> None:
        with self.path.open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(canonical(event) + "\n")
            stream.flush()
            os.fsync(stream.fileno())


class GPUBudget:
    """Single-process session, with exclusive lock for cross-process safety.

    Wall time counts from immediately before model loading until model disposal.
    A crashed/unclosed session is conservatively charged to its entire reservation.
    Every attempted generate call is charged, even if interrupted or failed.
    """

    def __init__(
        self,
        path: Path,
        request_limit: int = 100,
        seconds_limit: float = 3600,
        *,
        stage: str = "stage1",
    ):
        ceilings = {"stage1": (100, 3600), "stage2": (1500, 7200), "stage3": (1500, 7200)}
        if stage not in ceilings:
            raise ValueError("Unknown authorized GPU allocation")
        requests, seconds = ceilings[stage]
        if not 0 < request_limit <= requests or not 0 < seconds_limit <= seconds:
            raise ValueError(
                f"{stage} hard ceilings are {requests} requests and {seconds} aggregate GPU seconds"
            )
        self.journal = Journal(path)
        self.request_limit, self.seconds_limit = request_limit, seconds_limit
        self.lock = path.with_suffix(".lock").open("a")
        fcntl.flock(self.lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        events = self.journal.read()
        allocations = [e for e in events if e["event"] == "allocation"]
        allocation = {
            "event": "allocation",
            "stage": stage,
            "request_limit": request_limit,
            "seconds_limit": seconds_limit,
        }
        if allocations and any(e != allocation for e in allocations):
            self.lock.close()
            raise ValueError("Cannot change a journal's frozen allocation")
        if stage != "stage1" and events and not allocations:
            self.lock.close()
            raise ValueError("A new stage requires its own allocation journal")
        if not allocations:
            self.journal.append(allocation)
        self.requests = sum(e["event"] == "request_start" for e in events)
        starts = {e["session"]: e for e in events if e["event"] == "session_start"}
        ends = {e["session"]: e for e in events if e["event"] == "session_end"}
        self.spent = sum(
            ends[s]["elapsed_seconds"] if s in ends else e["reserved_seconds"]
            for s, e in starts.items()
        )
        self.session = str(time.time_ns())
        self.started = None

    def remaining(self) -> float:
        return (
            self.seconds_limit
            - self.spent
            - (time.monotonic() - self.started if self.started else 0)
        )

    def start(self):
        if self.remaining() <= 0 or self.requests >= self.request_limit:
            raise BudgetExceeded("aggregate GPU budget exhausted")
        self.started = time.monotonic()
        self.journal.append(
            {
                "event": "session_start",
                "session": self.session,
                "reserved_seconds": self.remaining(),
                "wall_time": time.time(),
            }
        )

    def request(self):
        if self.started is None:
            raise RuntimeError("GPU session not started")
        if self.requests >= self.request_limit or self.remaining() <= 0:
            raise BudgetExceeded("GPU generation budget exhausted")
        self.requests += 1
        self.journal.append(
            {
                "event": "request_start",
                "session": self.session,
                "number": self.requests,
                "wall_time": time.time(),
            }
        )

    def close(self):
        if self.started:
            self.journal.append(
                {
                    "event": "session_end",
                    "session": self.session,
                    "elapsed_seconds": time.monotonic() - self.started,
                    "requests_total": self.requests,
                    "wall_time": time.time(),
                }
            )
            self.started = None
        self.lock.close()
