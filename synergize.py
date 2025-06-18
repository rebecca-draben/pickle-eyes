#!/usr/bin/env python3

"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./synergize.py match_data_x.csv

"""

import csv
import trueskill
from collections import defaultdict
import statistics
import argparse


# Initialize TrueSkill environment with no draws (draw_probability=0.0)
ts = trueskill.TrueSkill(draw_probability=0.0, sigma=15.0, tau=0.0) 

# Dictionary to store player ratings, default rating assigned automatically
player_ratings = defaultdict(ts.Rating)

# Dictionary to store partnership stats:
# Each key is a tuple of two players, values track wins, losses, and detailed match info
partnership_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'matches': []})

# store which team the player plays on, assumes one team in the input data
player_to_team = {}


def update_ratings(p1, p2, o1, o2, score1, score2):
    """
    Update player ratings and partnership stats based on a single match result.

    p1, p2: players on team 1
    o1, o2: players on team 2
    score1, score2: points scored by each team
    """
    # Sort players alphabetically to normalize team keys (ensures consistent ordering)
    team_a = tuple(sorted([p1, p2]))
    team_b = tuple(sorted([o1, o2]))

    # Fetch current TrueSkill ratings for each player on both teams
    ratings_a = [player_ratings[p] for p in team_a]
    ratings_b = [player_ratings[p] for p in team_b]

    # Determine winner and update ratings accordingly using TrueSkill's rate function
    if score1 > score2:
        new_ratings_a, new_ratings_b = ts.rate([ratings_a, ratings_b])
        winner, loser = team_a, team_b
        winner_score, loser_score = score1, score2
    else:
        new_ratings_b, new_ratings_a = ts.rate([ratings_b, ratings_a])
        winner, loser = team_b, team_a
        winner_score, loser_score = score2, score1

    # Save updated ratings back to player_ratings dictionary
    for i, p in enumerate(team_a):
        player_ratings[p] = new_ratings_a[i]
    for i, p in enumerate(team_b):
        player_ratings[p] = new_ratings_b[i]

    # Record match information for both partnerships (both teams)
    for team, opponent, team_score, opponent_score in [
        (team_a, team_b, score1, score2),
        (team_b, team_a, score2, score1)
    ]:
        # Determine if this team won
        won = team_score > opponent_score
        
        # Calculate total exposed rating (skill) for team and opponent
        team_strength = sum(ts.expose(player_ratings[p]) for p in team)
        opponent_strength = sum(ts.expose(player_ratings[p]) for p in opponent)

        # Append detailed match record to partnership stats
        partnership_stats[team]['matches'].append({
            'won': won,
            'team_strength': team_strength,
            'opponent_strength': opponent_strength,
            'score_diff': team_score - opponent_score,
            'opponents': opponent
        })

        # Increment win/loss counters accordingly
        if won:
            partnership_stats[team]['wins'] += 1
        else:
            partnership_stats[team]['losses'] += 1

def calculate_synergy(partnership, stats):
    """
    Calculate synergy score and related metrics for a given partnership.

    partnership: tuple of two player names
    stats: dictionary containing partnership match history and results
    """
    # Require at least 2 matches to calculate meaningful synergy
    if len(stats['matches']) < 2:
        return None

    # Sum of individual player skills (exposed ratings)
    p1, p2 = partnership
    individual_strength = sum(ts.expose(player_ratings[p]) for p in partnership)

    total_performance = 0
    for match in stats['matches']:
        # Calculate expected win probability based on skill difference
        expected = 1 / (1 + 10 ** ((match['opponent_strength'] - match['team_strength']) / 10))
        actual = 1 if match['won'] else 0
        # Performance = actual result minus expected probability
        total_performance += (actual - expected)

    # Average performance over all matches
    avg_performance = total_performance / len(stats['matches'])

    # Calculate win rate safely
    win_rate = stats['wins'] / (stats['wins'] + stats['losses'])

    # Average score differential (margin of victory or loss)
    avg_score_diff = statistics.mean(m['score_diff'] for m in stats['matches'])

    # Return synergy metrics
    return {
        'synergy_score': avg_performance * 100,  # Scaled to percentage
        'win_rate': win_rate,
        'matches_played': len(stats['matches']),
        'avg_score_diff': avg_score_diff,
        'individual_strength': individual_strength
    }

def main():
    """
    Main execution function:
    Reads match data, updates ratings, calculates partnership synergy, and prints leaderboard.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Compute partnership synergy from match data.")
    parser.add_argument("input_file", help="CSV file with match data")
    args = parser.parse_args()
    input_file = args.input_file

    # Open the CSV file and read rows
    with open(input_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            players = [row[key].strip() for key in ['partner1', 'partner2', 'opponent1', 'opponent2']]
            team1_name = row['team1_name'].strip()
            team2_name = row['team2_name'].strip()

            if 'DEFAULT' in players:
                continue

            score1 = int(row['team1_points'])
            score2 = int(row['team2_points'])

            # Assign team names to players (assumes each player has one team)
            player_to_team[players[0]] = team1_name
            player_to_team[players[1]] = team1_name
            player_to_team[players[2]] = team2_name
            player_to_team[players[3]] = team2_name

            update_ratings(*players, score1, score2)

    # Calculate synergy for every partnership
    synergies = []
    for partnership, stats in partnership_stats.items():
        synergy = calculate_synergy(partnership, stats)
        if synergy:
            p1, p2 = partnership
            # Grab team name from the first player
            team_name = player_to_team.get(p1, "")
            synergies.append({
                'partnership': f"{p1} + {p2}",
                'player1': p1,
                'player2': p2,
                'team_name': team_name,
                **synergy
            })

    # Sort partnerships by synergy score, descending
    synergies.sort(key=lambda x: x['synergy_score'], reverse=True)

    # Print synergy leaderboard in CSV format
    print("Rank,Partnership,Player1,Player2,Team,Synergy_Score,Win_Rate,Games,Individual_Strength")
    for rank, data in enumerate(synergies, start=1):
        # Only print partnerships with at least one match
        if data['matches_played'] >= 2:
            print(f"{rank},\"{data['partnership']}\",{data['player1']},{data['player2']},{data['team_name']},"
                  f"{data['synergy_score']:.2f},{data['win_rate']:.2f},"
                  f"{data['matches_played']},{data['individual_strength']:.2f}")

if __name__ == '__main__':
    main()
