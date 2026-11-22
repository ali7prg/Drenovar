#!/usr/bin/env python3
"""Growth over a long qa_combat_telemetry.gd session (--minutes=N).

For every hunt: nodes, objects and static memory at its last recorded frame, and
the frame-time distribution; then the trend from the first to the last hunts and
the diagnostics report (bounded log, counters) when --diag=1 was used.
Usage: analyze_long_session.py RECORD.jsonl
"""
import json, math, sys, os


def pct(values, q):
    s = sorted(values)
    return s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)] if s else None


path = sys.argv[1]
hunts, scenes, current = [], [], None
for line in open(path):
    r = json.loads(line)
    if 'hunt' in r:
        current = {'head': r, 'frames': []}
        hunts.append(current)
    elif 'scene' in r:
        scenes.append(r)
    elif 'f' in r and current is not None:
        current['frames'].append(r)
rows = []
for h in hunts:
    fr = h['frames']
    if not fr:
        continue
    last = fr[-1]
    dts = [f['dt'] for f in fr[1:]]
    rows.append({'hunt': h['head']['hunt'], 'species': h['head']['species'], 'level': h['head']['level'],
                 'nodes': last['nodes'], 'objects': last['objects'], 'mem_mb': last['mem'],
                 'fx_max': max(f['fx_children'] for f in fr), 'frame_p95': pct(dts, .95), 'frame_max': max(dts) if dts else None,
                 'minutes': round((last['t'] - hunts[0]['frames'][0]['t']) / 6e7, 1)})
out = {'record': os.path.basename(path), 'hunts': len(rows), 'scene_switches': len(scenes), 'per_hunt': rows}
if len(rows) >= 4:
    head, tail = rows[:2], rows[-2:]
    out['trend'] = {k: [round(sum(r[k] for r in head) / 2, 1), round(sum(r[k] for r in tail) / 2, 1)] for k in ['nodes', 'objects', 'mem_mb']}
diag = path + '.diag.json'
if os.path.exists(diag):
    d = json.load(open(diag))
    out['diagnostics'] = {'log_rows': len(d['log']), 'log_total': d['log_total'], 'bytes': os.path.getsize(diag),
                          'frames': d['frames'], 'counters': d['counters'], 'clock': d['clock'], 'objects': d['objects']}
print(json.dumps(out, ensure_ascii=False, indent=1))
