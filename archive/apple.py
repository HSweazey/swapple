import requests

def get_apple_music_info(song_title: str, artist: str) -> dict | None:
    """
    Searches Apple Music via the public iTunes Search API.
    Returns Apple Music URL, track name, artist name, and high-res album art.
    """
    endpoint = "https://itunes.apple.com/search"
    params = {
        "term": f"{song_title} {artist}",
        "media": "music",
        "entity": "song",
        "limit": 1
    }
    
    try:
        response = requests.get(endpoint, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return None
            
        track = results[0]
        
        # Upgrade artwork resolution from 100x100 to 600x600
        artwork_url = track.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
        
        return {
            "apple_url": track.get("trackViewUrl"),
            "title": track.get("trackName"),
            "artist": track.get("artistName"),
            "album_art": artwork_url
        }
        
    except Exception as e:
        print(f"iTunes API Error: {e}")
        return None