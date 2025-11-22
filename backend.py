from flask import Flask, request, redirect, jsonify
import requests
import os
import sqlite3
import json
from urllib.parse import urlencode

app = Flask(__name__)

# Config - set these environment variables or edit directly for local testing
SPOTIFY_CLIENT_ID = os.environ.get('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.environ.get('SPOTIFY_CLIENT_SECRET')
REDIRECT_URI = os.environ.get('REDIRECT_URI') or 'http://127.0.0.1:5000/callback'
DB_PATH = os.environ.get('DB_PATH') or 'spotify_demo.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spotify_id TEXT UNIQUE,
        display_name TEXT,
        email TEXT,
        data JSON
    )
    ''')
    conn.commit()
    conn.close()

def save_user(spotify_id, display_name, email, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users (spotify_id, display_name, email, data) VALUES (?, ?, ?, ?)
    ''', (spotify_id, display_name, email, json.dumps(data)))
    conn.commit()
    conn.close()

@app.route('/')
def index():
    return "Spotify OAuth backend running. Configure your Streamlit frontend to open the authorize URL pointing to this app."

@app.route('/callback')
def callback():
    # Spotify sends code and state
    code = request.args.get('code')
    state = request.args.get('state')
    error = request.args.get('error')
    if error:
        return f"Error from Spotify: {error}", 400
    if not code:
        return "Missing code", 400

    # Exchange code for access token
    token_url = 'https://accounts.spotify.com/api/token'
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET,
    }
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    r = requests.post(token_url, data=payload, headers=headers)
    if r.status_code != 200:
        return f"Failed to get token: {r.text}", 500
    token_data = r.json()
    access_token = token_data.get('access_token')

    # Fetch user profile
    profile = requests.get('https://api.spotify.com/v1/me', headers={'Authorization': f'Bearer {access_token}'})
    if profile.status_code != 200:
        return f"Failed to get profile: {profile.text}", 500
    profile_data = profile.json()

    # Fetch user's top tracks (short term)
    top = requests.get('https://api.spotify.com/v1/me/top/tracks?limit=10', headers={'Authorization': f'Bearer {access_token}'})
    top_data = top.json() if top.status_code == 200 else {'error': top.text}

    # Save into DB
    spotify_id = profile_data.get('id')
    display_name = profile_data.get('display_name')
    email = profile_data.get('email')
    data = {'profile': profile_data, 'top_tracks': top_data, 'token_info': token_data}
    try:
        save_user(spotify_id, display_name, email, data)
    except Exception as e:
        return f"DB save failed: {e}", 500

    # Return a simple page to the user indicating success
    return f"<h2>Success!</h2><p>Saved data for Spotify user {display_name} ({spotify_id}). You can close this tab and return to the Streamlit app.</p>"

if __name__ == '__main__':
    init_db()
    app.run(port=5000, debug=True)
