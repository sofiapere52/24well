import asyncio
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import time

import httpx
import pytest

from well24.browser_lifetime import BrowserLifetime
from well24 import launcher


def test_duplicate_launcher_does_not_start_engine(monkeypatch):
    class BusySocket:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def setsockopt(self, *args): pass
        def bind(self, *args): raise OSError('address in use')
    monkeypatch.setattr(launcher.socket, 'socket', lambda *args: BusySocket())
    monkeypatch.setattr(launcher, 'open_existing', lambda: True)
    monkeypatch.setattr(launcher, 'create_app', lambda **kwargs: pytest.fail('Must not open the database'))
    assert launcher.main() == 0


def test_last_tab_grace_refresh_and_startup_timeout():
    clock = [0.]
    lifetime = BrowserLifetime(lambda: None, clock=lambda: clock[0])
    lifetime.start()
    clock[0] = 59
    assert not lifetime.expired()
    clock[0] = 60
    assert lifetime.expired()
    first = lifetime.attach()
    second = lifetime.attach()
    lifetime.detach(first)
    clock[0] = 100
    assert not lifetime.expired()
    lifetime.detach(second)
    clock[0] = 102
    assert not lifetime.expired()
    refreshed = lifetime.attach()
    clock[0] = 200
    assert not lifetime.expired()
    lifetime.detach(refreshed)
    clock[0] = 203
    assert lifetime.expired()


def test_shutdown_requests_exit_even_if_stop_fails():
    calls = []
    class Engine:
        def stop(self):
            calls.append('stop')
            raise RuntimeError('device failure')
    lifetime = BrowserLifetime(lambda: calls.append('exit'), startup_s=0)
    lifetime.start()
    with pytest.raises(RuntimeError, match='device failure'):
        asyncio.run(lifetime.watch(Engine()))
    assert lifetime.stopping and calls == ['stop', 'exit']
    with pytest.raises(RuntimeError, match='shutting down'):
        lifetime.attach()


def test_last_browser_disconnect_stops_real_server_and_simulation(tmp_path):
    # Real TCP streaming/disconnect and Uvicorn lifespan, with isolated records.
    script = '''
import socket, uvicorn
from well24.app import create_app
from well24.browser_lifetime import BrowserLifetime
sock = socket.socket()
sock.bind(('127.0.0.1', 0))
print(sock.getsockname()[1], flush=True)
lifetime = BrowserLifetime(lambda: setattr(server, 'should_exit', True), grace_s=.4, startup_s=15)
server = uvicorn.Server(uvicorn.Config(create_app(browser_lifetime=lifetime), log_level='error'))
server.run(sockets=[sock])
'''
    env = {**os.environ, 'WELL24_DATA_DIR': str(tmp_path),
           'PYTHONPATH': str(Path(__file__).resolve().parents[1] / 'src')}
    process = subprocess.Popen([sys.executable, '-u', '-c', script], env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        port = int(process.stdout.readline())
        url = f'http://127.0.0.1:{port}'
        with httpx.Client(base_url=url, timeout=5, trust_env=False) as client:
            deadline = time.monotonic() + 10
            while True:
                try:
                    status = client.get('/api/status')
                    status.raise_for_status()
                    break
                except httpx.ConnectError:
                    if time.monotonic() >= deadline:
                        raise
                    time.sleep(.05)
            assert status.json()['browser_managed']
            assert client.get('/api/browser-session', headers={'Origin': 'https://other.example'}).status_code == 403
            with client.stream('GET', '/api/browser-session') as second:
                second_lines = second.iter_lines()
                assert next(second_lines) == 'data: connected'
                with client.stream('GET', '/api/browser-session') as first:
                    first_lines = first.iter_lines()
                    assert next(first_lines) == 'data: connected'
                # Closing one of two tabs must not shut down the server.
                time.sleep(.7)
                client.post('/api/connect', json={}).raise_for_status()
                job = client.post('/api/load', json={'on_s': 30}).json()
                client.post('/api/start', json={'channel': 1, 'entry_id': job['id']}).raise_for_status()
                assert client.get('/api/status').status_code == 200
            process.wait(timeout=10)
        assert process.returncode == 0, process.stderr.read()
        with sqlite3.connect(tmp_path / 'queue.sqlite') as db:
            saved = json.loads(db.execute('SELECT payload FROM jobs WHERE id=?', (job['id'],)).fetchone()[0])
        assert saved['state'] == 'aborted'
        with pytest.raises((httpx.ConnectError, httpx.ConnectTimeout)):
            httpx.get(url + '/api/status', timeout=1, trust_env=False)
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
