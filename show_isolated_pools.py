#!/usr/bin/env python3

"""
To run this script:
Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./show_isolated_pools.py match_data_x.csv

"""

import csv
from collections import defaultdict
import networkx as nx

def find_player_pools(csv_file):
    G = nx.Graph()

    with open(csv_file, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            p1 = row['partner1'].strip()
            p2 = row['partner2'].strip()
            o1 = row['opponent1'].strip()
            o2 = row['opponent2'].strip()

            if 'DEFAULT' in [p1, p2, o1, o2]:
                continue

            # Add edges for teammates
            G.add_edge(p1, p2)
            G.add_edge(o1, o2)

            # Add edges for opponents
            G.add_edge(p1, o1)
            G.add_edge(p1, o2)
            G.add_edge(p2, o1)
            G.add_edge(p2, o2)

    # Now find connected components (disjoint pools)
    components = list(nx.connected_components(G))
    return components

def main(csv_file):
    pools = find_player_pools(csv_file)
    print(f"Found {len(pools)} disconnected player pools.")

    for i, pool in enumerate(sorted(pools, key=lambda p: -len(p)), 1):
        print(f"Pool {i} - {len(pool)} players:")
        print(", ".join(sorted(pool)))
        print()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python find_pools.py match_data.csv")
        sys.exit(1)
    main(sys.argv[1])
