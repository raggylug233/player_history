# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project overview

This is the **State 3174 Power Levels** dashboard for the mobile game **Whiteout Survival (WOS)**. It’s a single-file HTML application that visualizes alliance member power tracking data across weekly snapshots, with analytics to identify SVS (State vs. State) engagement and “slacker” behavior.

The dashboard is used by Steve (alliance leader of **BBL** in State 3174) for competitive analysis across the alliances tracked in S3174: **AAG, ACH, B2A, BBL, DGS, HAR, LIL, LTU, ONE, VLS, XYZ**.

## Architecture

### Single-file HTML deliverable

The entire app is a single self-contained HTML file (`index.html` / `power_levels_3174.html`). No build step, no external JS dependencies beyond Google Fonts. Data is embedded directly as a JavaScript constant.

```
<source data .xlsx>
        │
        │  Python build script (one-time, before HTML edit)
        ▼
<grouped JSON with fuzzy-matched players, scores, sparklines>
        │
        │  Embedded as `const DATA = [...]` in HTML
        ▼
<index.html — fully self-contained, no server needed>
```

### Data flow inside the page

1. `const DATA` — array of player objects (one per fuzzy-grouped player)
1. `applyFilters()` filters → sorts → calls `renderCards()`
1. `renderCards()` paginates → renders one card per player in the visible window
1. Each card has two independent expandable regions:
- **Detail table** (toggled by clicking the card header) — historical records
- **Detail chart** (toggled by clicking the sparkline) — full-size chart

### Player data shape

Each player object:

```js
{
  idx: 1,                          // 1-indexed rank by latest power
  name: "canonical name",          // most-frequent name in the group
  variants: ["aka1", "aka2"],      // empty array if no fuzzy merges
  count: 12,                       // number of records
  latest: { /* the most recent record */ },
  records: [ /* all records, sorted ascending by date */ ],
  sparkline: [ [date, power], ... ],

  // SVS analytics
  prep_rate: 0.14,                 // M/day, average during all SVS prep windows
  nonprep_rate: 0.88,              // M/day, average outside prep windows
  prep_days: 24,
  nonprep_days: 55,

  // Event banking analytics
  event_bonus: 2.66,               // sum of positive (event_rate - prep_rate) per qualifying event
  event_comparisons: [
    { event, event_start, event_end, event_rate, prep_rate, diff }
  ],

  // Slacker score (null if excluded)
  slacker_total: 3.40              // (nonprep_rate - prep_rate) + event_bonus, or null
}
```

## Conventions and rules

### Data conventions (Steve’s preferences)

- **Power values**: full integers, NOT abbreviated with “M” suffix in raw data
- **Ranks**: `R1`–`R5`
- **Furnace**: lowercase `fc##` (FC tier) or `f##` (regular furnace)
- **Dates**: `YYYY.MM.DD` format (dot-separated)
- **Player names**: preserve exact non-Latin characters, emojis, special Unicode — never normalize for display
- **Alliance colors**: each alliance has a fixed color (see `ALLIANCE_COLORS` constant in the HTML). When adding new alliances, give them distinct neon-palette colors.

### UI aesthetic

Dark/sci-fi/neon gamer aesthetic. **Maintain this consistency** across additions:

- **Background**: near-black `#050810` with a subtle scanline overlay and grid
- **Panels**: `#0f1b2d` with `#1a3050` borders
- **Accent**: cyan `#00c8ff` (primary), orange `#ff6b35` (SVS), purple `#a78bfa` (events), green `#39ff14` (growth), red `#ff4444` (loss)
- **Fonts** (Google Fonts):
  - `Rajdhani` — headings, button labels, large numbers
  - `Share Tech Mono` — small uppercase labels, dates, monospaced data
  - `Exo 2` — body text
- **Effects**: scanlines, subtle grid, glow on focused inputs, no shadows

### Mobile (≤640px)

The page detects mobile via `window.innerWidth <= 640` and adapts:

- Header stats are hidden
- Pagination becomes sticky at the bottom
- Page size defaults to 20 (vs 50 on desktop)
- Inputs use 16px font size to prevent iOS auto-zoom
- Cards stay readable; sparkline width shrinks to 60px

## Domain knowledge

### SVS (State vs. State)

A monthly competitive event. Each cycle has:

- A **prep window** (5 days, ending Saturday of SVS) where alliances prepare
- The **SVS battle** itself the following week

During prep, engaged players SPEND power on troops/research/buildings (so their snapshot power often goes DOWN — this is good behavior). After prep, they rebuild.

### SVS prep windows (fixed schedule)

Hardcoded in the HTML as `SVS_PREP`:

```
2026-01-26 to 2026-01-31    2026-07-13 to 2026-07-18
2026-02-23 to 2026-02-28    2026-08-10 to 2026-08-15
2026-03-23 to 2026-03-28    2026-09-07 to 2026-09-12
2026-04-20 to 2026-04-25    2026-10-05 to 2026-10-10
2026-05-18 to 2026-05-23    2026-11-02 to 2026-11-07
2026-06-15 to 2026-06-20    2026-11-30 to 2026-12-05
```

### In-game events (with rewards for power-related actions)

Hardcoded in the HTML as `EVENTS`:

```
Gilded Jade:    2026-02-15 to 2026-02-21
Dawn Feast:     2026-03-06 to 2026-03-12
Radiant Melody: 2026-04-01 to 2026-04-07
```

An event “qualifies” for the banking penalty if it **starts within 10 days after a prep window ends**. Currently Dawn Feast and Radiant Melody qualify. Gilded Jade (15 days after the Jan prep) does not.

### Slacker scoring

A “slacker” is a player who avoids spending power during SVS prep and saves it for in-game events instead — they’re getting alliance benefits without paying the SVS cost.

**Slacker score = `(nonprep_rate − prep_rate) + event_bonus`** in power/day units.

**Exclusion rule**: If `prep_rate < 0`, the player is engaged (spending during prep) and is **excluded entirely from slacker flag** — their `slacker_total` is `null`. They get no badge, don’t appear in the SLACKERS ONLY filter, and don’t show in the Slacker score sort. This rule was added because players who actively burn power for SVS shouldn’t be penalized, even if they grow during non-prep weeks.

**Event bonus**: For each qualifying event, if `event_rate > prep_rate` (player grew faster during the event week than during the preceding prep), the positive difference is added to `event_bonus`. Sums across all qualifying events.

**Threshold**: A player is flagged as a slacker if `slacker_total > 500_000` power/day. The badge displays as `💤 SLACKER +X.XXM/d` with a `🎁` suffix when `event_bonus > 500_000`.

### Fuzzy player grouping

Players occasionally rename themselves in-game. The data pipeline groups records that likely refer to the same player using three signals:

```
combined_score = 0.5 × name_similarity      // difflib SequenceMatcher
              + 0.3 × power_similarity     // min/max of mean power
              + 0.2 × alliance_match       // 1.0 same, 0.3 blank, 0.0 different
```

Names merge if `combined_score >= 0.82` AND `name_similarity >= 0.70` (quick filter).

**Hard veto**: Two names that appear on the **same snapshot date** are never merged — they must be different players. This prevents false positives like `Lord R` and `LordRawl` (similar names, same alliance, but both appeared in Feb 8 snapshot so they can’t be the same person).

**Known limitations** (`difflib.SequenceMatcher` at 0.80 threshold): misses stylistically dramatic name changes like `VICTØR DA VÏNCI` → `VICTØR SNØW`. Solution path when adding more data is a `manual_aliases` dict plus explicit deletion of bad fuzzy links.

### Sparkline x-axis

All sparklines use a **fixed global 3-month rolling window** ending at the latest snapshot date in the dataset. This means:

- Bands for SVS prep and events land at the same x-position on every card
- Players with fewer records have their dots clustered at the actual time positions, not stretched to fill the chart
- Comparison across players is visually consistent

### Post-SVS snapshot marker

Snapshots taken **on or after** an SVS prep end date get the ⚔️ marker in the detail table. The rule is `>=` (not strict `>`) because a snapshot dated 2026.04.25 represents the state at the end of the Apr 20–25 prep window. The orange left border on the row and the emoji indicate “this is the first snapshot at/after SVS prep ended.”

## Build process

### Refreshing data from a new .xlsx

When Steve uploads a new weekly snapshot, the data pipeline must run before the HTML can be updated. A reference Python script is included below — copy and run, then swap the resulting JSON into the HTML.

```python
import pandas as pd, json
from difflib import SequenceMatcher
from collections import Counter
from datetime import date

# === LOAD ===
df = pd.read_excel('path/to/3174_Power_Levels.xlsx')
df['Power'] = df['Power'].fillna(0).astype(int)
df['Rank'] = df['Rank'].fillna('')
df['Furnace'] = df['Furnace'].fillna('')
df['Alliance'] = df['Alliance'].fillna('')
df['State'] = df['State'].fillna('').astype(str).str.replace('.0','',regex=False)
df['Date'] = df['Date'].fillna('').astype(str)
df['Chief Name'] = df['Chief Name'].fillna('').astype(str).str.strip()

# === FUZZY GROUPING ===
names = df['Chief Name'].unique().tolist()
def name_sim(a, b): return SequenceMatcher(None, a.lower(), b.lower()).ratio()
def power_sim(pa, pb):
    mx = max(pa, pb); return min(pa, pb) / mx if mx > 0 else 1.0

name_stats = {}
for n in names:
    rows = df[df['Chief Name'] == n]
    name_stats[n] = {
        'power': rows['Power'].mean(),
        'alliance': rows['Alliance'].mode()[0] if len(rows) and rows['Alliance'].any() else '',
        'dates': set(rows['Date'].tolist())
    }

parent = {n: n for n in names}
def find(x):
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x
def union(a, b): parent[find(a)] = find(b)

THRESHOLD = 0.82
for i, a in enumerate(names):
    sa = name_stats[a]
    for b in names[i+1:]:
        sb = name_stats[b]
        ns = name_sim(a, b)
        if ns < 0.70: continue
        if sa['dates'] & sb['dates']: continue  # same-date veto
        ps = power_sim(sa['power'], sb['power'])
        same_alliance = (sa['alliance'] == sb['alliance'] and sa['alliance'] != '')
        alliance_score = 1.0 if same_alliance else (0.3 if not sa['alliance'] or not sb['alliance'] else 0.0)
        score = ns * 0.5 + ps * 0.3 + alliance_score * 0.2
        if score >= THRESHOLD:
            union(a, b)

# === BUILD PLAYERS ===
groups = {}
for n in names:
    groups.setdefault(find(n), []).append(n)

players = []
for root, members in groups.items():
    rows = df[df['Chief Name'].isin(set(members))].sort_values('Date')
    records = rows.to_dict(orient='records')
    if not records: continue
    canonical = Counter(r['Chief Name'] for r in records).most_common(1)[0][0]
    variants = sorted(set(r['Chief Name'] for r in records))
    players.append({
        'name': canonical,
        'variants': variants if len(variants) > 1 else [],
        'latest': records[-1],
        'records': records,
        'sparkline': [[r['Date'], r['Power']] for r in records if r['Date']],
        'count': len(records)
    })

# === SCORE: SVS PREP, EVENT, SLACKER ===
PREP = [
  (date(2026,1,26), date(2026,1,31)), (date(2026,2,23), date(2026,2,28)),
  (date(2026,3,23), date(2026,3,28)), (date(2026,4,20), date(2026,4,25)),
  (date(2026,5,18), date(2026,5,23)), (date(2026,6,15), date(2026,6,20)),
  (date(2026,7,13), date(2026,7,18)), (date(2026,8,10), date(2026,8,15)),
  (date(2026,9,7),  date(2026,9,12)), (date(2026,10,5), date(2026,10,10)),
  (date(2026,11,2), date(2026,11,7)), (date(2026,11,30),date(2026,12,5)),
]
EVENTS_ALL = [
  ('Gilded Jade',    date(2026,2,15), date(2026,2,21)),
  ('Dawn Feast',     date(2026,3,6),  date(2026,3,12)),
  ('Radiant Melody', date(2026,4,1),  date(2026,4,7)),
]
QUALIFYING = []
for nm, es, ee in EVENTS_ALL:
    for ps, pe in PREP:
        if 0 < (es - pe).days <= 10:
            QUALIFYING.append((nm, es, ee, ps, pe))
            break

def parse(s):
    s = s.replace('.','-')
    return date(int(s[:4]), int(s[5:7]), int(s[8:10]))

def compute_rate(sparkline, rng_start, rng_end):
    total_growth = 0.0; total_days = 0
    for i in range(1, len(sparkline)):
        d_prev = parse(sparkline[i-1][0]); d_curr = parse(sparkline[i][0])
        gap = (d_curr - d_prev).days
        if gap <= 0: continue
        lo = max(d_prev, rng_start); hi = min(d_curr, rng_end)
        overlap = (hi - lo).days + 1 if lo <= hi else 0
        if overlap <= 0: continue
        growth = sparkline[i][1] - sparkline[i-1][1]
        total_growth += growth * (overlap / gap)
        total_days += overlap
    return (total_growth / total_days) if total_days > 0 else None

for p in players:
    sparkline = sorted(p['sparkline'], key=lambda s: s[0])
    prep_growth = nonprep_growth = 0.0; prep_days = nonprep_days = 0
    for i in range(1, len(sparkline)):
        d_prev = parse(sparkline[i-1][0]); d_curr = parse(sparkline[i][0])
        days = (d_curr - d_prev).days
        if days <= 0: continue
        growth = sparkline[i][1] - sparkline[i-1][1]
        po = 0
        for ps, pe in PREP:
            lo = max(d_prev, ps); hi = min(d_curr, pe)
            if lo <= hi: po += (hi - lo).days + 1
        po = min(po, days); npo = days - po
        prep_growth += growth * (po/days); nonprep_growth += growth * (npo/days)
        prep_days += po; nonprep_days += npo

    prep_rate = prep_growth / prep_days if prep_days > 0 else None
    nonprep_rate = nonprep_growth / nonprep_days if nonprep_days > 0 else None
    p['prep_rate'] = round(prep_rate, 2) if prep_rate is not None else None
    p['nonprep_rate'] = round(nonprep_rate, 2) if nonprep_rate is not None else None
    p['prep_days'] = prep_days; p['nonprep_days'] = nonprep_days

    event_bonus = 0.0; ec = []
    for ename, es, ee, ps, pe in QUALIFYING:
        er = compute_rate(sparkline, es, ee); pr = compute_rate(sparkline, ps, pe)
        if er is None or pr is None: continue
        diff = er - pr
        ec.append({'event': ename, 'event_start': es.isoformat(), 'event_end': ee.isoformat(),
                   'event_rate': round(er, 2), 'prep_rate': round(pr, 2), 'diff': round(diff, 2)})
        if diff > 0: event_bonus += diff
    p['event_bonus'] = round(event_bonus, 2) if event_bonus > 0 else 0
    p['event_comparisons'] = ec

    # Slacker total — null if prep_rate is negative (player IS engaged)
    if prep_rate is None or nonprep_rate is None or prep_rate < 0:
        p['slacker_total'] = None
    else:
        p['slacker_total'] = round(nonprep_rate - prep_rate + event_bonus, 2)

players.sort(key=lambda p: p['latest']['Power'], reverse=True)
for i, p in enumerate(players): p['idx'] = i + 1

# === EMIT ===
with open('data.json', 'w', encoding='utf-8') as f:
    json.dump(players, f, ensure_ascii=False, separators=(',',':'))
```

After running this, the resulting JSON replaces the value of `const DATA = ...` in the HTML between the markers:

```
const DATA = <PASTE HERE>;

const ALLIANCE_COLORS = { ... };
```

## When making changes

1. **Read the relevant code section first** — there’s only one file but it’s ~1300 lines
1. **Preserve the existing aesthetic** — match font choices, spacing, color tokens, and the scanline/grid feel
1. **Mobile parity** — every new feature must work on mobile screens ≤640px wide
1. **Steve is authoritative on WOS mechanics** — defer to him on game-specific details (skill manual costs, refinement mechanics, furnace notation, alliance rosters). Claude’s training data on WOS has been wrong in the past.
1. **Communication style** — Steve prefers terse, command-style instructions and expects Claude to infer intent without lengthy clarification. Output clean code blocks, no commentary unless asked.

## File layout

```
.
├── CLAUDE.md                 # This file
├── index.html                # The single-file dashboard
├── power_levels_3174.html    # Mirror of index.html (legacy filename)
├── power_levels_3174_v2.html # Mirror (cache-buster filename)
└── data/
    └── 3174_Power_Levels.xlsx  # Source data (weekly snapshots)
```

The three `.html` files are byte-identical mirrors. If updating, update all three so cached shared links continue to serve the latest version.