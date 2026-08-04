from archive.spotify import get_spotify_track_info
from archive.apple import get_apple_music_info

def fetch_song_data(song_title: str, artist: str, spotify_client_id: str, spotify_client_secret: str) -> dict | None:
    """
    Queries both Spotify and Apple Music APIs and merges the results.
    """
    spotify_data = get_spotify_track_info(song_title, artist, spotify_client_id, spotify_client_secret)
    apple_data = get_apple_music_info(song_title, artist)
    
    # If neither service found a match, return None
    if not spotify_data and not apple_data:
        return None
        
    # Combine results, prioritizing Spotify for title/artwork fallback
    return {
        "title": spotify_data["title"] if spotify_data else apple_data["title"],
        "artist": spotify_data["artist"] if spotify_data else apple_data["artist"],
        "spotify_id": spotify_data["spotify_id"] if spotify_data else "",
        "spotify_url": spotify_data["spotify_url"] if spotify_data else "",
        "apple_url": apple_data["apple_url"] if apple_data else "",
        "album_art": spotify_data["album_art"] if spotify_data else apple_data["album_art"]
    }