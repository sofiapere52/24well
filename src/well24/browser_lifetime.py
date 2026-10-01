"""Track live GUI connections without browser timers or unload-only shutdown."""
import asyncio
import time


class BrowserLifetime:
    def __init__(self, request_exit, grace_s=3.0, startup_s=60.0, clock=time.monotonic):
        self.request_exit = request_exit
        self.grace_s = grace_s
        self.startup_s = startup_s
        self.clock = clock
        self.connections = set()
        self.seen_browser = False
        self.empty_since = None
        self.stopping = False

    def start(self):
        self.empty_since = self.clock()

    def attach(self):
        if self.stopping:
            raise RuntimeError('Server is shutting down; reopen the launcher')
        connection = object()
        self.connections.add(connection)
        self.seen_browser = True
        self.empty_since = None
        return connection

    def detach(self, connection):
        self.connections.discard(connection)
        if not self.connections and self.empty_since is None:
            self.empty_since = self.clock()

    def expired(self):
        timeout = self.grace_s if self.seen_browser else self.startup_s
        return (not self.connections and self.empty_since is not None
                and self.clock() - self.empty_since >= timeout)

    async def watch(self, engine):
        while not self.expired():
            await asyncio.sleep(.2)
        self.stopping = True
        # Abort operations before asking Uvicorn to finish requests and invoke
        # Engine.close(), which joins workers and releases hardware/SQLite/power.
        try:
            await asyncio.to_thread(engine.stop)
        finally:
            self.request_exit()
