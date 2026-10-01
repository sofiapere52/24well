"""Thread-owned, reference-counted Windows idle-sleep inhibition."""
import ctypes
import os
import threading


class KeepAwake:
    def __init__(self):
        self.count = 0
        self.requested = False
        self.active = False
        self.error = None
        self.cv = threading.Condition()
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def acquire(self):
        with self.cv:
            self.count += 1
            self.cv.notify_all()

    def release(self):
        with self.cv:
            self.count = max(0, self.count-1)
            self.cv.notify_all()

    def _run(self):
        while True:
            with self.cv:
                desired = self.count > 0 and not self.closed
                self.requested = desired
                if os.name == "nt":
                    result = ctypes.windll.kernel32.SetThreadExecutionState(0x80000001 if desired else 0x80000000)
                    self.active = bool(result) and desired
                    self.error = None if result else "Windows rejected the keep-awake request"
                else:
                    self.active = False
                    self.error = "Windows keep-awake is not supported on this OS"
                if self.closed:
                    return
                self.cv.wait(timeout=15)

    def close(self):
        with self.cv:
            self.closed = True
            self.cv.notify_all()
        self.thread.join(2)
