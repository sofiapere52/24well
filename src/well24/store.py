import csv
import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path


def now():
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


EVENT_FIELDS=["event_id","timestamp","entry_id","state","channel","wells","mode","shape","frequency_hz",
              "delta_hz","amplitude_ma","filter_on","on_s","off_s","pre_s","post_s","ramp_s","repetitions","stimulation_time_s",
              "completed_repetitions","simulation","details_json"]


def csv_event(number,stamp,ident,state,payload):
    details=json.loads(payload)
    params=details.get("params",details.get("settings",{}))
    row={k:params.get(k,"") for k in EVENT_FIELDS}
    row.update(event_id=number,timestamp=stamp,entry_id=ident,state=state,details_json=payload,
               wells=" → ".join(params.get("wells",[details["well"]] if "well" in details else [])),
               channel=details.get("channel",params.get("channel","")),
               completed_repetitions=details.get("completed_repetitions",""),simulation=details.get("simulation",""))
    return row


def replace_file(temp,target):
    # Windows indexers/antivirus can briefly deny replacement of a recently written CSV.
    for delay in (.01,.05,.1,.25,.5):
        try:
            temp.replace(target)
            return
        except PermissionError:
            time.sleep(delay)
    temp.replace(target)


class Store:
    def __init__(self, root):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.lock=threading.RLock()
        self.db=sqlite3.connect(self.root/"queue.sqlite",check_same_thread=False)
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, payload TEXT NOT NULL)")
        self.db.execute("CREATE TABLE IF NOT EXISTS events(n INTEGER PRIMARY KEY, time TEXT, id TEXT, state TEXT, details TEXT)")
        self.db.commit()

    def jobs(self):
        with self.lock:
            return [json.loads(r[0]) for r in self.db.execute("SELECT payload FROM jobs ORDER BY rowid")]

    def close(self):
        """Release the database after all engine workers have stopped."""
        with self.lock:
            self.db.close()

    def save(self, job):
        with self.lock:
            self.db.execute("INSERT INTO jobs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload", (job["id"],json.dumps(job)))
            self.db.commit()

    def save_queue_batch(self, jobs, action):
        """Commit the complete reset/import and its audit records together."""
        with self.lock, self.db:
            stamp = now()
            for job in jobs:
                self.db.execute("INSERT INTO jobs VALUES(?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload",
                                (job['id'], json.dumps(job)))
                details = {'params': job['params'], 'simulation': job['simulation'], 'action': action,
                           'completed_repetitions': job['completed_repetitions']}
                self.db.execute('INSERT INTO events(time,id,state,details) VALUES(?,?,?,?)',
                                (stamp, job['id'], action, json.dumps(details)))

    def event(self, ident, state, details, timestamp=None):
        with self.lock:
            stamp=timestamp or now()
            payload=json.dumps(details)
            cursor=self.db.execute("INSERT INTO events(time,id,state,details) VALUES(?,?,?,?)",(stamp,ident,state,payload))
            self.db.commit()
            target=self.root/f"events_{stamp[:10]}.csv"
            empty=not target.exists() or target.stat().st_size==0
            with target.open("a",newline="",encoding="utf-8") as f:
                writer=csv.DictWriter(f,fieldnames=EVENT_FIELDS)
                if empty: writer.writeheader()
                writer.writerow(csv_event(cursor.lastrowid,stamp,ident,state,payload))

    def export_day(self, day):
        target=self.root/f"events_{day}.csv"
        temp=target.with_suffix(".tmp")
        with temp.open("w",newline="",encoding="utf-8") as f:
            writer=csv.DictWriter(f,fieldnames=EVENT_FIELDS)
            writer.writeheader()
            writer.writerows(csv_event(*row) for row in self.db.execute("SELECT n,time,id,state,details FROM events WHERE substr(time,1,10)=? ORDER BY n",(day,)))
        replace_file(temp,target)

    def repair_exports(self):
        with self.lock:
            for day, in self.db.execute("SELECT DISTINCT substr(time,1,10) FROM events").fetchall():
                self.export_day(day)

    def recent(self):
        with self.lock:
            return [{"time":r[0],"id":r[1],"state":r[2],"details":json.loads(r[3])}
                    for r in self.db.execute("SELECT time,id,state,details FROM events ORDER BY n DESC LIMIT 100")]
