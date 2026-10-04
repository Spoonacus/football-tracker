import streamlit as st
import pandas as pd
import requests
import datetime
import os

st.set_page_config(page_title="Ghost Bowl ATS", page_icon="👻", layout="centered", initial_sidebar_state="collapsed")

# --- CUSTOM UI CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    .block-container {padding-top: 0.5rem !important; padding-bottom: 1rem !important; padding-left: 0.5rem !important; padding-right: 0.5rem !important;}
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

@st.cache_data(ttl=60) # Caches for only 60 seconds so live scores update fast
def fetch_current_week():
    # Calling the base scoreboard endpoint without a week parameter gives us ESPN's "Current Active Week"
    url = "http://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard"
    resp = requests.get(url)
    if resp.status_code != 200: 
        return None, None
    data = resp.json()
    
    sf_data, lv_data = None, None
    
    for event in data.get('events', []):
        comp = event['competitions'][0]
        teams = comp['competitors']
        team_abbrs = [t['team']['abbreviation'] for t in teams]
        
        if 'SF' in team_abbrs or 'LV' in team_abbrs:
            state = comp['status']['type']['state']
            status_text = event['status']['type']['shortDetail'] # e.g. "Sun 1:05 PM", "Q3 10:15", "Final"
            odds_str = comp.get('odds', [{}])[0].get('details', '') if comp.get('odds') else ''
            
            if not odds_str and state == 'post':
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
                my_team = next(t for t in teams if t['team']['abbreviation'] == 'SF')
                opp_team = next(t for t in teams if t['team']['abbreviation'] != 'SF')
                sf_data = {
                    'opp': opp_team['team']['abbreviation'], 'is_home': my_team['homeAway'] == 'home',
                    'state': state, 'status_text': status_text,
                    'my_score': my_team.get('score', '0'), 'opp_score': opp_team.get('score', '0'),
                    'spread': parse_spread(odds_str, 'SF')
                }
            
            if 'LV' in team_abbrs:
                my_team = next(t for t in teams if t['team']['abbreviation'] == 'LV')
                opp_team = next(t for t in teams if t['team']['abbreviation'] != 'LV')
                lv_data = {
                    'opp': opp_team['team']['abbreviation'], 'is_home': my_team['homeAway'] == 'home',
                    'state': state, 'status_text': status_text,
                    'my_score': my_team.get('score', '0'), 'opp_score': opp_team.get('score', '0'),
                    'spread': parse_spread(odds_str, 'LV')
                }
                
    return sf_data, lv_data

@st.cache_data(ttl=3600) # Caches for 1 hour because past history doesn't change
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
            
            # This line ensures the current week stays out of the table until the game is over
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

def build_live_card_html(team, bg_color, text_color, data):
    """Builds the HTML for the individual team's live scoreboard card"""
    if not data:
        return f"""<div style='background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 8px; width: 49%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2); border: 1px solid #444;'>
<div style='font-size: 0.85rem; font-weight: bold;'>{team}</div>
<div style='font-size: 1.1rem; padding: 10px 0;'>BYE WEEK</div>
</div>"""

    opp_prefix = "vs" if data['is_home'] else "@"
    spread_val = data['spread']
    spread_str = f"{spread_val:+.1f}" if spread_val != 0 else "PK"

    # Format text based on if game is upcoming vs live/final
    if data['state'] == 'pre':
        score_line = f"<div style='font-size: 0.95rem; font-weight: bold; margin: 8px 0;'>{data['status_text']}</div>"
    else:
        score_line = f"<div style='font-size: 1.4rem; font-weight: 900; margin: 2px 0;'>{data['my_score']} - {data['opp_score']}</div><div style='font-size: 0.75rem; color: {text_color}; opacity: 0.9;'>{data['status_text']}</div>"

    return f"""<div style='background-color: {bg_color}; color: {text_color}; padding: 8px; border-radius: 8px; width: 49%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2); border: 1px solid #444;'>
<div style='font-size: 0.75rem; font-weight: bold; letter-spacing: 0.5px;'>{team} {opp_prefix} {data['opp']}</div>
{score_line}
<div style='font-size: 0.75rem; margin-top: 5px; padding: 2px; background-color: rgba(255,255,255,0.15); border-radius: 4px;'>Spread: {spread_str}</div>
</div>"""

# --- BANNER IMAGE HEADER ---
if os.path.exists("1791152594772.jpg"):
    st.image("1791152594772.jpg", use_container_width=True)
elif os.path.exists("banner.jpg"):
    st.image("banner.jpg", use_container_width=True)
else:
    st.markdown("<h2 style='text-align: center;'>👻 Bay Bridge Ghost Bowl</h2>", unsafe_allow_html=True)

with st.spinner("Connecting to ESPN Live API..."):
    sf_live, lv_live = fetch_current_week()
    df = fetch_season_data()

# --- LIVE MATCHUP BANNER ---
live_html = f"""<div style='display: flex; justify-content: space-between; gap: 6px; margin-top: 5px; margin-bottom: 15px;'>
{build_live_card_html("49ERS", "#AA0000", "#FFFFFF", sf_live)}
{build_live_card_html("RAIDERS", "#000000", "#A5ACAF", lv_live)}
</div>"""
st.markdown(live_html, unsafe_allow_html=True)

if not df.empty:
    sf_wins = len(df[df["Winner"] == "49ers"])
    lv_wins = len(df[df["Winner"] == "Raiders"])
    ties = len(df[df["Winner"] == "Tie"])
    
    # Season Scoreboard Cards
    scoreboard_html = f"""<div style='display: flex; justify-content: space-between; gap: 8px; margin-top: 10px; margin-bottom: 12px;'>
<div style='background-color: #AA0000; color: #B3995D; padding: 8px; border-radius: 8px; width: 32%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2);'>
<div style='font-size: 0.75rem; font-weight: bold; color: white;'>SF WINS</div>
<div style='font-size: 1.8rem; font-weight: 900; line-height: 1.2;'>{sf_wins}</div>
</div>
<div style='background-color: #f0f2f6; color: black; padding: 8px; border-radius: 8px; width: 32%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2);'>
<div style='font-size: 0.75rem; font-weight: bold; color: #555;'>TIES</div>
<div style='font-size: 1.8rem; font-weight: 900; line-height: 1.2;'>{ties}</div>
</div>
<div style='background-color: #000000; color: #A5ACAF; padding: 8px; border-radius: 8px; width: 32%; text-align: center; box-shadow: 1px 1px 4px rgba(0,0,0,0.2);'>
<div style='font-size: 0.75rem; font-weight: bold; color: white;'>LV WINS</div>
<div style='font-size: 1.8rem; font-weight: 900; line-height: 1.2;'>{lv_wins}</div>
</div>
</div>"""
    st.markdown(scoreboard_html, unsafe_allow_html=True)
    
    if sf_wins > lv_wins:
        st.success("🔥 The **49ers** currently own the Bay Bridge!")
    elif lv_wins > sf_wins:
        st.success("🏴‍☠️ The **Raiders** currently own the Bay Bridge!")
    else:
        st.info("⚖️ The Ghost Bowl is currently a dead heat!")

    # Custom Table Rows
    table_rows = ""
    for index, row in df.iterrows():
        sf_class = "win-sf" if row['Winner'] == '49ers' else ""
        lv_class = "win-lv" if row['Winner'] == 'Raiders' else ""
        
        if row['Winner'] == '49ers': win_badge = "🔴 SF"
        elif row['Winner'] == 'Raiders': win_badge = "⚫ LV"
        else: win_badge = "Tie"

        table_rows += f"""<tr>
<td style="font-weight: bold;">{row['Week']}</td>
<td class="{sf_class}">{row['49ers Spread']:+.1f}</td>
<td class="{sf_class}">{row['49ers ATS Margin']:+.1f}</td>
<td class="{lv_class}">{row['Raiders Spread']:+.1f}</td>
<td class="{lv_class}">{row['Raiders ATS Margin']:+.1f}</td>
<td style="font-size: 0.75rem; font-weight: bold;">{win_badge}</td>
</tr>"""

    table_html = f"""<style>
.ghost-table {{ width: 100%; border-collapse: collapse; text-align: center; font-size: 0.85rem; font-family: sans-serif; margin-top: 10px; }}
.ghost-table th, .ghost-table td {{ padding: 6px 3px; border: 1px solid #ddd; }}
.sf-head {{ background-color: #AA0000; color: #B3995D; font-weight: bold; border: 1px solid #770000 !important; }}
.lv-head {{ background-color: #000000; color: #A5ACAF; font-weight: bold; border: 1px solid #333 !important; }}
.sub-head {{ background-color: #f8f9fa; font-size: 0.7rem; color: #555; }}
.win-sf {{ background-color: #fff0f0; font-weight: bold; color: #AA0000; }}
.win-lv {{ background-color: #f0f0f0; font-weight: bold; color: black; }}
</style>
<table class='ghost-table'>
<thead>
<tr>
<th rowspan="2" style="background-color: #f8f9fa;">Wk</th>
<th colspan="2" class="sf-head">49ERS</th>
<th colspan="2" class="lv-head">RAIDERS</th>
<th rowspan="2" style="background-color: #f8f9fa;">Win</th>
</tr>
<tr class="sub-head">
<th>Spread</th>
<th>ATS</th>
<th>Spread</th>
<th>ATS</th>
</tr>
</thead>
<tbody>
{table_rows}
</tbody>
</table>"""

    st.markdown(table_html, unsafe_allow_html=True)

else:
    st.info("No completed head-to-head weeks found yet for this season.")
    
