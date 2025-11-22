import streamlit as st
import webbrowser
import urllib.parse

# Configuration - these should be set by the user or via environment in production
SPOTIFY_CLIENT_ID = '99ed2c7a7c2a4912a301941033334d30'
BACKEND_BASE = "http://127.0.0.1:5000"

def main():
    st.title("Spotify OAuth demo")
    st.write("Click the button to log in with Spotify and authorize access to your music data.")

    if st.button("Log in with Spotify"):
        params = {
            "client_id": SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": f"{BACKEND_BASE}/callback",
            "scope": "user-read-private user-read-email user-top-read playlist-read-private",
            "state": "streamlit_demo_state",
        }
        url = "https://accounts.spotify.com/authorize?" + urllib.parse.urlencode(params)
        st.write("Opening Spotify sign-in page...")
        webbrowser.open(url)

    st.markdown("---")
    st.caption("This demo uses a Flask backend running at http://127.0.0.1:5000 to receive the OAuth callback and store data in a SQLite DB.")

if __name__ == '__main__':
    main()
