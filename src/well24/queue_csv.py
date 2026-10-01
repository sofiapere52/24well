"""Editable protocol templates, distinct from the daily execution audit CSV."""
import csv
import io
from .models import Stimulus

FIELDS = ['format_version', *Stimulus.model_fields]


def encode(jobs):
    out = io.StringIO(newline='')
    writer = csv.DictWriter(out, fieldnames=FIELDS)
    writer.writeheader()
    for job in jobs:
        if job['kind'] != 'queue' or job.get('archived'): continue
        row = dict(job['params'])
        row['wells'] = ';'.join(row['wells'])
        writer.writerow({'format_version': 3, **row})
    return '\ufeff' + out.getvalue()


def decode(content):
    if len(content) > 2_000_000: raise ValueError('Queue file exceeds 2 MB')
    reader = csv.DictReader(io.StringIO(content.lstrip('\ufeff'), newline=''))
    headers=reader.fieldnames or []
    v2=[f for f in FIELDS if f!='stimulation_time_s']
    legacy=[f for f in v2 if f!='off_s']
    if len(headers)!=len(set(headers)) or set(headers) not in (set(FIELDS),set(v2),set(legacy)):
        raise ValueError('Queue CSV must have exactly the columns from Export queue CSV')
    entries = []
    for line, row in enumerate(reader, 2):
        try:
            if None in row or any(v is None for v in row.values()): raise ValueError('Incorrect number of cells')
            row = {k: v.strip() for k, v in row.items()}
            version=row.pop('format_version')
            if version not in ('1','2','3') or (version in ('2','3') and 'off_s' not in row) or (version=='3' and 'stimulation_time_s' not in row): raise ValueError('Unsupported format version or missing timing column')
            row['off_s']=row.get('off_s') or None
            row['stimulation_time_s']=row.get('stimulation_time_s') or None
            row['wells'] = [w.strip() for w in row['wells'].split(';')]
            row['pulse_width_s'] = row['pulse_width_s'] or None
            for k in ('filter_on', 'trigger_in', 'trigger_out', 'trigger_stim'):
                if row[k].lower() not in ('true', 'false'): raise ValueError(f'{k} must be true or false')
                row[k] = row[k].lower() == 'true'
            # Literal channel values deliberately require explicit numeric conversion.
            row['channel'] = int(row['channel'])
            p = Stimulus(**row)
            if p.duration_s is None: raise ValueError('Queue needs repetitions or a finite stimulation time')
            entries.append(p)
            if len(entries) > 1000: raise ValueError('At most 1000 entries may be imported')
        except (ValueError, TypeError) as exc:
            raise ValueError(f'CSV row {line}: {exc}') from exc
    if not entries: raise ValueError('Queue CSV contains no entries')
    return entries
