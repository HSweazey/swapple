import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from keys import CLIENT_ID, CLIENT_SECRET

def get_spotify_track_info(song_title: str, artist: str, client_id: str, client_secret: str) -> dict | None:
    """
    Searches Spotify for a song and artist.
    Returns track ID, Spotify web link, track name, artist name, and high-res album art.
    """
    try:
        # Authenticate using Client Credentials flow
        auth_manager = SpotifyClientCredentials(
            client_id=client_id, 
            client_secret=client_secret
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        # Build precise search query
        query = f"track:{song_title} artist:{artist}"
        results = sp.search(q=query, type="track", limit=1)
        
        items = results.get("tracks", {}).get("items", [])
        if not items:
            # Fallback search without explicit tags if exact query misses
            results = sp.search(q=f"{song_title} {artist}", type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            
        if not items:
            return None
            
        track = items[0]
        
        return {
            "spotify_id": track["id"],
            "spotify_url": track["external_urls"]["spotify"],
            "title": track["name"],
            "artist": track["artists"][0]["name"],
            "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None
        }
        
    except Exception as e:
        print(f"Spotify API Error: {e}")
        return None