#!/usr/bin/env python3


"""
To run this script:

run in Chrome console: 
copy(document.querySelector("body > center").outerHTML)

run from command line:
pbpaste>> snippets.html && echo -e "\n\n< snippet separator -->\n\n" >> snippets.html

rename snippets.html to something more appropriate like cary_fall2024_intermediate50women.html

Activate the virtual environment with: source mypickleballenv/bin/activate
Run with: ./create_match_data.py snippets.html (or whatever file name it was renamed to)

Look for match_data_snippets.csv (or similar to whatever file name it was renamed to) to use as input to other rank and synergy scripts.

"""

from bs4 import BeautifulSoup
import csv
from datetime import datetime
import re
import argparse
import os


def clean_name(name):
    # Replace any whitespace (including unusual Unicode spaces) with a single space
    # \s matches all Unicode whitespace characters
    name = re.sub(r'\s+', ' ', name)  # collapse any whitespace sequence to a single space
    # Remove zero-width spaces and non-breaking spaces explicitly
    name = name.replace('\u200B', '').replace('\u00A0', '')
    return name.strip()


def parse_match(html):
    soup = BeautifulSoup(html, "html.parser")
    
    # match_id
    match_id_tag = soup.find("h1", string=lambda x: x and "Match Number" in x)
    match_id = match_id_tag.text.split(":")[1].strip() if match_id_tag else ""
    
    # match_date
    date_tag = soup.find("h4", string=lambda x: x and "," in x and any(month in x for month in 
                    ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]))
    date_str = date_tag.text.strip() if date_tag else ""
    match_date = ""
    if date_str:
        try:
            dt = datetime.strptime(date_str, "%a, %B %d, %Y")
            match_date = dt.strftime("%Y-%m-%d")
        except Exception:
            pass
    
    # team names
    team1_name = team2_name = ""
    header_row = soup.select_one("table.resultsbox tr")
    if header_row:
        h3_tags = header_row.find_all("h3")
        if len(h3_tags) >= 2:
            team1_name = clean_name(h3_tags[0].get_text())
            team2_name = clean_name(h3_tags[1].get_text())

    def extract_players(cell):
        links = cell.find_all("a")
        if links:
            return [clean_name(a.get_text()) for a in links]
        else:
            # Split plain text by line breaks if no <a> tags are present
            raw_text = cell.get_text(separator="\n")
            return [clean_name(name) for name in raw_text.strip().split("\n") if name.strip()]
    
    # results rows
    rows = soup.select("table.resultsbox tbody tr")
    
    games = []
    game_id = 1

    for row in rows:
        cells = row.find_all("td")
        if len(cells) == 4:
            game_id_text = cells[0].text.strip()
            # Try to extract numeric game ID (e.g. "Game 3" → 3)
            match_game_id = re.search(r'\d+', game_id_text)
            if not match_game_id:
                continue
            game_id = int(match_game_id.group())

            
            # extract players using the helper function
            team1_players = extract_players(cells[1])
            team2_players = extract_players(cells[2])
            
            score_text = cells[3].text.strip()
            if "-" in score_text:
                score_part = score_text.split("\n")[0].strip()
                team1_points, team2_points = [s.strip() for s in score_part.split("-")]
                team2_points = re.sub(r"\D", "", team2_points)  # keep digits only
            else:
                team1_points = team2_points = ""
            
            p1, p2 = (team1_players + ["", ""])[:2]
            o1, o2 = (team2_players + ["", ""])[:2]
            
            games.append({
                "match_id": match_id,
                "game_id": game_id,
                "match_date": match_date,
                "team1_name": team1_name,
                "team2_name": team2_name,
                "partner1": p1,
                "partner2": p2,
                "opponent1": o1,
                "opponent2": o2,
                "team1_points": team1_points,
                "team2_points": team2_points
            })
            game_id += 1
    
    return games



def main():
    parser = argparse.ArgumentParser(description="Parse match HTML and output CSV.")
    parser.add_argument("html_file", help="Input HTML file (e.g., test.html)")
    args = parser.parse_args()

    input_file = args.html_file

    # Validate input extension
    if not input_file.endswith(".html"):
        print("Error: Input file must have a .html extension.")
        return

    # Create output filename: match_data_<input_file_name_without_extension>.csv
    base_name = os.path.splitext(os.path.basename(input_file))[0]
    output_file = f"match_data_{base_name}.csv"

    # Read file content
    with open(input_file, "r", encoding="utf-8") as f:
        content = f.read()

    snippets = content.split("< snippet separator -->")

    all_games = []
    for snippet in snippets:
        snippet = snippet.strip()
        if snippet:
            games = parse_match(snippet)
            all_games.extend(games)

    # 🔍 REPORTING SECTION STARTS HERE
    from collections import defaultdict

    match_counts = defaultdict(int)
    for game in all_games:
        match_counts[game["match_id"]] += 1

    total_matches = len(match_counts)
    print(f"\n🔢 Total unique matches: {total_matches}")

    for match_id, count in match_counts.items():
        if count != 9:
            print(f"⚠️ Warning: Match {match_id} has {count} games (expected 9)")

    # ✅ END REPORTING

    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = [
            "match_id", "game_id", "match_date", "team1_name", "team2_name",
            "partner1", "partner2", "opponent1", "opponent2",
            "team1_points", "team2_points"
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_games)

    print(f"\n✅ Extracted {len(all_games)} games into {output_file}")



if __name__ == "__main__":
    main()
