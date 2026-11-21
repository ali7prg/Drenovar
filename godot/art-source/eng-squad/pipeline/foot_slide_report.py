#!/usr/bin/env python3
"""Foot / hoof contact slide and cycle-vs-path speed from qa_eng_squad_capture.gd telemetry.

usage:
  python3 foot_slide_report.py <capture_dir|telemetry.json> [--clip=walk] [--out=report.json]
                               [--tol=0.025] [--trim=0.15] [--min-contact=4] [--units=ENG-01,ENG-06]

Definitions (world coordinates, metres, game scale already applied):
  * clearance  = min over the joints of a foot (Foot+Toe, or Hoof) of (joint.y - terrain.y under it);
  * contact    = frames whose clearance is within --tol of the foot's own low level (5th percentile)
                 and whose vertical joint speed is below 0.25 m/s; runs shorter than --min-contact
                 frames are ignored;
  * planted joint = the joint of the foot that is lowest for most frames of the contact run;
  * stationary part = the contact run with --trim of its frames removed at each end
                 (touch-down and lift-off blends are excluded);
  * slide      = maximum horizontal distance of the planted joint from its position at the start of
                 the stationary part, and its mean horizontal speed;
  * path speed = horizontal speed of the unit origin (finite differences);
  * cycle speed= backward speed of the planted joint relative to the unit origin, projected on the
                 unit's facing (what the clip "walks"), averaged over stationary contact frames.
Proposed acceptance (contract.json -> acceptance): |cycle/path - 1| <= 2 %, slide <= 5 % of leg length.
"""
import json
import math
import os
import sys

HUMAN_FEET = {"LeftFoot": ["LeftFoot", "LeftToe"], "RightFoot": ["RightFoot", "RightToe"]}
HORSE_FEET = {"FrontLHoof": ["FrontLHoof"], "FrontRHoof": ["FrontRHoof"], "HindLHoof": ["HindLHoof"], "HindRHoof": ["HindRHoof"]}


def arg(name, default):
    for a in sys.argv[1:]:
        if a.startswith("--" + name + "="):
            return a.split("=", 1)[1]
    return default


def percentile(values, q):
    v = sorted(values)
    if not v:
        return 0.0
    k = (len(v) - 1) * q
    f = math.floor(k)
    c = min(len(v) - 1, f + 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def hdist(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def leg_length(header, unit_id, mounted):
    rest = header.get("rest_" + unit_id, {})
    scale = header.get("controller", {}).get("scale", 1.15)
    def d(a, b):
        if a in rest and b in rest:
            pa, pb = rest[a], rest[b]
            return math.dist(pa, pb)
        return None
    if mounted:
        parts = [d("FrontLUpper", "FrontLKnee"), d("FrontLKnee", "FrontLHoof")]
        top = rest.get("FrontLUpper", [0, 1.11, 0])[1]
        if None in parts:
            return 1.3 * scale
        return max(sum(parts), top) * scale
    parts = [d("LeftThigh", "LeftShin"), d("LeftShin", "LeftFoot")]
    if None in parts:
        return 0.94 * scale
    return (sum(parts) + rest.get("LeftFoot", [0, 0.095, 0])[1]) * scale


def analyse_unit(header, frames, name, clip_filter, tol, trim, min_contact):
    rows = []
    for f in frames:
        for u in f["units"]:
            if u["name"] == name and u.get("visible", True) and "bones" in u:
                if clip_filter and str(u.get("clip", "")).lower() != clip_filter and str(u.get("animation", "")).lower() != clip_filter:
                    continue
                rows.append((f["t"], u))
    if len(rows) < max(6, min_contact + 2):
        return None
    unit_id = name.rsplit("_", 1)[0]
    mounted = "FrontLHoof" in rows[0][1]["bones"]
    feet = HORSE_FEET if mounted else HUMAN_FEET
    leg = leg_length(header, unit_id, mounted)
    # path speed of the unit origin
    path_speeds = []
    for (t0, a), (t1, b) in zip(rows, rows[1:]):
        if t1 > t0:
            path_speeds.append(hdist(a["origin"], b["origin"]) / (t1 - t0))
    result = {"unit": name, "unit_id": unit_id, "mounted": mounted, "frames": len(rows), "leg_length_m": round(leg, 4),
              "path_speed_mps": round(sum(path_speeds) / len(path_speeds), 4) if path_speeds else 0.0, "feet": {}}
    cycle_samples = []
    slides_all = []      # straight segments
    slides_turn = []     # contacts during a heading change
    path_straight = []
    for foot, joints in feet.items():
        if any(j not in rows[0][1]["bones"] for j in joints):
            continue
        clear = []
        for t, u in rows:
            c = min(u["bones"][j][1] - u["bones"][j][3] for j in joints)
            clear.append(c)
        low = percentile(clear, 0.05)
        vy = [0.0] + [abs(clear[i] - clear[i - 1]) / max(1e-6, rows[i][0] - rows[i - 1][0]) for i in range(1, len(rows))]
        contact = [c <= low + tol and v < 0.25 for c, v in zip(clear, vy)]
        runs = []
        i = 0
        while i < len(contact):
            if contact[i]:
                j = i
                while j + 1 < len(contact) and contact[j + 1]:
                    j += 1
                if j - i + 1 >= min_contact:
                    runs.append((i, j))
                i = j + 1
            else:
                i += 1
        details = []
        for a, b in runs:
            n = b - a + 1
            cut = int(round(n * trim))
            s, e = a + cut, b - cut
            if e - s + 1 < 2:
                continue
            # planted joint = lowest joint in most frames of the stationary part
            votes = {}
            for k in range(s, e + 1):
                u = rows[k][1]
                jl = min(joints, key=lambda jn: u["bones"][jn][1] - u["bones"][jn][3])
                votes[jl] = votes.get(jl, 0) + 1
            planted = max(votes, key=votes.get)
            p0 = rows[s][1]["bones"][planted]
            slide = max(hdist(p0, rows[k][1]["bones"][planted]) for k in range(s, e + 1))
            travel = sum(hdist(rows[k][1]["bones"][planted], rows[k + 1][1]["bones"][planted]) for k in range(s, e))
            dur = rows[e][0] - rows[s][0]
            # turning: unit yaw change during the stationary part (rigid formation rotation in turns)
            yaw_change = abs(math.degrees(math.atan2(math.sin(rows[e][1]["yaw"] - rows[s][1]["yaw"]), math.cos(rows[e][1]["yaw"] - rows[s][1]["yaw"]))))
            seg_path = sum(hdist(rows[k][1]["origin"], rows[k + 1][1]["origin"]) for k in range(s, e)) / dur if dur > 0 else 0.0
            seg_cycle = []
            # cycle speed: planted joint velocity relative to the unit origin, along -facing
            for k in range(s, e):
                ua, ub = rows[k][1], rows[k + 1][1]
                dt = rows[k + 1][0] - rows[k][0]
                if dt <= 0:
                    continue
                ra = [ua["bones"][planted][q] - ua["origin"][q] for q in range(3)]
                rb = [ub["bones"][planted][q] - ub["origin"][q] for q in range(3)]
                yaw = ub["yaw"]
                fwd = (math.sin(yaw), math.cos(yaw))
                v_rel = ((rb[0] - ra[0]) / dt, (rb[2] - ra[2]) / dt)
                seg_cycle.append(-(v_rel[0] * fwd[0] + v_rel[1] * fwd[1]))
            turning = yaw_change >= 2.0
            if not turning:
                cycle_samples.extend(seg_cycle)
                path_straight.append(seg_path)
            cyc = sum(seg_cycle) / len(seg_cycle) if seg_cycle else 0.0
            details.append({"t_start": round(rows[a][0], 4), "t_end": round(rows[b][0], 4), "frames": n,
                            "planted_joint": planted, "slide_m": round(slide, 4), "slide_pct_leg": round(100 * slide / leg, 2),
                            "slide_speed_mps": round(travel / dur, 4) if dur > 0 else 0.0, "turning": turning,
                            "yaw_change_deg": round(yaw_change, 2), "path_speed_mps": round(seg_path, 4), "cycle_speed_mps": round(cyc, 4)})
            (slides_turn if turning else slides_all).append(slide)
        result["feet"][foot] = {"contact_level_m": round(low, 4), "contacts": details}
    if path_straight:
        result["path_speed_straight_mps"] = round(sum(path_straight) / len(path_straight), 4)
    if cycle_samples:
        cyc = sum(cycle_samples) / len(cycle_samples)
        result["cycle_speed_mps"] = round(cyc, 4)
        ref = result.get("path_speed_straight_mps", result["path_speed_mps"])
        if ref > 1e-3:
            result["cycle_vs_path_pct"] = round(100.0 * (cyc / ref - 1.0), 2)
    if slides_turn:
        result["turn_slide_max_m"] = round(max(slides_turn), 4)
        result["turn_contacts"] = len(slides_turn)
    if slides_all:
        result["slide_max_m"] = round(max(slides_all), 4)
        result["slide_median_m"] = round(percentile(slides_all, 0.5), 4)
        result["slide_max_pct_leg"] = round(100 * max(slides_all) / leg, 2)
        result["contacts"] = len(slides_all)
        result["contacts_over_5pct"] = sum(1 for s in slides_all if s > 0.05 * leg)
    return result


def main():
    src = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith("--") else "."
    path = os.path.join(src, "telemetry.json") if os.path.isdir(src) else src
    tele = json.load(open(path))
    header, frames = tele["header"], tele["frames"]
    clip = arg("clip", "walk").lower()
    clip = "" if clip in ("", "any", "all") else clip
    tol = float(arg("tol", "0.025"))
    trim = float(arg("trim", "0.15"))
    min_contact = int(arg("min-contact", "4"))
    wanted = [u for u in arg("units", "").split(",") if u]
    names = []
    for f in frames:
        for u in f["units"]:
            if u["name"] not in names:
                names.append(u["name"])
    report = {"source": path, "map": header.get("map"), "scenario": header.get("scenario"),
              "route": {k: header.get("route", {}).get(k) for k in ("length", "speed", "turn_deg", "metrics")},
              "fps": header.get("time", {}).get("fps"), "clip_filter": clip or "any",
              "acceptance_proposed": {"cycle_vs_path_pct_abs_max": 2.0, "slide_pct_leg_max": 5.0}, "units": []}
    for name in names:
        if wanted and not any(name.startswith(w) for w in wanted):
            continue
        r = analyse_unit(header, frames, name, clip, tol, trim, min_contact)
        if r:
            report["units"].append(r)
    # per unit type summary
    summary = {}
    for r in report["units"]:
        s = summary.setdefault(r["unit_id"], {"members": 0, "slide_max_m": 0.0, "slide_median_m": [], "slide_max_pct_leg": 0.0, "turn_slide_max_m": 0.0,
                                              "cycle_vs_path_pct": [], "path_speed_mps": [], "cycle_speed_mps": []})
        s["members"] += 1
        s["slide_max_m"] = max(s["slide_max_m"], r.get("slide_max_m", 0.0))
        if "slide_median_m" in r:
            s["slide_median_m"].append(r["slide_median_m"])
        s["slide_max_pct_leg"] = max(s["slide_max_pct_leg"], r.get("slide_max_pct_leg", 0.0))
        s["turn_slide_max_m"] = max(s["turn_slide_max_m"], r.get("turn_slide_max_m", 0.0))
        if "cycle_vs_path_pct" in r:
            s["cycle_vs_path_pct"].append(r["cycle_vs_path_pct"])
            s["cycle_speed_mps"].append(r["cycle_speed_mps"])
        s["path_speed_mps"].append(r.get("path_speed_straight_mps", r["path_speed_mps"]))
    for uid, s in summary.items():
        cv = s.pop("cycle_vs_path_pct")
        ps = s.pop("path_speed_mps")
        cs = s.pop("cycle_speed_mps")
        md = s.pop("slide_median_m")
        s["slide_median_m"] = round(sum(md) / len(md), 4) if md else None
        s["cycle_speed_mps_mean"] = round(sum(cs) / len(cs), 4) if cs else None
        s["cycle_vs_path_pct_mean"] = round(sum(cv) / len(cv), 2) if cv else None
        s["path_speed_mps_mean"] = round(sum(ps) / len(ps), 4) if ps else None
        s["pass_speed"] = (abs(s["cycle_vs_path_pct_mean"]) <= 2.0) if cv else None
        s["pass_slide"] = s["slide_max_pct_leg"] <= 5.0
    report["summary"] = summary
    out = arg("out", os.path.join(os.path.dirname(path), "foot_slide.json"))
    json.dump(report, open(out, "w"), indent=1)
    print(f"source {path}  clip={clip or 'any'}  route={report['route'].get('length')} m @ {report['route'].get('speed')} m/s")
    print("straight-line contacts only (|yaw change| < 2 deg); turn contacts reported separately")
    print(f"{'unit':8s} {'n':>2s} {'path m/s':>8s} {'cycle m/s':>9s} {'cyc/path %':>10s} {'slide med m':>11s} {'max m':>6s} {'% leg':>6s} {'turn max m':>10s}  pass(speed,slide)")
    for uid, s in summary.items():
        cv = s["cycle_vs_path_pct_mean"]
        print(f"{uid:8s} {s['members']:2d} {s['path_speed_mps_mean'] or 0:8.3f} {s['cycle_speed_mps_mean'] or 0:9.3f} {cv if cv is not None else float('nan'):10.1f} {s['slide_median_m'] or 0:11.3f} {s['slide_max_m']:6.3f} {s['slide_max_pct_leg']:6.1f} {s['turn_slide_max_m']:10.3f}  {s['pass_speed']},{s['pass_slide']}")
    print("report:", out)


if __name__ == "__main__":
    main()
