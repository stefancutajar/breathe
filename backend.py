from flask import Flask, request, redirect, jsonify
import requests
import os
import sqlite3
import json
from urllib.parse import urlencode

app = Flask(__name__)

# Config - set these environment variables or edit directly for local testing
SPOTIFY_CLIENT_ID = '99ed2c7a7c2a4912a301941033334d30'
SPOTIFY_CLIENT_SECRET ='c7c9db81f7da4a699c4bd49e57e4b73d'
REDIRECT_URI = 'http://127.0.0.1:5000/callback'
DB_PATH = 'spotify_demo.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Users table
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        spotify_id TEXT UNIQUE,
        display_name TEXT,
        email TEXT,
        data JSON
    )
    ''')
    # Songs table
    c.execute('''
    CREATE TABLE IF NOT EXISTS songs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_spotify_id TEXT,
        track_id TEXT,
        track_name TEXT,
        artist_name TEXT,
        album_name TEXT,
        spotify_url TEXT,
        album_url TEXT,
        artist_url TEXT,
        FOREIGN KEY(user_spotify_id) REFERENCES users(spotify_id)
    )
    ''')
    conn.commit()
    conn.close()

def save_user(spotify_id, display_name, email, data):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Save user
    c.execute('''INSERT OR REPLACE INTO users (spotify_id, display_name, email, data) VALUES (?, ?, ?, ?)''',
              (spotify_id, display_name, email, json.dumps(data)))
    # Remove old songs for this user (if any)
    c.execute('DELETE FROM songs WHERE user_spotify_id = ?', (spotify_id,))
    # Save top tracks
    tracks = data.get('top_tracks', {}).get('items', [])
    for track in tracks:
        track_id = track.get('id')
        track_name = track.get('name')
        # Get first artist (main)
        artist = track.get('artists', [{}])[0]
        artist_name = artist.get('name')
        artist_url = artist.get('external_urls', {}).get('spotify')
        album = track.get('album', {})
        album_name = album.get('name')
        album_url = album.get('external_urls', {}).get('spotify')
        spotify_url = track.get('external_urls', {}).get('spotify')
        c.execute('''INSERT INTO songs (user_spotify_id, track_id, track_name, artist_name, album_name, spotify_url, album_url, artist_url)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?)''',
                  (spotify_id, track_id, track_name, artist_name, album_name, spotify_url, album_url, artist_url))
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

    # Exchange code for access token (send client credentials as HTTP Basic Auth)
    import base64
    token_url = 'https://accounts.spotify.com/api/token'
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': REDIRECT_URI,
    }
    client_creds = f"{SPOTIFY_CLIENT_ID}:{SPOTIFY_CLIENT_SECRET}"
    b64_creds = base64.b64encode(client_creds.encode()).decode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {b64_creds}',
    }
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