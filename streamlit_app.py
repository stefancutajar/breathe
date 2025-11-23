import streamlit as st
import webbrowser
import urllib.parse
import requests
import pandas as pd
import altair as alt
import time

# Configuration - set these in your env or edit for local testing
SPOTIFY_CLIENT_ID = '99ed2c7a7c2a4912a301941033334d30'
BACKEND_BASE = "http://127.0.0.1:5000"


def fetch_json(path, params=None, timeout=5):
    try:
        r = requests.get(BACKEND_BASE + path, params=params, timeout=timeout)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        st.error(f"Failed to load {path}: {e}")
        return None

def show_kpis():
    data = fetch_json('/stats/kpis')
    if not data:
        return
    cols = st.columns(3)
    cols[0].metric('Total users', data.get('total_users'))
    cols[1].metric('Total songs (all)', data.get('total_songs'))
    avg = data.get('avg_songs_per_user')
    cols[2].metric('Avg songs per user', f"{avg:.1f}" if avg is not None else 'n/a')

def show_songs_dataset():
    data = fetch_json('/stats/songs')
    if not data or (isinstance(data, dict) and data.get('error')):
        st.error('Failed to load songs dataset.')
        return
    import pandas as pd
    df = pd.DataFrame(data)
    # Only keep and order the specified columns
    cols = ['user_spotify_id', 'track_id', 'track_name', 'artist_name', 'album_name']
    df = df[cols]
    st.subheader('Songs Dataset (from DB)')
    st.dataframe(df)

def show_top_songs(limit=5):
    data = fetch_json('/stats/top-songs', params={'limit': limit})
    if not data:
        return
    df = pd.DataFrame(data)
    if df.empty:
        st.write('No top songs yet')
        return
    st.subheader('Top 5 songs (ML model, probability density)')
    # Ensure probability column is present and sorted descending
    df = df.sort_values('probability', ascending=False)
    c = alt.Chart(df).mark_bar().encode(
        x=alt.X('probability:Q', title='Probability', scale=alt.Scale(domain=[0, 1])),
        y=alt.Y('track_name:N', sort='-x', title='Track'),
        tooltip=['track_name', 'artist_name', alt.Tooltip('probability:Q', format='.3f')]
    ).properties(height=300)
    st.altair_chart(c, use_container_width=True)
    # Show table with probabilities
    df['probability'] = df['probability'].map(lambda x: f"{x:.3f}")
    st.table(df[['track_name', 'artist_name', 'probability']].head(limit))

def show_genre_bubbles(max_bubbles=40):
    data = fetch_json('/stats/genres')
    if not data:
        return
    df = pd.DataFrame(data)
    if df.empty:
        st.write('No genre data yet')
        return
    st.subheader('Genres (bubble size = count)')
    # limit number of bubbles to keep chart readable
    df = df.head(max_bubbles)
    df['x'] = range(len(df))
    chart = alt.Chart(df).mark_circle().encode(
        x='x:Q',
        y=alt.Y('count:Q', title='Count'),
        size=alt.Size('count:Q', legend=None),
        color=alt.Color('genre:N', legend=None),
        tooltip=['genre', 'count']
    ).properties(height=350)
    st.altair_chart(chart, use_container_width=True)

def main():
    st.title("breathe")

    # Detect login state: use session_state and query param
    if 'logged_in' not in st.session_state:
        # Check for ?logged_in=1 in URL (after OAuth callback)
        query_params = st.experimental_get_query_params()
        st.session_state['logged_in'] = query_params.get('logged_in', ['0'])[0] == '1'

    # LOGOUT button logic
    if st.session_state.get('logged_in', False):
        if st.button("Log out"):
            st.session_state.clear()
            st.experimental_set_query_params()  # Clear query params
            st.experimental_rerun()

    # LOGIN PAGE: Only show login button if not logged in
    if not st.session_state.get('logged_in', False):
        params = {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": f"{BACKEND_BASE}/callback",
            "scope": "user-read-private user-read-email user-top-read playlist-read-private",
            "state": "streamlit_demo_state",
        }
        url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
        st.markdown(f'<a href="{url}" target="_self"><button style="font-size:1.2em;padding:0.5em 1.5em;">Log in with Spotify</button></a>', unsafe_allow_html=True)
        st.markdown('---')
        st.caption(f"This demo uses a Flask backend running at {BACKEND_BASE} to receive the OAuth callback and store data in a SQLite DB.")
        return

    # DASHBOARD PAGE: Only show after login
    data = fetch_json('/stats/kpis')
    if data and (data.get('total_users', 0) > 0 or data.get('simulation_songs', 0) > 0):
        show_kpis()
        show_top_songs(limit=5)
        show_genre_bubbles()
        show_songs_dataset()
    else:
        st.info('No analytics data yet. After logging in with Spotify, the dashboard will populate automatically.')

    st.markdown('---')
    st.caption(f"This demo uses a Flask backend running at {BACKEND_BASE} to receive the OAuth callback and store data in a SQLite DB.")


if __name__ == '__main__':
    main()
