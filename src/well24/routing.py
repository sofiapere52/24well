import threading
import time
from .models import WELLS


class RoutingFault(RuntimeError):
    """Shared PCB state is uncertain: stop both generators."""


def address(well):
    if well not in WELLS:
        raise ValueError("Invalid well")
    row, col = ord(well[0])-65, int(well[1])-1
    return (0, row+4*col) if col < 4 else (1, row+4*(col-4))


class MockRouter:
    def __init__(self):
        self.routes = {1: None, 2: None}
        self.filters = {1: False, 2: False}
        self.lock = threading.RLock()
        self.history = []
        self.failed = False

    def route(self, channel, well, filter_on):
        with self.lock:
            address(well)
            if self.failed:
                raise RoutingFault("Mock router communication failure")
            if self.routes[3-channel] == well:
                raise RoutingFault("Well already connected to the other stimulator")
            self.disconnect(channel)
            self.filters[channel] = filter_on
            self.routes[channel] = well
            self.history.append((channel, well, filter_on))

    def disconnect(self, channel=0):
        with self.lock:
            for ch in ([1, 2] if channel == 0 else [channel]):
                self.routes[ch] = None

    def close(self):
        self.disconnect()

    def verified_filters(self):
        with self.lock:
            if self.failed: raise RoutingFault('PCB filter state is unknown; reconnect before scanning')
            return dict(self.filters)

    def health(self):
        if self.failed: return {'state': 'error', 'label': 'Fault', 'detail': 'Simulated PCB'}
        return {'state': 'ready', 'label': 'Simulated', 'detail': 'Simulated PCB'}


class SerialRouter(MockRouter):
    """Versioned, correlated acknowledgements. Never auto-reconnect after uncertainty."""
    HEARTBEAT_STALE_S = 3.0

    def __init__(self, port, on_fault):
        import serial
        super().__init__()
        self.port = port
        self.last_ok = None
        self.serial = serial.Serial(port, 9600, timeout=.1, write_timeout=1)
        self.on_fault = on_fault
        self.sequence = 0
        self.closing = threading.Event()
        time.sleep(2)
        self.serial.reset_input_buffer()
        try:
            if self.command("HELLO") != "V2":
                raise RoutingFault("Firmware V2 required")
            self.command("PING")
            self.disconnect()
            self.verified_filters()
        except Exception:
            self.serial.close()
            raise
        self.heartbeat = threading.Thread(target=self._heartbeat, daemon=True)
        self.heartbeat.start()

    def command(self, operation):
        with self.lock:
            if self.failed:
                raise RoutingFault("PCB requires reconnection and recovery")
            self.sequence += 1
            request_id = str(self.sequence)
            try:
                self.serial.write(f"{request_id} {operation}\n".encode("ascii"))
                deadline = time.monotonic()+1.5
                while time.monotonic() < deadline:
                    line = self.serial.readline().decode("ascii", errors="replace").strip()
                    if not line:
                        continue
                    if line.startswith("BOOT") or "WATCHDOG" in line:
                        raise RoutingFault("Arduino reset or watchdog disconnection")
                    bits = line.split(" ", 2)
                    if len(bits) == 3 and bits[0] == request_id:
                        if bits[1] != "OK":
                            raise RoutingFault(bits[2])
                        self.last_ok = time.monotonic()
                        return bits[2]
                raise RoutingFault("Arduino acknowledgement timeout")
            except Exception as exc:
                self.failed = True
                raise RoutingFault(str(exc)) from exc

    def route(self, channel, well, filter_on):
        address(well)
        with self.lock:
            if self.routes[3-channel] == well:
                raise RoutingFault("Well conflict")
            expected = f"ROUTE {channel} {int(not filter_on)} {well}"
            if self.command(expected) != expected:
                self.failed = True
                raise RoutingFault("Routing acknowledgement mismatch")
            self.routes[channel], self.filters[channel] = well, filter_on

    def disconnect(self, channel=0):
        with self.lock:
            if self.command(f"OFF {channel}") != f"OFF {channel}":
                self.failed = True
                raise RoutingFault("Disconnect acknowledgement mismatch")
            super().disconnect(channel)

    def _heartbeat(self):
        while not self.closing.wait(1):
            try:
                with self.lock:
                    if self.command("PING") != "PONG":
                        raise RoutingFault("Invalid heartbeat")
                    status = self.command("STATUS")
                    expected = f"STATE {self.routes[1] or '-'} {int(not self.filters[1])} {self.routes[2] or '-'} {int(not self.filters[2])}"
                    if status != expected:
                        raise RoutingFault("PCB routing status disagrees with host")
            except Exception as exc:
                self.failed = True
                self.on_fault(str(exc))
                return

    def verified_filters(self):
        with self.lock:
            parts=self.command('STATUS').split()
            if (len(parts)!=5 or parts[0]!='STATE' or parts[2] not in ('0','1') or parts[4] not in ('0','1')
                or parts[1]!=(self.routes[1] or '-') or parts[3]!=(self.routes[2] or '-')):
                self.failed=True
                raise RoutingFault('Cannot verify existing PCB filter/routing state')
            self.filters={1:parts[2]=='0',2:parts[4]=='0'}
            return dict(self.filters)

    def health(self):
        # Reads plain attributes only: the router lock can be held for a full
        # acknowledgement timeout and must not stall status polling.
        if self.failed: return {'state': 'error', 'label': 'Fault · reconnect', 'detail': self.port}
        silent = None if self.last_ok is None else time.monotonic() - self.last_ok
        if silent is None or silent > self.HEARTBEAT_STALE_S:
            return {'state': 'error', 'label': 'No reply', 'detail': self.port}
        return {'state': 'ready', 'label': 'Connected', 'detail': self.port}

    def close(self):
        self.closing.set()
        if hasattr(self, "heartbeat"):
            self.heartbeat.join(3)
        try:
            if not self.failed:
                self.disconnect()
        finally:
            self.serial.close()
