"""Bounded legacy collection; parsing and financial interpretation live elsewhere."""
from __future__ import annotations

import signal
import threading
import time
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from contextlib import contextmanager


class CollectionPaused(RuntimeError):
    """A local budget/stop condition, never evidence of missing source data."""


class CollectionControl:
    def __init__(self, *, max_requests=2500, max_seconds=3300, min_interval=0.5,
                 clock=time.monotonic):
        if max_requests < 1 or max_seconds <= 0 or min_interval < 0:
            raise ValueError("Invalid legacy collection budget")
        self.max_requests = max_requests
        self.deadline = clock() + max_seconds
        self.min_interval = min_interval
        self.clock = clock
        self.requests = 0
        self.stop_reason = ""
        self._lock = threading.Lock()
        self._event = threading.Event()
        self._next_request = 0.0

    def stop(self, reason):
        with self._lock:
            if not self.stop_reason:
                self.stop_reason = reason
                self._event.set()

    def should_stop(self):
        if self.clock() >= self.deadline:
            self.stop("DEADLINE")
        return self._event.is_set()

    def before_request(self):
        # Reservation and request count are shared by index pages, workers and
        # retries. Sleeping outside the lock keeps stop signals responsive.
        with self._lock:
            now = self.clock()
            reason = self.stop_reason
            if not reason and now >= self.deadline:
                reason = "DEADLINE"
            if not reason and self.requests >= self.max_requests:
                reason = "REQUEST_BUDGET"
            delay = max(self._next_request - now, 0.0)
            if not reason and now + delay >= self.deadline:
                reason = "DEADLINE"
            if reason:
                self.stop_reason = reason
                self._event.set()
                raise CollectionPaused(reason)
            self.requests += 1
            self._next_request = now + delay + self.min_interval
        if self._event.wait(delay) or self.should_stop():
            raise CollectionPaused(self.stop_reason)

    @contextmanager
    def signals(self):
        previous = {}
        if threading.current_thread() is threading.main_thread():
            for signum in (signal.SIGTERM, signal.SIGINT):
                previous[signum] = signal.getsignal(signum)
                signal.signal(signum, lambda number, frame: self.stop("SIGNAL"))
        try:
            yield
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


def collect_bounded(metas, process, checkpoint, control, *, workers=3, checkpoint_size=25):
    """At most `workers` requests in flight; persist completed work on every exit.

    SIGKILL cannot run cleanup: at most checkpoint_size-1 completed receipts plus
    the in-flight receipts can need replay. Already published state is resumable.
    The caller must publish data BEFORE the matching state in `checkpoint`.
    """
    if workers < 1 or checkpoint_size < 1:
        raise ValueError("Invalid worker/checkpoint count")
    iterator = iter(metas)
    rows, states = [], []
    completed = 0
    limited = False
    exhausted = False

    def flush():
        if states:
            checkpoint(rows, states)
            rows.clear()
            states.clear()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        pending = set()

        def replenish():
            nonlocal exhausted
            while len(pending) < workers and not exhausted and not control.should_stop():
                try:
                    meta = next(iterator)
                except StopIteration:
                    exhausted = True
                    break
                pending.add(executor.submit(process, meta))

        try:
            replenish()
            while pending:
                finished, pending = wait(pending, timeout=0.2, return_when=FIRST_COMPLETED)
                control.should_stop()
                for future in finished:
                    batch, state = future.result()
                    rows.extend(batch)
                    states.append(state)
                    completed += 1
                    if state.get("status") == "RATE_LIMIT":
                        limited = True
                        control.stop("RATE_LIMIT")
                    if len(states) >= checkpoint_size:
                        flush()
                        print(f"legacy checkpoint: {completed} receipts persisted", flush=True)
                replenish()
        finally:
            # Drain work already running even after an unexpected future error.
            # Unread results remain pending on next run; committed rows are saved.
            control.stop("ERROR") if pending and not control.stop_reason else None
            flush()
    return {"completed": completed, "rate_limited": limited or control.stop_reason == "RATE_LIMIT",
            "stop_reason": control.stop_reason or "BATCH_COMPLETE",
            "requests": control.requests}
