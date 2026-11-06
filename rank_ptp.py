#!/usr/bin/env python3

"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate


PTP season-end rating analysis (doubles).

Inputs:
  ratings_file  CSV: player,rating   (rating = each player's minimum/self-rating floor)
  matches_file  CSV with columns: match_date, status, partner1, partner2,
                opponent1, opponent2, team1_points, team2_points

Usage:
  ./rank_ptp.py ratings.csv matches.csv
  ./rank_ptp.py ratings.csv matches.csv -o season.csv
  ./rank_ptp.py ratings.csv matches.csv --verbose > match_log.txt


Every match, in date order:
  1. Expectation: team rating = average of the partners' CURRENT ratings. The gap
     between teams gives tossup / slight favorite / heavy favorite.
  2. Result: point margin gives narrow / solid / blowout.
  3. Adjustment: looked up from the 15-category table, applied to all four players,
     plus a small bonus to the winners (and a matching penalty to the losers).
 
Favorites' adjustments are signed: winning by less than expected costs the favorite
rating, a blowout gains it, and the underdog gets the mirror image.
 
Outputs:
  * season ratings CSV (-o): start/final rating, change, change vs. the field,
    games, wins, and an outperformer/underperformer flag.
  * a backtest summary: how often the higher-rated team won, by expectation.
"""
 
import argparse
import csv
import statistics
import sys
from collections import defaultdict
from datetime import datetime
 
# --------------------------------------------------------------------------
# CONFIG
# --------------------------------------------------------------------------
BASE_RATING_DELTA = 0.0036   # scales every RATING_CHANGE multiplier (was 0.0030; raised 20%
                             # so ratings move a bit more per game - see notes)
DEFAULT_RATING = 3.5         # for players missing from the ratings file
 
WINNING_BONUS = 0.0055       # added to each winner
LOSING_PENALTY = 0.0055      # subtracted from each loser (equal = zero-sum)
 
TOSSUP_THRESHOLD = 0.1       # team rating gap below this = tossup
SLIGHT_THRESHOLD = 0.2       # below this = slight favorite, otherwise heavy
 
BLOWOUT_MARGIN = 12          # point margin >= this = blowout
NARROW_MARGIN = 3            # point margin < this = narrow, otherwise solid

FLAG_DELTA = 0.25           # |change vs. field median| >= this gets flagged

DATE_FORMATS = ["%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y", "%d/%m/%Y", "%Y/%m/%d", "%m-%d-%Y"]

# Multipliers (x BASE_RATING_DELTA, then split per player).
# Keys: (winner relative to expectation, favoredness level, margin).
#   tossup:   value is the winners' gain (losers lose the same)
#   favored:  value is the FAVORITE's change (signed); the underdog gets the negative
#   underdog: value is the underdog's gain; the favorite loses the same
RATING_CHANGE = {
    # Tossup
    ("tossup", None, "narrow"): 12,
    ("tossup", None, "solid"): 15,
    ("tossup", None, "blowout"): 18,
 
    # Underdog wins
    ("underdog", "heavy", "narrow"): 25,
    ("underdog", "heavy", "solid"): 30,
    ("underdog", "heavy", "blowout"): 35,
    ("underdog", "slight", "narrow"): 18,
    ("underdog", "slight", "solid"): 22,
    ("underdog", "slight", "blowout"): 26,
 
    # Favorite wins (signed: narrow win = underperformed, blowout = outperformed)
    ("favored", "slight", "narrow"): -4.5,
    ("favored", "slight", "solid"): 3.5,
    ("favored", "slight", "blowout"): 9.5,
    ("favored", "heavy", "narrow"): -6.5,
    ("favored", "heavy", "solid"): 1.5,
    ("favored", "heavy", "blowout"): 6.5,
}
# --------------------------------------------------------------------------
 
PLAYER_FIELDS_T1 = ("partner1", "partner2")
PLAYER_FIELDS_T2 = ("opponent1", "opponent2")
 
 
def load_ratings(filename):
    ratings = {}
    with open(filename, newline="", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        next(reader, None)  # header
        for row in reader:
            if len(row) < 2 or not row[0].strip():
                continue
            try:
                ratings[row[0].strip()] = float(row[1])
            except ValueError:
                print(f"warning: bad rating row skipped: {row}", file=sys.stderr)
    return ratings
 
 
def parse_match_date(s):
    s = s.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"unparseable date '{s}'")
 
 
def load_matches_sorted(path):
    rows, bad_dates = [], 0
    with open(path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        reader.fieldnames = [h.strip() for h in (reader.fieldnames or [])]
        required = {"match_date", "status", *PLAYER_FIELDS_T1, *PLAYER_FIELDS_T2,
                    "team1_points", "team2_points"}
        missing = required - set(reader.fieldnames)
        if missing:
            raise KeyError(f"matches CSV is missing columns {sorted(missing)}; "
                           f"found {reader.fieldnames}")
        for i, row in enumerate(reader):
            if (row["match_date"] or "").strip() == "match_date":
                continue  # repeated header from concatenated files
            try:
                row["_date"] = parse_match_date(row["match_date"])
            except ValueError as e:
                bad_dates += 1
                if bad_dates <= 5:
                    print(f"warning: {e}; match skipped", file=sys.stderr)
                continue
            row["_idx"] = i
            rows.append(row)
    if bad_dates:
        print(f"warning: {bad_dates} matches skipped for bad dates", file=sys.stderr)
    rows.sort(key=lambda r: (r["_date"], r["_idx"]))  # file order breaks same-day ties
    return rows
 
 
def skip_reason(row):
    status = (row.get("status") or "").strip().lower()
    if status != "completed":
        return f"status={status or 'blank'}"
    for fld in PLAYER_FIELDS_T1 + PLAYER_FIELDS_T2:
        if (row.get(fld) or "").strip().lower() == "default":
            return "default player"
    return None
 
 
def team_names(row, fields):
    return [n for n in ((row.get(f) or "").strip() for f in fields) if n]
 
 
def categorize(rating_gap, margin):
    if rating_gap < TOSSUP_THRESHOLD:
        level = None
    elif rating_gap < SLIGHT_THRESHOLD:
        level = "slight"
    else:
        level = "heavy"
    if margin >= BLOWOUT_MARGIN:
        result = "blowout"
    elif margin >= NARROW_MARGIN:
        result = "solid"
    else:
        result = "narrow"
    return level, result
 
 
def process(ratings, rows, verbose=False):
    start = dict(ratings)
    games = defaultdict(int)
    wins = defaultdict(int)
    unknown = set()
    skipped = defaultdict(int)
    backtest = defaultdict(lambda: [0, 0])  # level -> [games, higher-rated team won]
    played = 0
 
    def cur(name):
        if name not in ratings:
            ratings[name] = DEFAULT_RATING
            start[name] = DEFAULT_RATING
            unknown.add(name)
            print(f"WARNING: no rating found for player '{name}'; "
                  f"using default rating {DEFAULT_RATING}", file=sys.stderr)
        return ratings[name]
 
    for row in rows:
        reason = skip_reason(row)
        if reason:
            skipped[reason] += 1
            continue
        t1, t2 = team_names(row, PLAYER_FIELDS_T1), team_names(row, PLAYER_FIELDS_T2)
        try:
            s1, s2 = int(row["team1_points"]), int(row["team2_points"])
        except (TypeError, ValueError):
            skipped["bad score"] += 1
            continue
        if not t1 or not t2:
            skipped["missing players"] += 1
            continue
        if s1 == s2:
            skipped["tie"] += 1
            continue
 
        r1 = sum(cur(n) for n in t1) / len(t1)
        r2 = sum(cur(n) for n in t2) / len(t2)
        team1_won = s1 > s2
        margin = abs(s1 - s2)
        gap = abs(r1 - r2)
        level, margin_cat = categorize(gap, margin)
 
        if level is None:
            role = "tossup"
            winner_delta = BASE_RATING_DELTA * RATING_CHANGE[(role, None, margin_cat)] / 2
            d1, d2 = (winner_delta, -winner_delta) if team1_won else (-winner_delta, winner_delta)
            higher_won = team1_won == (r1 >= r2)
        else:
            team1_fav = r1 > r2
            fav_won = team1_won == team1_fav
            role = "favored" if fav_won else "underdog"
            mult = BASE_RATING_DELTA * RATING_CHANGE[(role, level, margin_cat)] / 2
            # favored-win value is the favorite's change; underdog-win value is the underdog's
            fav_delta, dog_delta = (mult, -mult) if fav_won else (-mult, mult)
            d1, d2 = (fav_delta, dog_delta) if team1_fav else (dog_delta, fav_delta)
            higher_won = fav_won
 
        d1 += WINNING_BONUS if team1_won else -LOSING_PENALTY
        d2 += -LOSING_PENALTY if team1_won else WINNING_BONUS
 
        bt = backtest[level or "tossup"]
        bt[0] += 1
        bt[1] += int(higher_won)
 
        before = {n: ratings[n] for n in t1 + t2}
        for n in t1:
            ratings[n] += d1
            games[n] += 1
            wins[n] += int(team1_won)
        for n in t2:
            ratings[n] += d2
            games[n] += 1
            wins[n] += int(not team1_won)
        played += 1
 
        if verbose:
            print(f"[{row['match_date']}] {'/'.join(t1)} ({s1}) vs {'/'.join(t2)} ({s2}) | "
                  f"team ratings {r1:.2f}/{r2:.2f} | {level or 'tossup'}, {role}, {margin_cat} | "
                  f"team1 {d1:+.4f}, team2 {d2:+.4f}")
            for n in t1 + t2:
                print(f"    {n}: {before[n]:.3f} -> {ratings[n]:.3f}")
 
    return {"start": start, "games": games, "wins": wins, "unknown": unknown,
            "skipped": skipped, "backtest": backtest, "played": played}
 

def season_report(ratings, res):
    deltas = {p: ratings[p] - res["start"][p] for p in ratings}
    eligible = [d for p, d in deltas.items() if res["games"][p] > 0]
    field_median = statistics.median(eligible) if eligible else 0.0
    rows = []
    for p in ratings:
        g = res["games"][p]
        vs_field = deltas[p] - field_median
        if g == 0:
            flag = "no games"
        elif vs_field >= FLAG_DELTA:
            flag = "outperformer"
        elif vs_field <= -FLAG_DELTA:
            flag = "underperformer"
        else:
            flag = "on level"
        rows.append((p, res["start"][p], ratings[p], deltas[p], vs_field, g, res["wins"][p], flag))
    rows.sort(key=lambda r: -r[2])  # final rating, highest to lowest
    return rows, field_median
 
 
def main():
    ap = argparse.ArgumentParser(description="Season-end PTP rating analysis.")
    ap.add_argument("ratings_file", help="CSV: player,rating (minimum ratings)")
    ap.add_argument("matches_file", help="CSV of match results")
    ap.add_argument("-o", "--output", default="temp_ratings.csv",
                    help="season ratings CSV, sorted by final rating (default: temp_ratings.csv)")
    ap.add_argument("--verbose", action="store_true", help="print every match")
    args = ap.parse_args()
 
    ratings = load_ratings(args.ratings_file)
    rows = load_matches_sorted(args.matches_file)
    res = process(ratings, rows, args.verbose)
    report, median = season_report(ratings, res)
 
    with open(args.output, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["player", "start_rating", "final_rating", "delta",
                    "delta_vs_field", "games", "wins", "flag"])
        for p, s, fin, d, vf, g, wn, flag in report:
            w.writerow([p, f"{s:.3f}", f"{fin:.3f}", f"{d:+.3f}", f"{vf:+.3f}", g, wn, flag])
 
    print(f"Matches rated: {res['played']} | players: {len(ratings)}")
    if res["skipped"]:
        print("Skipped: " + ", ".join(f"{k}: {v}" for k, v in sorted(res["skipped"].items())))
    if res["unknown"]:
        print(f"{len(res['unknown'])} players not in ratings file started at {DEFAULT_RATING}")
    print(f"Median season change (field drift): {median:+.3f}")
    flags = defaultdict(int)
    for r in report:
        flags[r[7]] += 1
    print("Flags: " + ", ".join(f"{k}: {v}" for k, v in sorted(flags.items())))
 
    print("\nBacktest - how often the higher-rated team won, by pre-game expectation:")
    for lvl in ("tossup", "slight", "heavy"):
        g, hw = res["backtest"].get(lvl, (0, 0))
        if g:
            print(f"  {lvl:7s} {g:6d} games  higher-rated won {hw / g:6.1%}")
 
    print(f"\nWrote {args.output}")
 
 
if __name__ == "__main__":
    main()