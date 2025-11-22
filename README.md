# Spotify OAuth Demo (Streamlit + Flask)

This small demo shows how to initiate a Spotify OAuth sign-in from a Streamlit frontend and handle the OAuth callback in a Flask backend which saves user data to a SQLite database.

Files added:
- `streamlit_app.py` - Streamlit frontend which opens the Spotify authorization URL.
- `backend.py` - Flask app that handles the `/callback` route, exchanges the code for tokens, fetches profile and top tracks, and saves to `spotify_demo.db`.
- `requirements.txt` - Python dependencies.

Quick start

1. Create a Spotify Developer app at https://developer.spotify.com/dashboard and add a Redirect URI: `http://127.0.0.1:5000/callback`.
2. Set environment variables (or edit files directly for local testing):

   - `SPOTIFY_CLIENT_ID`
   - `SPOTIFY_CLIENT_SECRET`

   Example (zsh):

   ```bash
   export SPOTIFY_CLIENT_ID=99ed2c7a7c2a4912a301941033334d30
   export SPOTIFY_CLIENT_SECRET=c7c9db81f7da4a699c4bd49e57e4b73d
   ```

3. Install dependencies:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

4. Start the Flask backend:

   ```bash
   python backend.py
   ```

5. In another terminal start Streamlit:

   ```bash
   streamlit run streamlit_app.py
   ```

6. Click "Log in with Spotify" in the Streamlit UI. Spotify will prompt for authorization. After approval, the Flask backend will exchange the code, fetch data, and store it in `spotify_demo.db`.

Notes and next steps

- This demo stores the entire JSON data in a single column; for production you should normalize schema and avoid storing secrets.
- Use HTTPS and proper secret management for production.
- Add CSRF/state verification, token refresh, and better error handling.
# breathe
