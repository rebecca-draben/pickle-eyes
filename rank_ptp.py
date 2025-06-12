#!/usr/bin/env python3

import csv

BASE_RATING_DELTA = 0.005

TOSSUP_THRESHOLD = 0.1       # Ratings within this range are tossups
SLIGHT_THRESHOLD = 0.2      # Up to this is slight favorite, anything above is heavy

BLOWOUT_MARGIN = 11
NARROW_MARGIN = 4

# Rating changes multipliers based on context (will be scaled by BASE_RATING_DELTA)
# 3-tuple (winner relative to expectations, level of favoredness, margin of game result)
RATING_CHANGE = {
    # Underdog heavy wins (biggest rating gains)
    ('underdog', 'heavy', 'narrow'): 25,    
    ('underdog', 'heavy', 'solid'): 30,     
    ('underdog', 'heavy', 'blowout'): 35,  

    # Underdog slight wins (moderate gains)
    ('underdog', 'slight', 'narrow'): 18,   
    ('underdog', 'slight', 'solid'): 22,    
    ('underdog', 'slight', 'blowout'): 26,  

    # Tossup games (standard changes)
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

# Apply rating updates based on a match
def update_ratings(ratings, match):
    _, p1, p2, o1, o2, s1, s2 = match
    if "DEFAULT" in [p1, p2, o1, o2]:
        print("Skipping match due to DEFAULT player:", match)
        return

    s1, s2 = int(s1), int(s2)
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

    print(f"\nMatch: {p1}/{p2} ({s1}) vs {o1}/{o2} ({s2})")
    print(f"{p1}/{p2} avg rating: {team1_rating:.2f}, {o1}/{o2} avg rating: {team2_rating:.2f}")
    print(f"Score: {s1}-{s2} → {'Winners: ' + p1 + '/' + p2 if team1_won else 'Winners: ' + o1 + '/' + o2}")
    print(f"Rating difference: {rating_diff:.2f}")

    if rating_diff < TOSSUP_THRESHOLD:
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
    rating_change_multiplier = RATING_CHANGE.get(key, 10)
    change = BASE_RATING_DELTA * rating_change_multiplier
    delta = change / 2

    print(f"Result margin: {result_margin}")
    print(f"Rating change multiplier: {rating_change_multiplier}, Change per player: {delta:.2f}")

    if team1_won:
        ratings[p1] = r1 + delta
        ratings[p2] = r2 + delta
        ratings[o1] = r3 - delta
        ratings[o2] = r4 - delta
    else:
        ratings[p1] = r1 - delta
        ratings[p2] = r2 - delta
        ratings[o1] = r3 + delta
        ratings[o2] = r4 + delta

    print(f"Updated ratings:")
    print(f"  {p1}: {r1:.2f} → {ratings[p1]:.2f}")
    print(f"  {p2}: {r2:.2f} → {ratings[p2]:.2f}")
    print(f"  {o1}: {r3:.2f} → {ratings[o1]:.2f}")
    print(f"  {o2}: {r4:.2f} → {ratings[o2]:.2f}")


# Process all matches in file
def process_matches(ratings_file, matches_file):
    ratings = load_ratings(ratings_file)

    with open(matches_file, newline='') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header
        for match in reader:
            update_ratings(ratings, match)

    return ratings

# Print final ratings sorted highest to lowest
def print_ratings(ratings):
    print("\nFinal Player Ratings:")
    for player, rating in sorted(ratings.items(), key=lambda x: -x[1]):
        print(f"{player},{rating:.2f}")

# Main block
if __name__ == "__main__":
    # run fall 2024 data
    #final_ratings = process_matches("ratings_2024_fall.csv", "match_data_2024_fall.csv")

    # run spring 2025 data
    final_ratings = process_matches("ratings_2025_spring.csv", "match_data_2025_spring.csv")

    print_ratings(final_ratings)

