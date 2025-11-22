import csv
import sqlite3
import json
from pathlib import Path

DB_PATH = 'spotify_demo.db'
CSV_PATH = 'dataset.csv'

def load_top_songs(limit=10000):
    """Load top unique songs by popularity from the CSV."""
    path = Path(CSV_PATH)
    if not path.exists():
        raise FileNotFoundError(f"{CSV_PATH} not found")

    songs = []
    seen = set()
    with open(CSV_PATH, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        # CSV has a leading unnamed index column; ensure 'track_id' exists
        for row in reader:
            try:
                pop = int(row.get('popularity', 0))
            except Exception:
                pop = 0
            track_id = row.get('track_id')
            if not track_id or track_id in seen:
                continue
            seen.add(track_id)
            songs.append((pop, track_id, row))

    # sort by popularity desc
    songs.sort(key=lambda x: x[0], reverse=True)
    top = songs[:limit]
    # return list of dicts (track info)
    return [item[2] for item in top]

def create_simulation_table(conn):
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS songs_simulation (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        track_id TEXT,
        track_name TEXT,
        artist_name TEXT,
        album_name TEXT,
        popularity INTEGER
    )
    ''')
    conn.commit()

def populate_simulation(conn, top_songs, num_users=5000, songs_per_user=50):
    c = conn.cursor()
    total_top = len(top_songs)
    if total_top < songs_per_user:
        raise ValueError('Not enough top songs to choose from')

    # We'll use a deterministic but well-distributed selection using modular arithmetic.
    # For user i (0-based) pick songs at indices: (i * step + j) % total_top
    # Choose step to be a large prime-ish number relative to total_top to spread picks.
    step = 7919  # prime

    for i in range(num_users):
        user_id = f'sim_user_{i+1}'
        base = (i * step) % total_top
        picks = set()
        j = 0
        while len(picks) < songs_per_user:
            idx = (base + j) % total_top
            picks.add(idx)
            j += 1

        for idx in picks:
            row = top_songs[idx]
            track_id = row.get('track_id')
            track_name = row.get('track_name') or row.get('track_name')
            artist_name = row.get('artists')
            album_name = row.get('album_name')
            try:
                popularity = int(row.get('popularity') or 0)
            except Exception:
                popularity = 0
            c.execute('''INSERT INTO songs_simulation (user_id, track_id, track_name, artist_name, album_name, popularity)
                         VALUES (?, ?, ?, ?, ?, ?)''',
                      (user_id, track_id, track_name, artist_name, album_name, popularity))

    conn.commit()

def main():
    print('Loading top songs...')
    top = load_top_songs(limit=10000)
    print(f'Loaded {len(top)} top unique songs')

    conn = sqlite3.connect(DB_PATH)
    create_simulation_table(conn)
    print('Populating simulation table (this may take a minute)...')
    populate_simulation(conn, top, num_users=5000, songs_per_user=50)
    print('Done. Closing DB.')
    conn.close()

if __name__ == '__main__':
    main()
