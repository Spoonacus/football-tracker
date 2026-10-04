import streamlit as st
import pandas as pd
import requests
import datetime

st.set_page_config(page_title="Household ATS Showdown", page_icon="🏈", layout="wide")

def parse_spread(odds_str, team_abbr):
    """Parses the text string (e.g., 'SF -3.5') into a clean number."""
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
    results = []
    now = datetime.datetime.now()
    year = now.year if now.month > 2 else now.year - 1
    
    for week in range(1, 19):
        url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard?dates={year}&week={week}&seasontype=2"
        resp = requests.get(url)
        if resp.status_code != 200: 
            continue
            
        data = resp.json()
        sf_data, lv_data = None, None
        
        for event in data.get('events', []):
            comp = event['competitions'][0]
            if comp['status']['type']['state'] != 'post': 
                continue
                
            teams = comp['competitors']
            team_abbrs = [t['team']['abbreviation'] for t in teams]
            
            # Only process if it's a 49ers or Raiders game
            if 'SF' in team_abbrs or 'LV' in team_abbrs:
                
                # Check for odds in the main scoreboard first
                odds_str = comp.get('odds', [{}])[0].get('details', '') if comp.get('odds') else ''
                
                # FIX: If ESPN stripped the odds because the game ended, fetch the historical game summary
                if not odds_str:
                    game_id = event['id']
                    summary_url = f"http://site.api.espn.com/apis/site/v2/sports/football/nfl/summary?event={game_id}"
                    try:
                        sum_resp = requests.get(summary_url)
                        if sum_resp.status_code == 200:
                            pickcenter = sum_resp.json().get('pickcenter', [])
                            if pickcenter:
                                odds_str = pickcenter[0].get('details', '')
                    except:
                        pass 
                        
                # Extract 49ers data
                if 'SF' in team_abbrs:
                    sf_team = next(t for t in teams if t['team']['abbreviation'] == 'SF')
                    opp_team = next(t for t in teams if t['team']['abbreviation'] != 'SF')
                    sf_data = {
                        'score': int(sf_team['score']), 
                        'opp_score': int(opp_team['score']), 
                        'spread': parse_spread(odds_str, 'SF')
                    }
                
                # Extract Raiders data
                if 'LV' in team_abbrs:
                    lv_team = next(t for t in teams if t['team']['abbreviation'] == 'LV')
                    opp_team = next(t for t in teams if t['team']['abbreviation'] != 'LV')
                    lv_data = {
                        'score': int(lv_team['score']), 
                        'opp_score': int(opp_team['score']), 
                        'spread': parse_spread(odds_str, 'LV')
                    }
        
        # Calculate weekly winner if both played
        if sf_data and lv_data:
            sf_ats = (sf_data['score'] - sf_data['opp_score']) + sf_data['spread']
            lv_ats = (lv_data['score'] - lv_data['opp_score']) + lv_data['spread']
            
            if sf_ats > lv_ats: 
                winner = "49ers"
            elif lv_ats > sf_ats: 
                winner = "Raiders"
            else: 
                winner = "Tie"
            
            results.append({
                "Week": week,
                "49ers Spread": sf_data['spread'],
                "49ers ATS Margin": sf_ats,
                "Raiders Spread": lv_data['spread'],
                "Raiders ATS Margin": lv_ats,
                "Winner": winner
            })
            
    return pd.DataFrame(results)

# --- DASHBOARD UI ---
st.title("🏈 ATS Showdown: 49ers vs. Raiders")
st.caption("Live scores & historical closing lines via ESPN")

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
    
    # FIX: Format numbers to show +/- signs and 1 decimal place, then highlight the winning team
    styled_df = df.style.format({
        "49ers Spread": "{:+.1f}",
        "49ers ATS Margin": "{:+.1f}",
        "Raiders Spread": "{:+.1f}",
        "Raiders ATS Margin": "{:+.1f}",
    }).apply(lambda x: [
        'background-color: lightgreen; color: black' if v == '49ers' else 
        ('background-color: lightgray; color: black' if v == 'Raiders' else '') 
        for v in x
    ], subset=['Winner'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("No completed head-to-head weeks found yet for this season.")
    
