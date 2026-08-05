import streamlit as st
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
from PIL import Image
import streamlit.components.v1 as components
import os

# --- PAGE SETUP & AESTHETICS ---
# Fallback to emoji if icon.png isn't found locally yet
if os.path.exists("icon.png"):
    icon_img = Image.open("icon.png")
    st.set_page_config(page_title="Our Music Hub", page_icon=icon_img, layout="centered")
else:
    st.set_page_config(page_title="Our Music Hub", page_icon="🌸", layout="centered")

# Inject Javascript to override the mobile home screen icon
components.html(
    f"""
    <script>
        const doc = window.parent.document;
        const existingIcons = doc.querySelectorAll('link[rel="apple-touch-icon"]');
        existingIcons.forEach(icon => icon.remove());
        const newIcon = doc.createElement('link');
        newIcon.rel = 'apple-touch-icon';
        // PASTE YOUR RAW GITHUB IMAGE URL BELOW
        newIcon.href = 'https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/our-music-hub/main/icon.png';
        doc.head.appendChild(newIcon);
    </script>
    """,
    height=0,
    width=0,
)

st.markdown("""
    <style>
    /* Pastel pink background */
    .stApp {
        background-color: #FDF1F4; 
    }
    /* Rounded corners for inputs */
    div[data-baseweb="input"] > div, div[data-baseweb="radio"] {
        border-radius: 20px !important;
    }
    div[data-baseweb="input"] > div {
        border: 1px solid #FFC0CB !important;
        background-color: white !important;
    }
    /* Rounded buttons */
    div.stButton > button:first-child {
        border-radius: 20px;
        background-color: #FFB6C1;
        color: white;
        border: none;
        font-weight: bold;
        transition: 0.3s;
    }
    div.stButton > button:first-child:hover {
        background-color: #FF69B4;
    }
    /* Gallery cards */
    .gallery-card {
        background-color: white;
        padding: 20px;
        border-radius: 24px;
        box-shadow: 0 4px 15px rgba(255, 182, 193, 0.2);
        text-align: center;
        margin-bottom: 10px; 
        border: 2px solid #FFF0F5;
    }
    /* Cute links */
    .link-container {
        display: flex;
        justify-content: center;
        gap: 10px;
        margin-top: 15px;
    }
    .apple-link, .spotify-link {
        padding: 8px 16px;
        text-decoration: none;
        border-radius: 15px;
        font-weight: bold;
        font-size: 13px;
        transition: 0.2s;
    }
    .apple-link {
        background-color: #FFE4E1;
        color: #FF69B4;
    }
    .apple-link:hover {
        background-color: #FFB6C1;
        color: white;
    }
    .spotify-link {
        background-color: #E8F5E9;
        color: #1DB954;
    }
    .spotify-link:hover {
        background-color: #1DB954;
        color: white;
    }
    /* Center the Streamlit checkboxes under the cards */
    .stCheckbox {
        display: flex;
        justify-content: center;
        margin-bottom: 25px;
    }
    /* Style the tabs */
    button[data-baseweb="tab"] {
        font-size: 18px !important;
        font-weight: bold !important;
    }
    </style>
""", unsafe_allow_html=True)

# --- API FUNCTIONS ---
def get_spotify_track_info(song_title: str, artist: str) -> dict | None:
    try:
        auth_manager = SpotifyClientCredentials(
            client_id=st.secrets["SPOTIFY_CLIENT_ID"], 
            client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"]
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
        
        query = f"track:{song_title} artist:{artist}"
        results = sp.search(q=query, type="track", limit=1)
        items = results.get("tracks", {}).get("items", [])
        
        if not items:
            results = sp.search(q=f"{song_title} {artist}", type="track", limit=1)
            items = results.get("tracks", {}).get("items", [])
            
        if not items: return None
        track = items[0]
        
        return {
            "spotify_id": track["id"],
            "spotify_url": track["external_urls"]["spotify"],
            "title": track["name"],
            "artist": track["artists"][0]["name"],
            "album_art": track["album"]["images"][0]["url"] if track["album"]["images"] else None
        }
    except Exception as e:
        st.error(f"Spotify API Error: {e}")
        return None

def get_apple_music_info(song_title: str, artist: str) -> dict | None:
    endpoint = "https://itunes.apple.com/search"
    params = {"term": f"{song_title} {artist}", "media": "music", "entity": "song", "limit": 1}
    try:
        response = requests.get(endpoint, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results: return None
        
        track = results[0]
        artwork_url = track.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
        
        return {
            "apple_url": track.get("trackViewUrl"),
            "title": track.get("trackName"),
            "artist": track.get("artistName"),
            "album_art": artwork_url
        }
    except Exception as e:
        st.error(f"iTunes API Error: {e}")
        return None

def fetch_song_data(song_title: str, artist: str) -> dict | None:
    spotify_data = get_spotify_track_info(song_title, artist)
    apple_data = get_apple_music_info(song_title, artist)
    
    if not spotify_data and not apple_data:
        return None
        
    return {
        "Title": spotify_data["title"] if spotify_data else apple_data["title"],
        "Artist": spotify_data["artist"] if spotify_data else apple_data["artist"],
        "Spotify ID": spotify_data["spotify_id"] if spotify_data else "",
        "Spotify URL": spotify_data["spotify_url"] if spotify_data else "",
        "Apple URL": apple_data["apple_url"] if apple_data else "",
        "Album Art": spotify_data["album_art"] if spotify_data else apple_data["album_art"],
        "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M")
    }

# --- MAIN APP UI ---
st.title("🌸 Our Music Hub 🌸")

# Initialize Google Sheets Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# Set ttl=0 so it pulls live data on startup, bypassing the cache
df = conn.read(worksheet="Sheet1", ttl=0)

expected_columns = ["Title", "Artist", "Spotify ID", "Spotify URL", "Apple URL", "Album Art", "Date Added", "Playlist", "Listened"]
if df.empty or len(df.columns) == 0:
    df = pd.DataFrame(columns=expected_columns)

# --- INPUT SECTION ---
with st.container():
    st.write("### Drop a new rec! 🎧")
    col1, col2 = st.columns(2)
    with col1:
        song_input = st.text_input("Song Title", placeholder="e.g. Pink Pony Club")
    with col2:
        artist_input = st.text_input("Artist", placeholder="e.g. Chappell Roan")
        
    playlist_selection = st.radio("Whose playlist is this for?", ["Hannah", "Alyssa"], horizontal=True)
        
    if st.button("Search & Save ✨"):
        if song_input and artist_input:
            with st.spinner("Hunting for the tracks..."):
                new_song = fetch_song_data(song_input, artist_input)
                
                if new_song:
                    new_song["Playlist"] = playlist_selection
                    new_song["Listened"] = False 
                    
                    if not df.empty and new_song["Spotify ID"] in df["Spotify ID"].values and new_song["Spotify ID"] != "":
                        st.warning(f"You already have '{new_song['Title']}' in the vault!")
                    else:
                        new_row_df = pd.DataFrame([new_song])
                        updated_df = pd.concat([new_row_df, df], ignore_index=True)
                        conn.update(worksheet="Sheet1", data=updated_df)
                        
                        st.success(f"Added '{new_song['Title']}' to {playlist_selection}'s vault! 🎉")
                        # Clear cache and instantly refresh to show new data
                        st.cache_data.clear()
                        st.rerun()
                else:
                    st.error("Couldn't find that exact song. Check the spelling and try again!")

st.divider()

# --- GALLERY VIEW (TABS) ---
st.write("### The Vault 💖")

# Read the sheet again, explicitly setting ttl=0 to bypass cache
df = conn.read(worksheet="Sheet1", ttl=0)
df = df.dropna(subset=["Title", "Artist"]) 

if not df.empty:
    if "Listened" not in df.columns:
        df["Listened"] = False
    df["Listened"] = df["Listened"].fillna(False).astype(bool)
    
    # Sort the dataframe: Unlistened (False) at top, then by Date Added (Newest first)
    df = df.sort_values(by=["Listened", "Date Added"], ascending=[True, False]).reset_index(drop=True)
    
    # Split the dataframe for each tab
    df_hannah = df[df["Playlist"] == "Hannah"]
    df_alyssa = df[df["Playlist"] == "Alyssa"]
    
    tab_hannah, tab_alyssa = st.tabs(["🌸 Hannah's List", "🎧 Alyssa's List"])
    
    # --- HANNAH'S TAB ---
    with tab_hannah:
        if df_hannah.empty:
            st.info("Hannah's vault is empty!")
        else:
            for index, row in df_hannah.iterrows():
                title = row.get("Title", "Unknown")
                artist = row.get("Artist", "Unknown")
                spotify_id = row.get("Spotify ID", "")
                spotify_url = row.get("Spotify URL", "")
                apple_url = row.get("Apple URL", "")
                current_status = row.get("Listened", False)
                
                # Render the HTML Card
                card_html = f"""<div class="gallery-card" style="opacity: {'0.6' if current_status else '1.0'};">
<h4 style="margin-bottom: 5px; margin-top: 0px; color: #333;">{title}</h4>
<p style="margin-top: 0px; margin-bottom: 15px; color: #666; font-style: italic;">{artist}</p>"""
                
                # Embed Spotify
                if pd.notna(spotify_id) and spotify_id != "":
                    card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="https://open.spotify.com/embed/track/{spotify_id}" width="100%" height="80" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>"""
                
                # Embed Apple Music
                if pd.notna(apple_url) and apple_url != "":
                    apple_embed_url = apple_url.replace("music.apple.com", "embed.music.apple.com")
                    card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="{apple_embed_url}" width="100%" height="150" frameBorder="0" allowfullscreen="" allow="autoplay *; encrypted-media *;" loading="lazy"></iframe>"""
                
                card_html += '<div class="link-container">'
                if pd.notna(apple_url) and apple_url != "":
                    card_html += f'<a href="{apple_url}" target="_blank" class="apple-link">Apple 🍎</a>'
                if pd.notna(spotify_url) and spotify_url != "":
                    card_html += f'<a href="{spotify_url}" target="_blank" class="spotify-link">Spotify 🟢</a>'
                card_html += '</div></div>'
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                unique_key = f"h_listened_{spotify_id}_{index}"
                new_status = st.checkbox("Mark as Listened ✔️" if not current_status else "Listened 🎧", 
                                         value=current_status, 
                                         key=unique_key)
                
                if new_status != current_status:
                    df.at[index, "Listened"] = new_status
                    conn.update(worksheet="Sheet1", data=df)
                    st.cache_data.clear()
                    st.rerun()

    # --- ALYSSA'S TAB ---
    with tab_alyssa:
        if df_alyssa.empty:
            st.info("Alyssa's vault is empty!")
        else:
            for index, row in df_alyssa.iterrows():
                title = row.get("Title", "Unknown")
                artist = row.get("Artist", "Unknown")
                spotify_id = row.get("Spotify ID", "")
                spotify_url = row.get("Spotify URL", "")
                apple_url = row.get("Apple URL", "")
                current_status = row.get("Listened", False)
                
                # Render the HTML Card
                card_html = f"""<div class="gallery-card" style="opacity: {'0.6' if current_status else '1.0'};">
<h4 style="margin-bottom: 5px; margin-top: 0px; color: #333;">{title}</h4>
<p style="margin-top: 0px; margin-bottom: 15px; color: #666; font-style: italic;">{artist}</p>"""
                
                # Embed Spotify
                if pd.notna(spotify_id) and spotify_id != "":
                    card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="https://open.spotify.com/embed/track/{spotify_id}" width="100%" height="80" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>"""
                
                # Embed Apple Music
                if pd.notna(apple_url) and apple_url != "":
                    apple_embed_url = apple_url.replace("music.apple.com", "embed.music.apple.com")
                    card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="{apple_embed_url}" width="100%" height="150" frameBorder="0" allowfullscreen="" allow="autoplay *; encrypted-media *;" loading="lazy"></iframe>"""
                
                card_html += '<div class="link-container">'
                if pd.notna(apple_url) and apple_url != "":
                    card_html += f'<a href="{apple_url}" target="_blank" class="apple-link">Apple 🍎</a>'
                if pd.notna(spotify_url) and spotify_url != "":
                    card_html += f'<a href="{spotify_url}" target="_blank" class="spotify-link">Spotify 🟢</a>'
                card_html += '</div></div>'
                
                st.markdown(card_html, unsafe_allow_html=True)
                
                unique_key = f"a_listened_{spotify_id}_{index}"
                new_status = st.checkbox("Mark as Listened ✔️" if not current_status else "Listened 🎧", 
                                         value=current_status, 
                                         key=unique_key)
                
                if new_status != current_status:
                    df.at[index, "Listened"] = new_status
                    conn.update(worksheet="Sheet1", data=df)
                    st.cache_data.clear()
                    st.rerun()

else:
    st.info("The vault is empty! Add your first track above. 🎶")