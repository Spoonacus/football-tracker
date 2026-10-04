import streamlit as st
import pandas as pd
import requests
import datetime

# Added 'initial_sidebar_state="collapsed"' to hide the menu on mobile
st.set_page_config(page_title="Ghost Bowl ATS", page_icon="👻", layout="wide", initial_sidebar_state="collapsed")

# --- CUSTOM UI CSS ---
# This injects custom design rules, overriding Streamlit's default look
st.markdown("""
    <style>
    /* Hide the Streamlit top menu and footer for a native app feel */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Center the main dataframe headers */
    .col_heading {text-align: center !important;}
    </style>
""", unsafe_allow_html=True)

def parse_spread(odds_str, team_abbr):
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
            
            if 'SF' in team_abbrs or 'LV' in team_abbrs:
                odds_str = comp.get('odds', [{}])[0].get('details', '') if comp.get('odds') else ''
                
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
                        
                if 'SF' in team_abbrs:
                    sf_team = next(t for t in teams if t['team']['abbreviation'] == 'SF')
                    opp_team = next(t for t in teams if t['team']['abbreviation'] != 'SF')
                    sf_data = {'score': int(sf_team['score']), 'opp_score': int(opp_team['score']), 'spread': parse_spread(odds_str, 'SF')}
                
                if 'LV' in team_abbrs:
                    lv_team = next(t for t in teams if t['team']['abbreviation'] == 'LV')
                    opp_team = next(t for t in teams if t['team']['abbreviation'] != 'LV')
                    lv_data = {'score': int(lv_team['score']), 'opp_score': int(opp_team['score']), 'spread': parse_spread(odds_str, 'LV')}
        
        if sf_data and lv_data:
            sf_ats = (sf_data['score'] - sf_data['opp_score']) + sf_data['spread']
            lv_ats = (lv_data['score'] - lv_data['opp_score']) + lv_data['spread']
            
            if sf_ats > lv_ats: winner = "49ers"
            elif lv_ats > sf_ats: winner = "Raiders"
            else: winner = "Tie"
            
            results.append({
                "Week": week,
                "49ers Spread": sf_data['spread'], "49ers ATS Margin": sf_ats,
                "Raiders Spread": lv_data['spread'], "Raiders ATS Margin": lv_ats,
                "Winner": winner
            })
            
    return pd.DataFrame(results)

# --- CUSTOM HEADER UI ---
st.markdown("""
    <div style='text-align: center; padding-bottom: 20px;'>
        <h1 style='font-size: 2.5rem; margin-bottom: 0px;'>👻 Bay Bridge Ghost Bowl 🏈</h1>
        <p style='font-size: 1.1rem; color: #888;'>Against The Spread Household Tracker</p>
    </div>
""", unsafe_allow_html=True)

with st.spinner("Connecting to ESPN API..."):
    df = fetch_season_data()

# --- CUSTOM SCOREBOARD UI ---
if not df.empty:
    sf_wins = len(df[df["Winner"] == "49ers"])
    lv_wins = len(df[df["Winner"] == "Raiders"])
    ties = len(df[df["Winner"] == "Tie"])
    
    # We replace standard st.metrics with custom HTML cards for team colors
    scoreboard_html = f"""
    <div style='display: flex; justify-content: space-between; gap: 10px; margin-bottom: 20px;'>
        <div style='background-color: #AA0000; color: #B3995D; padding: 15px; border-radius: 10px; width: 32%; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);'>
            <div style='font-size: 0.9rem; font-weight: bold; color: white;'>49ERS</div>
            <div style='font-size: 2.5rem; font-weight: 900;'>{sf_wins}</div>
        </div>
        <div style='background-color: #A5ACAF; color: black; padding: 15px; border-radius: 10px; width: 32%; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.2);'>
            <div style='font-size: 0.9rem; font-weight: bold; color: black;'>TIES</div>
            <div style='font-size: 2.5rem; font-weight: 900;'>{ties}</div>
        </div>
        <div style='background-color: #000000; color: #A5ACAF; padding: 15px; border-radius: 10px; width: 32%; text-align: center; box-shadow: 2px 2px 5px rgba(0,0,0,0.2); border: 1px solid #A5ACAF;'>
            <div style='font-size: 0.9rem; font-weight: bold; color: white;'>RAIDERS</div>
            <div style='font-size: 2.5rem; font-weight: 900;'>{lv_wins}</div>
        </div>
    </div>
    """
    st.markdown(scoreboard_html, unsafe_allow_html=True)
    
    if sf_wins > lv_wins:
        st.success("🔥 The **49ers** currently own the Bay Bridge!")
    elif lv_wins > sf_wins:
        st.success("🏴‍☠️ The **Raiders** currently own the Bay Bridge!")
    else:
        st.info("⚖️ The Ghost Bowl is currently a dead heat!")

    st.markdown("<h3 style='text-align: center; padding-top: 10px;'>📊 Completed Weeks</h3>", unsafe_allow_html=True)
    
    # Table Formatting
    styled_df = df.style.format({
        "49ers Spread": "{:+.1f}", "49ers ATS Margin": "{:+.1f}",
        "Raiders Spread": "{:+.1f}", "Raiders ATS Margin": "{:+.1f}",
    }).apply(lambda x: [
        'background-color: #ffcccc; color: black; font-weight: bold' if v == '49ers' else 
        ('background-color: #e6e6e6; color: black; font-weight: bold' if v == 'Raiders' else '') 
        for v in x
    ], subset=['Winner'])
    
    st.dataframe(styled_df, use_container_width=True, hide_index=True)
else:
    st.info("No completed head-to-head weeks found yet for this season.")
    
