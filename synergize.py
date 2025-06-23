#!/usr/bin/env python3

"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./synergize.py match_data_x.csv

"""

import csv
from collections import defaultdict
import statistics
import argparse
from trueskillthroughtime import History, Player, Gaussian

# Histories for each player
player_objs = {}  # name -> Player()

# Partnership stats: store wins/losses and match history
partnership_stats = defaultdict(lambda: {'wins': 0, 'losses': 0, 'matches': []})
player_to_team = {}

# To build History, store compositions: [ [winner_team, loser_team], ... ]
compositions = []

def record_partnership(p_team, o_team, team_won, score_diff):
    """
    Track partnership performance (win/loss, score diff, opponents).
    """
    key = tuple(sorted(p_team))
    partnership_stats[key]['matches'].append({
        'won': team_won,
        'score_diff': score_diff,
        'opponents': tuple(sorted(o_team))
    })
    if team_won:
        partnership_stats[key]['wins'] += 1
    else:
        partnership_stats[key]['losses'] += 1

def build_players(*names):
    """
    Ensure each player name has a Player() object.
    """
    for name in names:
        if name not in player_objs:
            player_objs[name] = Player()

def parse_csv(input_file):
    with open(input_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)

        for idx, row in enumerate(reader):
            p1 = row['partner1'].strip()
            p2 = row['partner2'].strip()
            o1 = row['opponent1'].strip()
            o2 = row['opponent2'].strip()
            if 'DEFAULT' in (p1, p2, o1, o2):
                continue

            score1 = int(row['team1_points'])
            score2 = int(row['team2_points'])
            win_team = [p1, p2] if score1 > score2 else [o1, o2]
            lose_team = [o1, o2] if score1 > score2 else [p1, p2]
            team_won = score1 > score2
            score_diff = abs(score1 - score2)

            build_players(p1, p2, o1, o2)

            # Track team-to-player association (assumes consistent naming)
            player_to_team[p1] = row['team1_name'].strip()
            player_to_team[p2] = row['team1_name'].strip()
            player_to_team[o1] = row['team2_name'].strip()
            player_to_team[o2] = row['team2_name'].strip()

            # Record for the TTT History
            compositions.append([win_team, lose_team])

            # Record partnership stats for both teams
            record_partnership(win_team, lose_team, True, score_diff)
            record_partnership(lose_team, win_team, False, -score_diff)

def compute_synergy(curves):
    """
    For each partnership, compute synergy metrics using latest player mus.
    """
    results = []
    # Latest skill (mu) for each player
    latest_mu = {name: curves[name][-1][1].mu for name in curves}

    for (p1, p2), stats in partnership_stats.items():
        if len(stats['matches']) < 2:
            continue

        indiv_strength = latest_mu[p1] + latest_mu[p2]

        total_perf = 0
        for m in stats['matches']:
            team_strength = latest_mu[p1] + latest_mu[p2]
            opp1, opp2 = m['opponents']
            opp_strength = latest_mu[opp1] + latest_mu[opp2]
            expected = 1 / (1 + 10 ** ((opp_strength - team_strength) / 10))
            actual = 1 if m['won'] else 0
            total_perf += (actual - expected)

        avg_perf = total_perf / len(stats['matches'])
        win_rate = stats['wins'] / (stats['wins'] + stats['losses'])
        avg_diff = statistics.mean(m['score_diff'] for m in stats['matches'])
        team_name = player_to_team.get(p1, "")

        results.append({
            'partnership': f"{p1} + {p2}",
            'player1': p1,
            'player2': p2,
            'team_name': team_name,
            'synergy_score': avg_perf * 100,
            'win_rate': win_rate,
            'matches_played': len(stats['matches']),
            'avg_score_diff': avg_diff,
            'individual_strength': indiv_strength
        })

    results.sort(key=lambda x: x['synergy_score'], reverse=True)
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('input_file', help='CSV file with match data')
    args = parser.parse_args()

    parse_csv(args.input_file)

    # Run TrueSkill Through Time
    # gamma=0 models static skill; set >0 to let skills drift over time
    history = History(compositions, gamma=0.01)
    history.convergence()
    curves = history.learning_curves()

    synergies = compute_synergy(curves)

    # Output CSV
    print("Rank,Partnership,Player1,Player2,Team,Synergy_Score,Win_Rate,Games,Individual_Strength")
    for rank, d in enumerate(synergies, 1):
        print(f"{rank},\"{d['partnership']}\",{d['player1']},{d['player2']},{d['team_name']},"
              f"{d['synergy_score']:.2f},{d['win_rate']:.2f},"
              f"{d['matches_played']},{d['individual_strength']:.2f}")

if __name__ == '__main__':
    main()
