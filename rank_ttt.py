#!/usr/bin/env python3


"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./rank_ttt.py match_data_x.csv
This script is slower, but more accurate
"""

import csv
from datetime import datetime
from collections import defaultdict
from trueskillthroughtime import History, Player, Gaussian

def parse_csv_for_ttt(csv_path):
    compositions = []
    results = []
    match_dates = []
    players = set()
    player_teams = {}

    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            p1, p2 = row['partner1'].strip(), row['partner2'].strip()
            o1, o2 = row['opponent1'].strip(), row['opponent2'].strip()

            if 'DEFAULT' in [p1, p2, o1, o2]:
                continue

            team1_name = row['team1_name'].strip()
            team2_name = row['team2_name'].strip()

            # Assign team names once per player
            for p in [p1, p2]:
                if p not in player_teams:
                    player_teams[p] = team1_name
            for o in [o1, o2]:
                if o not in player_teams:
                    player_teams[o] = team2_name

            try:
                team1_points = int(row['team1_points'])
                team2_points = int(row['team2_points'])
            except ValueError:
                continue  # skip invalid scores

            compositions.append([[p1, p2], [o1, o2]])
            results.append([1, 0] if team1_points > team2_points else [0, 1])

            try:
                match_date = datetime.strptime(row['match_date'].strip(), "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Invalid date format: {row['match_date']}")
            match_dates.append(match_date)

            players.update([p1, p2, o1, o2])

    # Sort all lists by match_date
    sorted_indices = sorted(range(len(match_dates)), key=lambda i: match_dates[i])
    compositions = [compositions[i] for i in sorted_indices]
    results = [results[i] for i in sorted_indices]
    times = list(range(len(compositions)))

    return compositions, results, times, sorted(players), player_teams

def compute_ttt_ratings(compositions, results, times, players):
    priors = {
        p: Player(Gaussian(mu=25.0, sigma=8.333), beta=4.1667, gamma=0.0)
        for p in players
    }

    h = History(
        composition=compositions,
        results=results,
        times=times,
        priors=priors,
        sigma=8.333,
        beta=4.1667,
        gamma=0.0
    )

    h.convergence(iterations=20, epsilon=1e-3)

    curves = h.learning_curves()
    final_ratings = {p: curves[p][-1][1] for p in players}

    return final_ratings

def main(csv_file):
    print("Parsing match data...")
    compositions, results, times, players, player_teams = parse_csv_for_ttt(csv_file)
    print(f"Total matches: {len(compositions)}")
    print(f"Total players: {len(players)}")

    print("Running TrueSkill Through Time inference...")
    ratings = compute_ttt_ratings(compositions, results, times, players)

    ranked = sorted(
        ratings.items(),
        key=lambda x: x[1].mu,
        reverse=True
    )

    print("Rank,Player,Team,Mu,Sigma")
    for i, (p, r) in enumerate(ranked, 1):
        team = player_teams.get(p, "Unknown")
        print(f"{i},{p},{team},{r.mu:.2f},{r.sigma:.2f}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python ttt_ratings.py match_data.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    main(csv_file)
