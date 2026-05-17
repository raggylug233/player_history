# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project overview

This is the **State 3174 Power Levels** dashboard for the mobile game **Whiteout Survival (WOS)**. It’s a single-file HTML application that visualizes alliance member power tracking data across weekly snapshots, with analytics to identify SVS (State vs. State) engagement and “slacker” behavior.

The dashboard is used by Steve (alliance leader of **BBL** in State 3174) for competitive analysis across the alliances tracked in S3174: **AAG, ACH, B2A, BBL, DGS, HAR, LIL, LTU, ONE, VLS, XYZ**.

## Architecture

### Single-file HTML deliverable

The app is a single HTML file (`index.html`) that loads its data from a sibling `data.js` (which defines `const DATA = [...]`). No build step, no external JS dependencies beyond Google Fonts.

```
3174 Power Levels.xlsx
        │
        │  python3 build_data.py
        ▼
data.js  (const DATA = [...] — fuzzy-grouped players, scores, sparklines)
        │
        │  loaded via <script src="data.js">
        ▼
index.html  (the dashboard, opens directly from disk)
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

When Steve uploads a new weekly snapshot, run the build script to regenerate `data.js`:

```bash
python3 build_data.py
```

This reads `3174 Power Levels.xlsx` and writes `data.js` (`const DATA = [...]`). The script handles loading, fuzzy player grouping, SVS prep/non-prep rate computation, qualifying-event bonuses, slacker scoring, and ranking — see `build_data.py` for the implementation. Pass `python3 build_data.py INPUT.xlsx OUTPUT.js` to override the defaults.

Dependencies: `pandas`, `openpyxl` (`pip install pandas openpyxl`).

## When making changes

1. **Read the relevant code section first** — there’s only one file but it’s ~1300 lines
1. **Preserve the existing aesthetic** — match font choices, spacing, color tokens, and the scanline/grid feel
1. **Mobile parity** — every new feature must work on mobile screens ≤640px wide
1. **Steve is authoritative on WOS mechanics** — defer to him on game-specific details (skill manual costs, refinement mechanics, furnace notation, alliance rosters). Claude’s training data on WOS has been wrong in the past.
1. **Communication style** — Steve prefers terse, command-style instructions and expects Claude to infer intent without lengthy clarification. Output clean code blocks, no commentary unless asked.

## File layout

```
.
├── CLAUDE.md                  # This file
├── index.html                 # The dashboard
├── data.js                    # `const DATA = [...]` loaded by index.html
├── build_data.py              # Regenerates data.js from the xlsx
└── 3174 Power Levels.xlsx     # Source data (weekly snapshots)
```