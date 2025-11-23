from flask import Flask, request, redirect, jsonify
import requests
import os
import sqlite3
import json
from urllib.parse import urlencode
import csv
from pathlib import Path
CSV_PATH = 'dataset.csv'

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
    # Artists table
    c.execute('''
    CREATE TABLE IF NOT EXISTS artists (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_spotify_id TEXT,
        artist_id TEXT,
        artist_name TEXT,
        popularity INTEGER,
        genres TEXT,
        followers INTEGER,
        spotify_url TEXT,
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
    # Remove old songs and artists for this user (if any)
    c.execute('DELETE FROM songs WHERE user_spotify_id = ?', (spotify_id,))
    c.execute('DELETE FROM artists WHERE user_spotify_id = ?', (spotify_id,))
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
    # Save top artists
    artists = data.get('top_artists', {}).get('items', [])
    for artist in artists:
        artist_id = artist.get('id')
        artist_name = artist.get('name')
        popularity = artist.get('popularity')
        genres = ', '.join(artist.get('genres', []))
        followers = artist.get('followers', {}).get('total')
        spotify_url = artist.get('external_urls', {}).get('spotify')
        c.execute('''INSERT INTO artists (user_spotify_id, artist_id, artist_name, popularity, genres, followers, spotify_url)
                     VALUES (?, ?, ?, ?, ?, ?, ?)''',
                  (spotify_id, artist_id, artist_name, popularity, genres, followers, spotify_url))
# New endpoint to return all artists like /stats/songs
@app.route('/stats/artists')
def stats_artists():
    """Return all rows from the artists table as JSON array."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM artists')
        columns = [desc[0] for desc in c.description]
        rows = c.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()
    return jsonify(result)
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
    top_tracks = requests.get('https://api.spotify.com/v1/me/top/tracks?limit=50&time_range=short_term', headers={'Authorization': f'Bearer {access_token}'})
    top_tracks_data = top_tracks.json() if top_tracks.status_code == 200 else {'error': top_tracks.text}

    # Fetch user's top artists (short term)
    top_artists = requests.get('https://api.spotify.com/v1/me/top/artists?limit=50&time_range=short_term', headers={'Authorization': f'Bearer {access_token}'})
    top_artists_data = top_artists.json() if top_artists.status_code == 200 else {'error': top_artists.text}

    # Save into DB
    spotify_id = profile_data.get('id')
    display_name = profile_data.get('display_name')
    email = profile_data.get('email')
    data = {
        'profile': profile_data,
        'top_tracks': top_tracks_data,
        'top_artists': top_artists_data,
        'token_info': token_data
    }

    try:
        save_user(spotify_id, display_name, email, data)
    except Exception as e:
        return f"DB save failed: {e}", 500

    # After saving, redirect back to the Streamlit frontend with ?logged_in=1 so the user sees the dashboard.
    STREAMLIT_BASE = os.environ.get('STREAMLIT_BASE') or 'http://127.0.0.1:8501'
    return redirect(f"{STREAMLIT_BASE}?logged_in=1")

@app.route('/stats/top-artists')
def stats_top_artists():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        row = c.execute('SELECT data FROM users ORDER BY id DESC LIMIT 1').fetchone()
        if not row:
            conn.close()
            return jsonify([])
        data = json.loads(row[0])
        artists = data.get('top_artists', {}).get('items', [])
        # Only keep relevant fields for dataframe
        result = []
        for artist in artists:
            result.append({
                'artist_name': artist.get('name'),
                'artist_id': artist.get('id'),
                'popularity': artist.get('popularity'),
                'genres': ', '.join(artist.get('genres', [])),
                'followers': artist.get('followers', {}).get('total'),
                'spotify_url': artist.get('external_urls', {}).get('spotify'),
            })
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()
    return jsonify(result)

    # After saving, redirect back to the Streamlit frontend with ?logged_in=1 so the user sees the dashboard.
    STREAMLIT_BASE = os.environ.get('STREAMLIT_BASE') or 'http://127.0.0.1:8501'
    return redirect(f"{STREAMLIT_BASE}?logged_in=1")

@app.route('/stats/songs')
def stats_songs():
    """Return all rows from the songs table as JSON array."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('SELECT * FROM songs')
        columns = [desc[0] for desc in c.description]
        rows = c.fetchall()
        result = [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        conn.close()
        return jsonify({'error': str(e)}), 500
    conn.close()
    return jsonify(result)

@app.route('/stats/top-songs')
def stats_top_songs():
    """Return ML model top-5 with normalized probabilities (density function)."""
    import math
    limit = int(request.args.get('limit', 5))
    candidate_pool = int(request.args.get('pool', 500))

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Build track -> set(user_id)
    track_users = {}
    try:
        for track_id, user_id in c.execute('SELECT track_id, user_spotify_id FROM songs'):
            if not track_id:
                continue
            track_users.setdefault(track_id, set()).add(user_id or 'real_unknown')
    except Exception:
        pass
    try:
        for track_id, user_id in c.execute('SELECT track_id, user_id FROM songs_simulation'):
            if not track_id:
                continue
            track_users.setdefault(track_id, set()).add(user_id or 'sim_unknown')
    except Exception:
        pass

    if not track_users:
        conn.close()
        return jsonify([])

    items_by_pop = sorted(track_users.items(), key=lambda kv: len(kv[1]), reverse=True)
    candidates = items_by_pop[:candidate_pool]
    sizes = {tid: len(users) for tid, users in candidates}
    sim_scores = {tid: 0.0 for tid, _ in candidates}
    n = len(candidates)
    for i in range(n):
        tid_i, users_i = candidates[i]
        size_i = sizes[tid_i]
        if size_i == 0:
            continue
        for j in range(i+1, n):
            tid_j, users_j = candidates[j]
            size_j = sizes[tid_j]
            if size_j == 0:
                continue
            inter = len(users_i & users_j)
            if inter == 0:
                continue
            sim = inter / math.sqrt(size_i * size_j)
            sim_scores[tid_i] += sim
            sim_scores[tid_j] += sim

    ranked = sorted([(tid, sim_scores.get(tid, 0.0), sizes.get(tid, 0)) for tid, _ in candidates], key=lambda x: (x[1], x[2]), reverse=True)

    # Normalize scores to sum to 1 (density function)
    top_n = []
    total_score = sum([score for _, score, _ in ranked[:limit]])
    for tid, score, pop in ranked[:limit]:
        prob = (score / total_score) if total_score > 0 else 0.0
        row = c.execute('SELECT track_name, artist_name FROM songs_simulation WHERE track_id = ? LIMIT 1', (tid,)).fetchone()
        if not row:
            row = c.execute('SELECT track_name, artist_name FROM songs WHERE track_id = ? LIMIT 1', (tid,)).fetchone()
        track_name = row[0] if row else None
        artist_name = row[1] if row else None
        top_n.append({'track_id': tid, 'track_name': track_name, 'artist_name': artist_name, 'probability': prob})

    conn.close()
    return jsonify(top_n)

def _load_genre_map():
    """Load a mapping track_id -> genre from CSV (cached per process)."""
    if not Path(CSV_PATH).exists():
        return {}
    # simple in-memory cache
    if hasattr(app, '_genre_map'):
        return app._genre_map
    genre_map = {}
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tid = row.get('track_id')
            genre = row.get('track_genre')
            if tid and genre:
                genre_map[tid] = genre
    app._genre_map = genre_map
    return genre_map

@app.route('/stats/genres')
def stats_genres():
    """Return genre counts aggregated from songs and songs_simulation using CSV genre map."""
    genre_map = _load_genre_map()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # collect track ids from both tables
    counts = {}
    for tbl in ('songs', 'songs_simulation'):
        try:
            for row in c.execute(f'SELECT track_id FROM {tbl}'):
                tid = row[0]
                genre = genre_map.get(tid, 'unknown')
                counts[genre] = counts.get(genre, 0) + 1
        except Exception:
            # table might not exist
            continue
    conn.close()
    # convert to list
    result = [{'genre': g, 'count': c} for g, c in counts.items()]
    # sort descending
    result.sort(key=lambda x: x['count'], reverse=True)
    return jsonify(result)

@app.route('/stats/kpis')
def stats_kpis():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Count distinct real Spotify users
    try:
        real_users = c.execute('SELECT COUNT(DISTINCT spotify_id) FROM users').fetchone()[0] or 0
    except Exception:
        real_users = 0
    # Count distinct simulated users (user_id in songs_simulation)
    try:
        sim_users = c.execute('SELECT COUNT(DISTINCT user_id) FROM songs_simulation').fetchone()[0] or 0
    except Exception:
        sim_users = 0
    total_users = real_users + sim_users

    # Count song rows from each table
    try:
        total_songs = c.execute('SELECT COUNT(*) FROM songs').fetchone()[0] or 0
    except Exception:
        total_songs = 0
    try:
        sim_songs = c.execute('SELECT COUNT(*) FROM songs_simulation').fetchone()[0] or 0
    except Exception:
        sim_songs = 0

    conn.close()
    total_songs_all = total_songs + sim_songs
    avg_songs_per_user = (total_songs_all / total_users) if total_users > 0 else None
    return jsonify({
        'total_users': total_users,
        'total_songs': total_songs_all,
        'avg_songs_per_user': avg_songs_per_user,
        'simulation_songs': sim_songs,
    })


if __name__ == '__main__':
    init_db()
    app.run(port=5000, debug=True)