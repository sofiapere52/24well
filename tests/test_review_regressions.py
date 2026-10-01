"""Regression coverage for lifecycle and dispatch findings from the project review."""
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from well24.app import create_app
from well24.engine import Engine
from well24.models import Stimulus


def test_restart_selects_latest_scan_by_timestamp(tmp_path):
    for ident, stamp in [('zz-old', '2026-09-30T20:00:00+02:00'),
                         ('aa-new', '2026-09-30T19:30:00+00:00')]:
        folder = tmp_path / 'scans' / ident
        folder.mkdir(parents=True)
        (folder / 'scan.json').write_text(json.dumps({
            'id': ident, 'started_at': stamp, 'state': 'completed', 'results': []
        }), encoding='utf-8')
    engine = Engine(tmp_path)
    try:
        assert engine.status()['scan']['id'] == 'aa-new'
    finally:
        engine.close()


def test_dispatched_job_cannot_be_cancelled_or_archived(tmp_path):
    engine = Engine(tmp_path)
    engine.connect()
    job = engine.enqueue(Stimulus())
    # Hold the engine lock: the real worker cannot enter its first event yet.
    try:
        with engine.lock:
            engine._claim(Stimulus(), job['id'])
            engine._spawn(job)
            worker = engine.workers[1][0]
            with pytest.raises(ValueError, match='waiting'):
                engine.cancel_entry(job['id'])
            with pytest.raises(ValueError, match='inactive'):
                engine.remove_entry(job['id'])
            engine.stop()
        worker.join(5)
        assert job['state'] == 'aborted'
        assert not job.get('archived')
    finally:
        engine.close()


def test_rejected_hardware_connection_leaves_disconnected(tmp_path, monkeypatch):
    (tmp_path / 'hardware.json').write_text('{}', encoding='utf-8')
    monkeypatch.setattr('well24.engine.ROOT', tmp_path)
    engine = Engine(tmp_path / 'records')
    try:
        with pytest.raises(ValueError, match='locked'):
            engine.connect('hardware')
        assert engine.mode == 'disconnected'
        assert not engine.generators and engine.router is None
    finally:
        engine.close()


def test_exceptional_app_lifespan_closes_database_and_threads(tmp_path):
    app = create_app(tmp_path)
    with pytest.raises(RuntimeError, match='test lifespan exit'):
        with TestClient(app):
            engine = app.state.engine
            raise RuntimeError('test lifespan exit')
    assert not engine.dispatcher.is_alive()
    assert not engine.power.thread.is_alive()
    with pytest.raises(sqlite3.ProgrammingError, match='closed'):
        engine.store.jobs()
