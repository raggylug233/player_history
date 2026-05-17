#!/usr/bin/env python3
"""Regenerate data.js from the weekly Power Levels .xlsx snapshot.

Usage:
    python3 build_data.py [INPUT_XLSX] [OUTPUT_JS]

Defaults:
    INPUT_XLSX = "3174 Power Levels.xlsx"
    OUTPUT_JS  = "data.js"

Pipeline:
    1. Load + normalize the xlsx
    2. Fuzzy-group records that likely refer to the same player (rename detection)
    3. Compute SVS prep / non-prep growth rates, qualifying-event bonuses, slacker totals
    4. Sort by latest power, assign ranks, emit `const DATA = [...]` to data.js
"""
import json
import sys
from collections import Counter
from datetime import date
from difflib import SequenceMatcher

import pandas as pd

INPUT_XLSX = sys.argv[1] if len(sys.argv) > 1 else "3174 Power Levels.xlsx"
OUTPUT_JS = sys.argv[2] if len(sys.argv) > 2 else "data.js"

# === LOAD ===
df = pd.read_excel(INPUT_XLSX)
df["Power"] = df["Power"].fillna(0).astype(int)
df["Rank"] = df["Rank"].fillna("")
df["Furnace"] = df["Furnace"].fillna("")
df["Alliance"] = df["Alliance"].fillna("")
df["State"] = df["State"].fillna("").astype(str).str.replace(".0", "", regex=False)
df["Date"] = df["Date"].fillna("").astype(str)
df["Chief Name"] = df["Chief Name"].fillna("").astype(str).str.strip()

# === FUZZY GROUPING ===
names = df["Chief Name"].unique().tolist()


def name_sim(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def power_sim(pa, pb):
    mx = max(pa, pb)
    return min(pa, pb) / mx if mx > 0 else 1.0


# Manual alias overrides for cases the fuzzy matcher misses (e.g., dramatic
# stylistic renames like VICTØR DA VÏNCI → VICTØR SNØW). Maps alias → canonical;
# both names must appear in the source xlsx. Applied after fuzzy grouping, so
# manual entries override veto rules.
MANUAL_ALIASES = {
    "올루 ᴵᵘ": "올루 olu",
}

name_stats = {}
for n in names:
    rows = df[df["Chief Name"] == n]
    name_stats[n] = {
        "power": rows["Power"].mean(),
        "alliance": rows["Alliance"].mode()[0] if len(rows) and rows["Alliance"].any() else "",
        "dates": set(rows["Date"].tolist()),
    }

parent = {n: n for n in names}


def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def union(a, b):
    parent[find(a)] = find(b)


THRESHOLD = 0.82
POWER_VETO = 0.3  # mean-power ratio below this (one < 30% of the other) → never merge

for i, a in enumerate(names):
    sa = name_stats[a]
    for b in names[i + 1:]:
        sb = name_stats[b]

        ns = name_sim(a, b)
        if ns < 0.70:
            continue

        # Same-date veto: if a and b both appear in any snapshot, they must
        # be different players (one person can't be listed twice in one snapshot).
        # This also covers the "same timestamp in different alliances" case.
        if sa["dates"] & sb["dates"]:
            continue

        # Power veto: vastly different mean power can't be the same player even
        # accounting for growth across the dataset's time range.
        ps = power_sim(sa["power"], sb["power"])
        if ps < POWER_VETO:
            continue

        same_alliance = sa["alliance"] == sb["alliance"] and sa["alliance"] != ""
        alliance_score = (
            1.0 if same_alliance else (0.3 if not sa["alliance"] or not sb["alliance"] else 0.0)
        )
        score = ns * 0.5 + ps * 0.3 + alliance_score * 0.2
        if score >= THRESHOLD:
            union(a, b)

# Manual alias overrides — force-union pairs the fuzzy matcher misses.
for alias, canonical in MANUAL_ALIASES.items():
    a_in = alias in parent
    c_in = canonical in parent
    if a_in and c_in:
        union(alias, canonical)
    else:
        missing = [n for n, p in [(alias, a_in), (canonical, c_in)] if not p]
        print(f"WARNING: manual alias {alias!r} → {canonical!r} skipped; not in xlsx: {missing}")

# === BUILD PLAYERS ===
groups = {}
for n in names:
    groups.setdefault(find(n), []).append(n)

players = []
for root, members in groups.items():
    rows = df[df["Chief Name"].isin(set(members))].sort_values("Date")
    records = rows.to_dict(orient="records")
    if not records:
        continue
    canonical = Counter(r["Chief Name"] for r in records).most_common(1)[0][0]
    variants = sorted(set(r["Chief Name"] for r in records))
    players.append(
        {
            "name": canonical,
            "variants": variants if len(variants) > 1 else [],
            "latest": records[-1],
            "records": records,
            "sparkline": [[r["Date"], r["Power"]] for r in records if r["Date"]],
            "count": len(records),
        }
    )

# === SCORE: SVS PREP, EVENT, SLACKER ===
PREP = [
    (date(2026, 1, 26), date(2026, 1, 31)),
    (date(2026, 2, 23), date(2026, 2, 28)),
    (date(2026, 3, 23), date(2026, 3, 28)),
    (date(2026, 4, 20), date(2026, 4, 25)),
    (date(2026, 5, 18), date(2026, 5, 23)),
    (date(2026, 6, 15), date(2026, 6, 20)),
    (date(2026, 7, 13), date(2026, 7, 18)),
    (date(2026, 8, 10), date(2026, 8, 15)),
    (date(2026, 9, 7), date(2026, 9, 12)),
    (date(2026, 10, 5), date(2026, 10, 10)),
    (date(2026, 11, 2), date(2026, 11, 7)),
    (date(2026, 11, 30), date(2026, 12, 5)),
]
EVENTS_ALL = [
    ("Gilded Jade", date(2026, 2, 15), date(2026, 2, 21)),
    ("Dawn Feast", date(2026, 3, 6), date(2026, 3, 12)),
    ("Radiant Melody", date(2026, 4, 1), date(2026, 4, 7)),
]
QUALIFYING = []
for nm, es, ee in EVENTS_ALL:
    for ps, pe in PREP:
        if 0 < (es - pe).days <= 10:
            QUALIFYING.append((nm, es, ee, ps, pe))
            break


def parse(s):
    s = s.replace(".", "-")
    return date(int(s[:4]), int(s[5:7]), int(s[8:10]))


def compute_rate(sparkline, rng_start, rng_end):
    total_growth = 0.0
    total_days = 0
    for i in range(1, len(sparkline)):
        d_prev = parse(sparkline[i - 1][0])
        d_curr = parse(sparkline[i][0])
        gap = (d_curr - d_prev).days
        if gap <= 0:
            continue
        lo = max(d_prev, rng_start)
        hi = min(d_curr, rng_end)
        overlap = (hi - lo).days + 1 if lo <= hi else 0
        if overlap <= 0:
            continue
        growth = sparkline[i][1] - sparkline[i - 1][1]
        total_growth += growth * (overlap / gap)
        total_days += overlap
    return (total_growth / total_days) if total_days > 0 else None


for p in players:
    sparkline = sorted(p["sparkline"], key=lambda s: s[0])
    prep_growth = nonprep_growth = 0.0
    prep_days = nonprep_days = 0
    for i in range(1, len(sparkline)):
        d_prev = parse(sparkline[i - 1][0])
        d_curr = parse(sparkline[i][0])
        days = (d_curr - d_prev).days
        if days <= 0:
            continue
        growth = sparkline[i][1] - sparkline[i - 1][1]
        po = 0
        for ps, pe in PREP:
            lo = max(d_prev, ps)
            hi = min(d_curr, pe)
            if lo <= hi:
                po += (hi - lo).days + 1
        po = min(po, days)
        npo = days - po
        prep_growth += growth * (po / days)
        nonprep_growth += growth * (npo / days)
        prep_days += po
        nonprep_days += npo

    prep_rate = prep_growth / prep_days if prep_days > 0 else None
    nonprep_rate = nonprep_growth / nonprep_days if nonprep_days > 0 else None
    p["prep_rate"] = round(prep_rate, 2) if prep_rate is not None else None
    p["nonprep_rate"] = round(nonprep_rate, 2) if nonprep_rate is not None else None
    p["prep_days"] = prep_days
    p["nonprep_days"] = nonprep_days

    event_bonus = 0.0
    ec = []
    for ename, es, ee, ps, pe in QUALIFYING:
        er = compute_rate(sparkline, es, ee)
        pr = compute_rate(sparkline, ps, pe)
        if er is None or pr is None:
            continue
        diff = er - pr
        ec.append(
            {
                "event": ename,
                "event_start": es.isoformat(),
                "event_end": ee.isoformat(),
                "event_rate": round(er, 2),
                "prep_rate": round(pr, 2),
                "diff": round(diff, 2),
            }
        )
        if diff > 0:
            event_bonus += diff
    p["event_bonus"] = round(event_bonus, 2) if event_bonus > 0 else 0
    p["event_comparisons"] = ec

    # Slacker total: null if player IS engaged (spending power during prep)
    if prep_rate is None or nonprep_rate is None or prep_rate < 0:
        p["slacker_total"] = None
    else:
        p["slacker_total"] = round(nonprep_rate - prep_rate + event_bonus, 2)

players.sort(key=lambda p: p["latest"]["Power"], reverse=True)
for i, p in enumerate(players):
    p["idx"] = i + 1

# === EMIT ===
payload = json.dumps(players, ensure_ascii=False, separators=(",", ":"))
with open(OUTPUT_JS, "w", encoding="utf-8") as f:
    f.write("const DATA = " + payload + ";\n")

print(f"Wrote {OUTPUT_JS}: {len(players)} players from {len(df)} records ({INPUT_XLSX})")
