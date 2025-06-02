#!/usr/bin/env python3

import csv
import trueskill
from collections import defaultdict

"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Put the data to analyze in match_data.csv
Run with: ./rank.py

"""

# Set up TrueSkill environment with no draws
# draw_probability=0.0 because there are no draws, there is always a winner
# sigma=15.0 so that players are not penalized by fewer games, their initial uncertainty is high, so it can vary quickly
# tau=0.0 so there is no skill drift, so inactive players are not penalized over time
ts = trueskill.TrueSkill(draw_probability=0.0, sigma=15.0, tau=0.0) 
player_ratings = defaultdict(ts.Rating)

def update_ratings(p1, p2, o1, o2, team1_score, team2_score):
    # Get current ratings for players on team 1
    current_rating_team1 = [player_ratings[p1], player_ratings[p2]]
    # Get current ratings for players on team 2
    current_rating_team2 = [player_ratings[o1], player_ratings[o2]]

    # Determine which team won and rate accordingly because TrueSkill expects the winning team first in the list
    if team1_score > team2_score:
        new_rating_team1, new_rating_team2 = ts.rate([current_rating_team1, current_rating_team2])
    else:
        new_rating_team2, new_rating_team1 = ts.rate([current_rating_team2, current_rating_team1])

    # Update global player ratings with the newly calculated ratings
    player_ratings[p1], player_ratings[p2] = new_rating_team1
    player_ratings[o1], player_ratings[o2] = new_rating_team2

def main():
    input_file = "match_data.csv"

    with open(input_file, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            p1 = row['partner1'].strip()
            p2 = row['partner2'].strip()
            o1 = row['opponent1'].strip()
            o2 = row['opponent2'].strip()

            # Skip any games that were defaulted
            if 'DEFAULT' in [p1, p2, o1, o2]:
                continue

            team1_score = int(row['team1_points'])
            team2_score = int(row['team2_points'])

            update_ratings(p1, p2, o1, o2, team1_score, team2_score)

    # Sort players by their skill estimate (exposed rating) in descending order
    ranked_players = sorted(player_ratings.items(), key=lambda x: ts.expose(x[1]), reverse=True)

    # Print CSV header
    print("Rank,Player,Skill,Mu,Sigma")

    # Print CSV rows
    # Unpack ranked players, for example: rank=1, player='Alice', rating=Rating(mu=30, sigma=7)
    for rank, (player, rating) in enumerate(ranked_players, 1):
        exposed = ts.expose(rating)
        print(f"{rank},{player},{exposed:.2f},{rating.mu:.2f},{rating.sigma:.2f}")

if __name__ == '__main__':
    main()

