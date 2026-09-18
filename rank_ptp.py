#!/usr/bin/env python3

"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./rank_ptp.py match_data_x.csv

"""

import csv
import argparse
from datetime import datetime

BASE_RATING_DELTA = 0.0035  # Scales up or down all RATING_CHANGE numbers to add/subtract more for each win/loss

WINNING_BONUS = 0.01   # Applied to winners: +WINNING_BONUS
LOSING_PENALTY = 0.01  # Applied to losers: -LOSING_PENALTY (kept equal to WINNING_BONUS to stay zero-sum)

TOSSUP_THRESHOLD = 0.1      # Rating difference up to this value is tossup
SLIGHT_THRESHOLD = 0.2      # Rating difference up to this value is slight favorite, anything above is heavy favorite

BLOWOUT_MARGIN = 12
NARROW_MARGIN = 3

# Common date formats to try when parsing the match date column, in order.
DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m/%d/%y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%m-%d-%Y",
]

# Rating changes multipliers based on context (will be scaled by BASE_RATING_DELTA)
# 3-tuple (winner relative to expectations, level of favoredness, margin of game result)
#
# 15 total categories:
#   - Tossup:            3 entries (no favored side exists, so no favored/underdog split)
#   - Slight favorite:   6 entries (favored won / underdog won) x (narrow/solid/blowout)
#   - Heavy favorite:    6 entries (favored won / underdog won) x (narrow/solid/blowout)
RATING_CHANGE = {
    # Underdog heavy wins (biggest rating gains)
    ('underdog', 'heavy', 'narrow'): 25,
    ('underdog', 'heavy', 'solid'): 30,
    ('underdog', 'heavy', 'blowout'): 35,

    # Underdog slight wins (moderate gains)
    ('underdog', 'slight', 'narrow'): 18,
    ('underdog', 'slight', 'solid'): 22,
    ('underdog', 'slight', 'blowout'): 26,

    # Tossup games (standard changes) - no favored/underdog split, no favorite exists
    ('tossup', None, 'narrow'): 12,
    ('tossup', None, 'solid'): 15,
    ('tossup', None, 'blowout'): 18,

    # Slightly favored team wins (small gains)
    ('favored', 'slight', 'narrow'): 8,
    ('favored', 'slight', 'solid'): 10,
    ('favored', 'slight', 'blowout'): 12,

    # Heavily favored team wins (minimal gains)
    ('favored', 'heavy', 'narrow'): 3,
    ('favored', 'heavy', 'solid'): 5,
    ('favored', 'heavy', 'blowout'): 7,
}


# Load initial ratings from CSV
def load_ratings(filename):
    ratings = {}
    with open(filename, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for row in reader:
            player, rating = row
            ratings[player] = float(rating)
    return ratings


def parse_match_date(date_str):
    """Parse a date string using a list of common formats. Raises ValueError if none match."""
    date_str = date_str.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Could not parse date '{date_str}' with any known format")


def load_matches_sorted(matches_file):
    """
    Load all match rows and sort them chronologically by the 'date' column
    before any ratings are processed. Processing must happen in true match
    order for the dynamic, path-dependent rating updates to be meaningful.
    """
    with open(matches_file, newline='') as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return rows

    if 'match_date' not in rows[0]:
        raise KeyError(
            "Expected a 'match_date' column in the matches CSV to sort chronologically, "
            f"but found columns: {list(rows[0].keys())}. "
            "Update the column name in load_matches_sorted() if yours differs."
        )

    for row in rows:
        row['_parsed_date'] = parse_match_date(row['match_date'])

    rows.sort(key=lambda r: r['_parsed_date'])
    return rows


def is_skippable(row):
    """
    A match should be skipped if its 'status' column doesn't indicate a
    normally completed match. In particular this covers 'Default' and
    'Dbl Default' (single/double default), matched case-insensitively and
    substring-wise so variants like 'DEFAULT', 'default', 'Dbl. Default'
    etc. are all caught. Only rows whose status is exactly 'Completed'
    (case-insensitive) are processed - anything else (defaults, and any
    other non-completed status such as cancellations) is skipped, with the
    reason logged so it's clear from the output what was excluded and why.
    """
    status = row.get('status', '').strip()
    if status.lower() != 'completed':
        return True, status
    return False, status


# Apply rating updates based on a match
def update_ratings(ratings, row):
    p1 = row['partner1'].strip()
    p2 = row['partner2'].strip()
    o1 = row['opponent1'].strip()
    o2 = row['opponent2'].strip()

    skip, status = is_skippable(row)
    if skip:
        print(f"Skipping match (status='{status}'):", row)
        return

    s1 = int(row['team1_points'])
    s2 = int(row['team2_points'])
    default_rating = 3.5

    # Get current ratings or use default
    r1 = ratings.get(p1, default_rating)
    r2 = ratings.get(p2, default_rating)
    r3 = ratings.get(o1, default_rating)
    r4 = ratings.get(o2, default_rating)

    team1_rating = (r1 + r2) / 2
    team2_rating = (r3 + r4) / 2

    team1_won = s1 > s2
    rating_diff = abs(team1_rating - team2_rating)

    date_label = row.get('match_date', '?')
    print(f"\n[{date_label}] Match: {p1}/{p2} ({s1}) vs {o1}/{o2} ({s2})")
    print(f"{p1}/{p2} avg rating: {team1_rating:.2f}, {o1}/{o2} avg rating: {team2_rating:.2f}")
    print(f"Score: {s1}-{s2} → {'Winners: ' + p1 + '/' + p2 if team1_won else 'Winners: ' + o1 + '/' + o2}")
    print(f"Rating difference: {rating_diff:.2f}")

    if rating_diff < TOSSUP_THRESHOLD:
        # No favorite exists in a tossup, so there is no favored/underdog split -
        # this is one of the 3 tossup categories (by margin only).
        winner_context = 'tossup'
        favoredness_level = None
        print("Match context: Toss-up")
    else:
        favored_team = 'team1' if team1_rating > team2_rating else 'team2'
        favoredness_level = 'slight' if rating_diff < SLIGHT_THRESHOLD else 'heavy'
        winner_context = (
            'favored' if (team1_won and favored_team == 'team1') or (not team1_won and favored_team == 'team2')
            else 'underdog'
        )
        favored_players = f"{p1}/{p2}" if favored_team == 'team1' else f"{o1}/{o2}"
        print(f"Favored team: {favored_players}")
        print(f"Favored level: {favoredness_level}")
        print(f"Winning team type: {winner_context}")

    margin = abs(s1 - s2)
    if margin >= BLOWOUT_MARGIN:
        result_margin = 'blowout'
    elif margin >= NARROW_MARGIN:
        result_margin = 'solid'
    else:
        result_margin = 'narrow'

    key = (winner_context, favoredness_level, result_margin)
    if key not in RATING_CHANGE:
        # Should never happen - all 15 valid categories are populated above.
        raise KeyError(f"Unexpected rating category {key} - not one of the 15 defined categories")
    rating_change_multiplier = RATING_CHANGE[key]
    change = BASE_RATING_DELTA * rating_change_multiplier
    delta = change / 2

    print(f"Result margin: {result_margin}")
    print(f"Rating change multiplier: {rating_change_multiplier}, Change per player: {delta:.3f}")
    print(f"Winning bonus: +{WINNING_BONUS}, Losing penalty: -{LOSING_PENALTY}")

    if team1_won:
        ratings[p1] = r1 + delta + WINNING_BONUS
        ratings[p2] = r2 + delta + WINNING_BONUS
        ratings[o1] = r3 - delta - LOSING_PENALTY
        ratings[o2] = r4 - delta - LOSING_PENALTY
    else:
        ratings[p1] = r1 - delta - LOSING_PENALTY
        ratings[p2] = r2 - delta - LOSING_PENALTY
        ratings[o1] = r3 + delta + WINNING_BONUS
        ratings[o2] = r4 + delta + WINNING_BONUS

    print(f"Updated ratings:")
    print(f"  {p1}: {r1:.3f} → {ratings[p1]:.3f}")
    print(f"  {p2}: {r2:.3f} → {ratings[p2]:.3f}")
    print(f"  {o1}: {r3:.3f} → {ratings[o1]:.3f}")
    print(f"  {o2}: {r4:.3f} → {ratings[o2]:.3f}")


# Process all matches in file, in chronological order
def process_matches(ratings_file, matches_file):
    ratings = load_ratings(ratings_file)

    rows = load_matches_sorted(matches_file)
    for row in rows:
        update_ratings(ratings, row)

    return ratings


# Print final ratings sorted highest to lowest
def print_ratings(ratings):
    print("\nFinal Player Ratings:")
    for player, rating in sorted(ratings.items(), key=lambda x: -x[1]):
        print(f"{player},{rating:.2f}")


# Main block
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process rating updates from match data.")
    parser.add_argument("ratings_file", help="Input CSV file with initial ratings")
    parser.add_argument("matches_file", help="CSV file with match results")

    args = parser.parse_args()

    final_ratings = process_matches(args.ratings_file, args.matches_file)
    print_ratings(final_ratings)

