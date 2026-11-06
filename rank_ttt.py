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


# --------------------------------------------------
# MODEL PARAMETERS
# --------------------------------------------------

MU = 25.0
SIGMA = 20.0
BETA = 4.1667

GAMMA = 0.01
CONVERGENCE_ITERATIONS = 20
CONVERGENCE_EPSILON = 1e-3


# --------------------------------------------------
# PARSE MATCH DATA
# --------------------------------------------------

def parse_csv_for_ttt(csv_path):
    compositions = []
    results = []
    match_dates = []

    players = set()
    player_teams = defaultdict(set)

    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)

        for row in reader:

            status = row.get('status', '').strip().lower()

            p1 = row['partner1'].strip()
            p2 = row['partner2'].strip()
            o1 = row['opponent1'].strip()
            o2 = row['opponent2'].strip()

            # Skip defaulted matches
            if status in ('default', 'dbl default') or \
               'default' in (p1.lower(), p2.lower(),
                             o1.lower(), o2.lower()):
                continue

            # Validate scores
            try:
                team1_points = int(row['team1_points'])
                team2_points = int(row['team2_points'])
            except (ValueError, TypeError):
                continue

            # Skip matches where both teams have zero points
            if team1_points + team2_points == 0:
                continue

            # Validate date
            try:
                match_date = datetime.strptime(
                    row['match_date'].strip(), "%Y-%m-%d"
                )
            except ValueError:
                raise ValueError(
                    f"Invalid date format: {row['match_date']}"
                )

            team1_name = row['team1_name'].strip()
            team2_name = row['team2_name'].strip()

            # Record team associations
            for p in [p1, p2]:
                player_teams[p].add(team1_name)

            for o in [o1, o2]:
                player_teams[o].add(team2_name)

            # Record match composition
            compositions.append([[p1, p2], [o1, o2]])

            # Record results
            if team1_points > team2_points:
                results.append([1, 0])
            elif team2_points > team1_points:
                results.append([0, 1])
            else:
                results.append([1, 1])

            match_dates.append(match_date)

            # Track all players
            players.update([p1, p2, o1, o2])

    # Sort all match data chronologically
    sorted_indices = sorted(
        range(len(match_dates)),
        key=lambda i: match_dates[i]
    )

    compositions = [compositions[i] for i in sorted_indices]
    results = [results[i] for i in sorted_indices]
    sorted_dates = [match_dates[i] for i in sorted_indices]

    if not sorted_dates:
        raise ValueError(f"No valid completed games found in {csv_path}")

    # Convert dates to days since first match
    base_date = sorted_dates[0]

    times = [
        (d - base_date).days
        for d in sorted_dates
    ]

    return (
        compositions,
        results,
        times,
        sorted(players),
        player_teams
    )


# --------------------------------------------------
# COMPUTE TRUESKILL THROUGH TIME RATINGS
# --------------------------------------------------

def compute_ttt_ratings(compositions, results, times, players):

    # Give every player the same initial prior
    priors = {
        p: Player(
            Gaussian(mu=MU, sigma=SIGMA),
            beta=BETA,
            gamma=GAMMA
        )
        for p in players
    }

    h = History(
        composition=compositions,
        results=results,
        times=times,
        priors=priors,
        sigma=SIGMA,
        beta=BETA,
        gamma=GAMMA
    )

    # Run TTT inference
    h.convergence(
        iterations=CONVERGENCE_ITERATIONS,
        epsilon=CONVERGENCE_EPSILON
    )

    # Retrieve learning curves
    curves = h.learning_curves()

    # Use each player's last available estimate
    final_ratings = {
        p: curves[p][-1][1]
        for p in players
        if curves[p]
    }

    return final_ratings


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main(csv_file):

    print("Parsing match data...")

    (
        compositions,
        results,
        times,
        players,
        player_teams
    ) = parse_csv_for_ttt(csv_file)

    print(f"Total matches: {len(compositions)}")
    print(f"Total players: {len(players)}")
    print(f"Gamma: {GAMMA}")
    print()

    print("Running TrueSkill Through Time inference...")

    ratings = compute_ttt_ratings(
        compositions,
        results,
        times,
        players
    )

    # Rank by best estimated skill (mu)
    ranked = sorted(
        ratings.items(),
        key=lambda x: x[1].mu,
        reverse=True
    )

    print()
    print("Rank,Player,Team,Skill,Mu,Sigma")

    for i, (p, r) in enumerate(ranked, 1):

        skill = r.mu

        teams = sorted(player_teams.get(p, []))
        team_str = "|".join(teams) if teams else "Unknown"

        print(
            f"{i},{p},{team_str},"
            f"{skill:.2f},{r.mu:.2f},{r.sigma:.2f}"
        )


# --------------------------------------------------
# COMMAND LINE
# --------------------------------------------------

if __name__ == "__main__":

    import sys

    if len(sys.argv) != 2:
        print("Usage: python ttt_ratings.py match_data.csv")
        sys.exit(1)

    csv_file = sys.argv[1]
    main(csv_file)

