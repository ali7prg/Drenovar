#!/usr/bin/env python3
"""Per-symptom numbers from a qa_combat_telemetry.gd record (JSON lines).

Symptoms measured (Linux evidence; frame times are not iPhone frame times):
  clock      presentation clock frozen / sped up while real time runs, delay changes
  hidden     army actor hidden while its soldiers would be on screen
  vanish     a living soldier or the creature leaves the drawn set while on screen
  jumps      per-frame displacement above 16 m/s of real or shown time (teleports)
  snaps      per-frame yaw change above 0.6 rad (instant turns)
  strikes    server strikes whose attack clip was on screen from windup to contact
  stalls     frame-time outliers (p50/p95/p99/max and frames > 50/100/250 ms)
Usage: analyze_combat_telemetry.py RECORD.jsonl [--json]
"""
import json, math, sys
from collections import defaultdict, Counter


def pct(values, q):
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, int(math.ceil(q * len(s))) - 1)]


def split(path):
    hunts = []
    for line in open(path):
        r = json.loads(line)
        if 'hunt' in r:
            hunts.append({'head': r, 'frames': [], 'dumps': []})
        elif not hunts:
            continue
        elif 'f' in r:
            hunts[-1]['frames'].append(r)
        elif 'events' in r:
            hunts[-1]['dumps'].append(r)
    return hunts


def strike_report(frames, dumps):
    """Server strikes vs strikes drawn, and how late each strike reached the client."""
    if not dumps:
        return {}
    final = dumps[-1]
    if final.get('battleAt') is None:
        return {}  # no fight (a recalled march)
    battle_at = float(final['battleAt'])
    soldier = [e for e in final['events'] if e[1] == 'soldier_attack']
    creature = [e for e in final['events'] if e[1] != 'soldier_attack']
    ft_of = {f['f']: f['ft'] for f in frames}
    first_known = {}
    for d in dumps:
        for e in d['events']:
            k = (round(float(e[0])), e[1], e[2], int(e[3]))
            first_known.setdefault(k, ft_of.get(d['frame']))
    late = []
    for e in final['events']:
        k = (round(float(e[0])), e[1], e[2], int(e[3]))
        known = first_known.get(k)
        if known is None:
            continue
        prepare = 760.0 if e[2] in ('ENG-03', 'ENG-04', 'ENG-10') else 640.0
        late.append(known - (battle_at + float(e[0]) - prepare))
    shown = defaultdict(set)
    for f in frames:
        if f['actor'] != 'shown':
            continue
        for u in f.get('units', []):
            s = u.get('strike')
            if u['clip'] == 'attack' and isinstance(s, (int, float)) and s > -1e300 and u['vis'] and u.get('scr') in ('in', 'part'):
                shown[u['n'].split('_')[0]].add((u['n'], s))
    server_by_type = Counter(e[2] for e in soldier)
    return {'server_soldier_strikes': len(soldier), 'server_creature_strikes': len(creature),
            'server_by_type': dict(server_by_type), 'shown_on_screen_by_type': {k: len(v) for k, v in shown.items()},
            'shown_total': sum(len(v) for v in shown.values()),
            'stretched_k': final.get('stretched'), 'delay_ms': final.get('delay'),
            'arrival_vs_windup_ms': {'p50': pct(late, .5), 'p95': pct(late, .95), 'max': max(late) if late else None,
                                     'late_share': round(sum(x > 0 for x in late) / max(1, len(late)), 3)}}


def analyze_all(path):
    return [dict(analyze(h['head'], h['frames']), strike_vs_server=strike_report(h['frames'], h['dumps'])) for h in split(path)]


def analyze(head, frames):
    out = {'species': head.get('species'), 'level': head.get('level'), 'frames': len(frames)}
    # --- frame time
    dts = [f['dt'] for f in frames[1:]]
    out['frame_ms'] = {'p50': pct(dts, .5), 'p95': pct(dts, .95), 'p99': pct(dts, .99), 'max': max(dts) if dts else None,
                       'over50': sum(d > 50 for d in dts), 'over100': sum(d > 100 for d in dts), 'over250': sum(d > 250 for d in dts)}
    by_phase = defaultdict(list)
    for f in frames[1:]:
        by_phase[f['phase']].append(f['dt'])
    out['frame_ms_by_phase'] = {k: {'p50': pct(v, .5), 'p95': pct(v, .95), 'max': max(v)} for k, v in by_phase.items()}
    # --- presentation clock
    frozen_ms, fast_ms, delays = 0.0, 0.0, []
    frozen_runs, run = [], 0.0
    for a, b in zip(frames, frames[1:]):
        real = (b['t'] - a['t']) / 1000.0
        shown = b['ft'] - a['ft']
        if b['delay'] != a['delay']:
            delays.append({'frame': b['f'], 'phase': b['phase'], 'from': a['delay'], 'to': b['delay']})
        if real > 0 and shown <= 0.01 and b['phase'] in ('march', 'fight', 'return'):
            frozen_ms += real; run += real
        else:
            if run > 0: frozen_runs.append(round(run))
            run = 0.0
        if real > 0 and shown > real * 1.3 + 1:
            fast_ms += real
    if run > 0: frozen_runs.append(round(run))
    out['clock'] = {'frozen_ms': round(frozen_ms), 'frozen_runs_ms': sorted(frozen_runs, reverse=True)[:8],
                    'sped_up_ms': round(fast_ms), 'delay_changes': delays[:12], 'delay_change_count': len(delays)}
    # --- army actor hidden while some soldier was on screen in the previous shown frame
    hidden_frames, hidden_on_screen = 0, 0
    last_units = None
    for f in frames:
        if f['actor'] == 'shown':
            last_units = f.get('units', [])
        elif f['actor'] == 'hidden' and f['phase'] in ('march', 'fight', 'return'):
            hidden_frames += 1
            if last_units and any(u.get('scr') in ('in', 'part') for u in last_units):
                hidden_on_screen += 1
    out['army_hidden'] = {'frames': hidden_frames, 'frames_after_on_screen': hidden_on_screen}
    # --- per-soldier tracks
    tracks = defaultdict(list)
    for f in frames:
        for u in f.get('units', []) if f['actor'] == 'shown' else []:
            tracks[u['n']].append((f, u))
    vanish, jumps, snaps = [], [], []
    for name, tr in tracks.items():
        for (fa, a), (fb, b) in zip(tr, tr[1:]):
            gap = fb['f'] - fa['f']
            real = max(1e-3, (fb['t'] - fa['t']) / 1e6)
            shown = max(0.0, (fb['ft'] - fa['ft']) / 1000.0)
            d = math.dist(a['pos'], b['pos'])
            # Faster than a galloping rider (16 m/s) over the real or the shown time
            # of the frame, and more than 1.2 m: a teleport, not movement.
            if gap == 1 and d > max(1.2, 16.0 * max(real, shown)) and a['clip'] != 'death' and b['clip'] != 'death':
                jumps.append({'unit': name, 'frame': fb['f'], 'phase': fb['phase'], 'metres': round(d, 2), 'dt_ms': round(real * 1000, 1),
                              'clip': [a['clip'], b['clip']]})
            dy = abs((b['yaw'] - a['yaw'] + math.pi) % (2 * math.pi) - math.pi)
            if gap == 1 and dy > 0.6 and b['clip'] != 'death':
                snaps.append({'unit': name, 'frame': fb['f'], 'phase': fb['phase'], 'rad': round(dy, 2), 'clip': [a['clip'], b['clip']]})
    # vanish: present in frame n (visible, on screen, not dead) and absent / invisible in n+1 while the actor stays shown
    for fa, fb in zip(frames, frames[1:]):
        if fa['actor'] != 'shown':
            continue
        nb = {u['n']: u for u in fb.get('units', [])} if fb['actor'] == 'shown' else {}
        for u in fa.get('units', []):
            if not u['vis'] or u.get('scr') not in ('in', 'part') or u['clip'] == 'death':
                continue
            if u['n'] in fb.get('fallen', []):
                continue
            v = nb.get(u['n'])
            if v is None or not v['vis']:
                vanish.append({'unit': u['n'], 'frame': fb['f'], 'phase': fb['phase'],
                               'why': 'actor_hidden' if fb['actor'] != 'shown' else ('freed' if v is None else 'invisible'),
                               'anchor_in_frustum': fb.get('anchor_in'), 'clip': u['clip']})
    # Too fast: displacement over >= 150 ms of shown time above 16 m/s (a slide
    # or run no soldier or horse can make, even when every frame is short).
    fast = []
    for name, tr in tracks.items():
        j = 0
        for i in range(len(tr)):
            fi, ui = tr[i]
            while j < i and fi['ft'] - tr[j][0]['ft'] > 300.0:
                j += 1
            fj, uj = tr[j]
            span = (fi['ft'] - fj['ft']) / 1000.0
            if span >= 0.15 and fi['f'] - fj['f'] == i - j and 'death' not in (ui['clip'], uj['clip']):
                v = math.dist(ui['pos'], uj['pos']) / span
                if v > 16.0:
                    fast.append({'unit': name, 'frame': fi['f'], 'phase': fi['phase'], 'mps': round(v, 1), 'clip': ui['clip']})
    out['too_fast'] = {'count': len(fast), 'by_phase': Counter(f['phase'] for f in fast), 'worst': sorted(fast, key=lambda f: -f['mps'])[:5]}
    out['vanish'] = {'count': len(vanish), 'by_reason': Counter(v['why'] for v in vanish), 'by_phase': Counter(v['phase'] for v in vanish), 'first': vanish[:10]}
    out['jumps'] = {'count': len(jumps), 'by_phase': Counter(j['phase'] for j in jumps), 'worst': sorted(jumps, key=lambda j: -j['metres'])[:10]}
    out['snaps'] = {'count': len(snaps), 'by_phase': Counter(s['phase'] for s in snaps), 'first': snaps[:8]}
    # --- strikes: every distinct (unit, strike) shown; was the attack clip on screen and progressing?
    strikes = {}
    for name, tr in tracks.items():
        for f, u in tr:
            s = u.get('strike')
            if u['clip'] != 'attack' or s is None or (isinstance(s, (int, float)) and s < -1e300):
                continue
            k = (name, s)
            e = strikes.setdefault(k, {'frames': 0, 'on_screen': 0, 'anim': set(), 'ap': []})
            e['frames'] += 1
            e['on_screen'] += u.get('scr') in ('in', 'part') and u['vis']
            e['anim'].add(u.get('anim', ''))
            e['ap'].append(u.get('ap', 0))
    seen_ok = 0
    for e in strikes.values():
        prog = max(e['ap']) - min(e['ap']) if e['ap'] else 0
        e['progress_s'] = round(prog, 3)
        if e['on_screen'] >= 6 and prog >= 0.3 and any('attack' in a for a in e['anim']):
            seen_ok += 1
    out['strikes'] = {'distinct_shown': len(strikes), 'visible_with_progress': seen_ok,
                      'frames_median': pct([e['frames'] for e in strikes.values()], .5)}
    # --- creature
    clips, beast_vanish, beast_jumps = Counter(), 0, []
    prev = None
    for f in frames:
        b = f.get('beast')
        if b:
            clips[b['clip']] += 1
        if prev and prev['beast'] and prev['beast']['vis'] and prev['beast']['scr'] in ('in', 'part') and (not b or not b['vis']) and f['phase'] in ('march', 'fight'):
            beast_vanish += 1
        if prev and prev.get('beast') and b and f['f'] == prev['f'] + 1:
            d = math.dist(prev['beast']['pos'], b['pos'])
            if d > 1.2:
                beast_jumps.append({'frame': f['f'], 'metres': round(d, 2), 'phase': f['phase']})
        prev = f
    out['creature'] = {'clip_frames': clips, 'vanish_on_screen': beast_vanish, 'jumps': beast_jumps[:8]}
    # --- growth
    out['growth'] = {'nodes': [frames[0]['nodes'], frames[-1]['nodes']], 'objects': [frames[0]['objects'], frames[-1]['objects']],
                     'mem_mb': [frames[0]['mem'], frames[-1]['mem']], 'fx_children_max': max(f['fx_children'] for f in frames)}
    return out


if __name__ == '__main__':
    result = analyze_all(sys.argv[1])
    print(json.dumps(result, indent=1, default=lambda o: sorted(o) if isinstance(o, set) else str(o), ensure_ascii=False))
