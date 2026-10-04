import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(page_title="Household ATS Showdown", page_icon="🏈", layout="wide")

def parse_spread(odds_str, team_abbr):
    """
    Think of this like a DAX SWITCH or nested IF statement.
    It takes ESPN's text string (e.g., 'SF -3.5') and turns it into a decimal number.
    """
    if not odds_str or odds_str.upper() in ["EVEN", "PK"]:
        return 0.0
    
    parts = odds_str.split(" ")
    if len(parts) >= 2:
        favored_team = parts[0]
        try:
            spread_val = float(parts[1])
        except ValueError:
            return 0.0
            
        if favored_team == team_abbr:
            return spread_val
        else:
            return abs(spread_val) 
    return 0.0

@st.cache_data(ttl=3600) 
def fetch_season_data():
    """
    This is your Python equivalent of Power Query (M-Code).
    It connects to the web, drills down into the JSON, and builds a clean table.
    """
    results = []
    now = datetime.datetime.now()
    year = now.year if now.month > 2 else now.year - 1
    
    for week in range(1, 19):
        # Web.Contents equivalent: Pulls the raw JSON for that specific week
        url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={year}&week={week}&seasontype=2"
        resp = requests.get(url)
        if resp.status_code != 200: 
            continue
            
        data = resp.json()
        sf_data, lv_data = None, None
        
        # Expand the JSON records (like clicking the "Expand" arrows in Power Query)
        for event in data.get('events', []):
            comp = event['competitions'][0]
            
            # Filter out games that haven't finished yet ('post' means completed)
            if comp['status']['type']['state'] != 'post': 
                continue
                
            teams = comp['competitors']
            team_abbrs = [t['team']['abbreviation'] for t in teams]
            
            # ESPN stores the closing spread in the 'details' text field
            odds_str = comp.get('odds', [{}])[0].get('details', '') if comp.get('odds') else ''
            
            if 'SF' in team_abbrs:
                sf_team = next(t for t in teams if t['team']['abbreviation'] == 'SF')
                opp_team = next(t for t in teams if t['team']['abbreviation'] != 'SF')
                sf_data = {
                    'score': int(sf_team['score']), 
                    'opp_score': int(opp_team['score']), 
                    'spread': parse_spread(odds_str, 'SF')
                }
            
            if 'LV' in team_abbrs:
                lv_team = next(t for t in teams if t['team']['abbreviation'] == 'LV')
                opp_team = next(t for t in teams if t['team']['abbreviation'] != 'LV')
                lv_data = {
                    'score': int(lv_team['score']), 
                    'opp_score': int(opp_team['score']), 
                    'spread': parse_spread(odds_str, 'LV')
                }
        
        # If both teams played this week (ignores bye weeks), calculate the winner
        if sf_data and lv_data:
            sf_ats = (sf_data['score'] - sf_data['opp_score']) + sf_data['spread']
            lv_ats = (lv_data['score'] - lv_data['opp_score']) + lv_data['spread']
            
            if sf_ats > lv_ats: 
                winner = "49ers"
            elif lv_ats > sf_ats: 
                winner = "Raiders"
            else: 
                winner = "Tie"
            
            # Append a new row to our list
            results.append({
                "Week": week,
                "49ers Spread": sf_data['spread'],
                "49ers ATS Margin": sf_ats,
                "Raiders Spread": lv_data['spread'],
                "Raiders ATS Margin": lv_ats,
                "Winner": winner
            })
            
    # Convert our list of rows into a DataFrame (a clean table)
    return pd.DataFrame(results)


# --- DASHBOARD UI (Your 'Excel Canvas') ---
st.title("🏈 ATS Showdown: 49ers vs. Raiders")
st.caption("Live scores & closing lines via ESPN")

with st.spinner("Crunching this season's matchups..."):
    df = fetch_season_data()

st.header("🏆 Season Scoreboard")
if not df.empty:
    sf_wins = len(df[df["Winner"] == "49ers"])
    lv_wins = len(df[df["Winner"] == "Raiders"])
    ties = len(df[df["Winner"] == "Tie"])
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🔴 49ers Wins", sf_wins)
    col2.metric("⚫ Raiders Wins", lv_wins)
    col3.metric("⚖️ Ties", ties)
    
    if sf_wins > lv_wins:
        st.success("🔥 The 49ers are leading the household!")
    elif lv_wins > sf_wins:
        st.success("🔥 The Raiders are leading the household!")
    else:
        st.info("⚖️ It's a dead heat!")

    st.header("📊 Completed Weeks")
    # Apply a light green highlight to the winning team's column
    st.dataframe(
        df.style.apply(lambda x: ['background-color: lightgreen' if v == '49ers' else '' for v in x], subset=['Winner']),
        use_container_width=True,
        hide_index=True
    )
else:
    st.info("No completed head-to-head weeks found yet for this season.")
    
