#!/usr/bin/env python3


"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./rank_ts.py match_data_x.csv
This script is faster, but less accurate
"""

import csv
import argparse
import trueskill
from collections import defaultdict


# Set up TrueSkill environment with no draws
# draw_probability=0.0 because there are no draws, there is always a winner
# sigma=15.0 so that players are not penalized by fewer games, their initial uncertainty is high, so it can vary quickly
# tau=0.0 so there is no skill drift, so inactive players are not penalized over time
ts = trueskill.TrueSkill(draw_probability=0.0, sigma=8.333, tau=0.0) 
player_ratings = defaultdict(ts.Rating)

# store which team the player plays on, assumes one team in the input data
player_teams = {}

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
    parser = argparse.ArgumentParser(description="Calculate TrueSkill ratings from match data.")
    parser.add_argument("csv_file", help="Input match data CSV file (e.g., match_data_test.csv)")
    args = parser.parse_args()

    input_file = args.csv_file

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

            team1_name = row['team1_name'].strip()
            team2_name = row['team2_name'].strip()

            # Set team names only if not already set (first occurrence wins)
            for player in [p1, p2]:
                if player not in player_teams:
                    player_teams[player] = team1_name
            for player in [o1, o2]:
                if player not in player_teams:
                    player_teams[player] = team2_name

            team1_score = int(row['team1_points'])
            team2_score = int(row['team2_points'])

            update_ratings(p1, p2, o1, o2, team1_score, team2_score)

    # Sort players by their skill estimate (exposed rating) in descending order
    ranked_players = sorted(player_ratings.items(), key=lambda x: x[1].mu, reverse=True)

    # Print CSV header
    print("Rank,Player,Team,Skill,Mu,Sigma")

    # Print CSV rows
    # Unpack ranked players, for example: rank=1, player='Alice', rating=Rating(mu=30, sigma=7)
    for rank, (player, rating) in enumerate(ranked_players, 1):
        exposed = ts.expose(rating)
        team_name = player_teams.get(player, "Unknown")
        print(f"{rank},{player},{team_name},{exposed:.2f},{rating.mu:.2f},{rating.sigma:.2f}")


if __name__ == '__main__':
    main()

