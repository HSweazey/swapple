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
import re

# --- PAGE SETUP & AESTHETICS ---
if os.path.exists("icon.png"):
    icon_img = Image.open("icon.png")
    st.set_page_config(page_title="Swapple", page_icon=icon_img, layout="centered")
else:
    st.set_page_config(page_title="Swapple", page_icon="🌸", layout="centered")

components.html(
    f"""
    <script>
        const doc = window.parent.document;
        const existingIcons = doc.querySelectorAll('link[rel="apple-touch-icon"]');
        existingIcons.forEach(icon => icon.remove());
        const newIcon = doc.createElement('link');
        newIcon.rel = 'apple-touch-icon';
        newIcon.href = 'https://raw.githubusercontent.com/YOUR_GITHUB_USERNAME/our-music-hub/main/icon.png';
        doc.head.appendChild(newIcon);
    </script>
    """,
    height=0,
    width=0,
)

st.markdown("""
    <style>
    .stApp { background-color: #FDF1F4; }
    div[data-baseweb="input"] > div, div[data-baseweb="radio"] { border-radius: 20px !important; }
    div[data-baseweb="input"] > div, div[data-baseweb="textarea"] > div {
        border: 1px solid #FFC0CB !important;
        background-color: white !important;
    }
    div.stButton > button:first-child {
        border-radius: 20px;
        background-color: #FFB6C1;
        color: white;
        border: none;
        font-weight: bold;
        transition: 0.3s;
        width: 100%;
    }
    div.stButton > button:first-child:hover { background-color: #FF69B4; }
    .gallery-card {
        background-color: white;
        padding: 20px;
        border-radius: 24px;
        box-shadow: 0 4px 15px rgba(255, 182, 193, 0.2);
        text-align: center;
        margin-bottom: 10px; 
        border: 2px solid #FFF0F5;
    }
    .review-box {
        background-color: #FFF0F5;
        border-radius: 12px;
        padding: 15px;
        margin-top: 15px;
        text-align: left;
    }
    .note-box {
        background-color: #FFF0F5;
        border-radius: 8px;
        padding: 10px;
        margin-bottom: 12px;
        text-align: left;
        border-left: 4px solid #FFB6C1;
    }
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
    .apple-link { background-color: #FFE4E1; color: #FF69B4; }
    .apple-link:hover { background-color: #FFB6C1; color: white; }
    .spotify-link { background-color: #E8F5E9; color: #1DB954; }
    .spotify-link:hover { background-color: #1DB954; color: white; }
    button[data-baseweb="tab"] {
        font-size: 15px !important;
        font-weight: bold !important;
    }
    .action-container { margin-bottom: 30px; }
    </style>
""", unsafe_allow_html=True)

# --- API FUNCTIONS ---
def get_details_from_link(link: str) -> tuple[str, str] | None:
    try:
        if "spotify.com" in link and "track" in link:
            track_id = link.split("track/")[1].split("?")[0]
            auth_manager = SpotifyClientCredentials(
                client_id=st.secrets["SPOTIFY_CLIENT_ID"], 
                client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"]
            )
            sp = spotipy.Spotify(auth_manager=auth_manager)
            track = sp.track(track_id)
            return track["name"], track["artists"][0]["name"]
            
        elif "music.apple.com" in link:
            match = re.search(r'[?&]i=(\d+)', link)
            if match:
                track_id = match.group(1)
                response = requests.get(f"https://itunes.apple.com/lookup?id={track_id}", timeout=5)
                data = response.json()
                if data.get("results"):
                    return data["results"][0]["trackName"], data["results"][0]["artistName"]
    except Exception as e:
        st.error(f"Error reading link: {e}")
    return None

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
    except Exception:
        return None

def get_apple_music_info(song_title: str, artist: str) -> dict | None:
    endpoint = "https://itunes.apple.com/search"
    clean_title = re.split(r' - | \(| \[', song_title)[0].strip()
    queries = [f"{song_title} {artist}", f"{clean_title} {artist}"]
    
    for q in queries:
        params = {"term": q, "media": "music", "entity": "song", "limit": 1}
        try:
            response = requests.get(endpoint, params=params, timeout=5)
            response.raise_for_status()
            data = response.json()
            results = data.get("results", [])
            
            if results:
                track = results[0]
                artwork_url = track.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                return {
                    "apple_url": track.get("trackViewUrl"),
                    "title": track.get("trackName"),
                    "artist": track.get("artistName"),
                    "album_art": artwork_url
                }
        except Exception:
            continue
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
        "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

def render_song_card(title, artist, spotify_id, spotify_url, apple_url, rating=None, review_text=None, reviewer=None, note=None):
    card_html = f"""<div class="gallery-card">
<h4 style="margin-bottom: 5px; margin-top: 0px; color: #333;">{title}</h4>
<p style="margin-top: 0px; margin-bottom: 15px; color: #666; font-style: italic;">{artist}</p>"""

    # Inject the Add/Edit Note right below the title/artist
    if pd.notna(note) and str(note).strip() != "":
        card_html += f"""
        <div class="note-box">
            <p style="margin: 0; font-size: 13px; color: #d63384;"><strong>💭 Note:</strong> {note}</p>
        </div>
        """
    
    if pd.notna(spotify_id) and spotify_id != "":
        card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="https://open.spotify.com/embed/track/{spotify_id}" width="100%" height="80" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>"""
    
    if pd.notna(apple_url) and apple_url != "":
        apple_embed_url = apple_url.replace("music.apple.com", "embed.music.apple.com")
        card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="{apple_embed_url}" width="100%" height="150" frameBorder="0" allowfullscreen="" allow="autoplay *; encrypted-media *;" loading="lazy"></iframe>"""
    
    if pd.notna(review_text) and str(review_text).strip() != "":
        try:
            star_count = int(float(rating))
            stars = "⭐" * star_count
        except (ValueError, TypeError):
            stars = "⭐" 
            
        rev_name = reviewer if pd.notna(reviewer) else "Unknown"
        card_html += f"""
        <div class="review-box">
            <strong>{rev_name}'s Rating:</strong> {stars}<br>
            <p style="margin-top:5px; margin-bottom:0; font-size:14px; color:#444;">"{review_text}"</p>
        </div>
        """

    card_html += '<div class="link-container">'
    if pd.notna(apple_url) and apple_url != "":
        card_html += f'<a href="{apple_url}" target="_blank" class="apple-link">Apple 🍎</a>'
    if pd.notna(spotify_url) and spotify_url != "":
        card_html += f'<a href="{spotify_url}" target="_blank" class="spotify-link">Spotify 🟢</a>'
    card_html += '</div></div>'
    
    st.markdown(card_html, unsafe_allow_html=True)


# --- DATA INITIALIZATION ---
conn = st.connection("gsheets", type=GSheetsConnection)
df = conn.read(worksheet="Sheet1", ttl="10m")

expected_columns = ["Title", "Artist", "Spotify ID", "Spotify URL", "Apple URL", "Album Art", "Date Added", "Playlist", "Listened", "Rating", "Review", "Reviewer", "Date Reviewed", "Note"]
if df.empty or len(df.columns) == 0:
    df = pd.DataFrame(columns=expected_columns)
for col in expected_columns:
    if col not in df.columns:
        df[col] = ""

df["Listened"] = df["Listened"].fillna(False).astype(bool)
df["Rating"] = df["Rating"].fillna("").astype(str)
df["Review"] = df["Review"].fillna("").astype(str)
df["Reviewer"] = df["Reviewer"].fillna("").astype(str)
df["Date Reviewed"] = df["Date Reviewed"].fillna("").astype(str)
df["Note"] = df["Note"].fillna("").astype(str)
df = df.reset_index(drop=True)

# --- MAIN APP UI ---
st.title("🌸 Our Music Hub 🌸")

# --- INPUT SECTION ---
with st.container():
    st.write("### Drop a new rec! 🎧")
    
    input_tab1, input_tab2 = st.tabs(["📝 Type it out", "🔗 Paste a link"])
    
    with input_tab1:
        col1, col2 = st.columns(2)
        with col1:
            song_input = st.text_input("Song Title", placeholder="e.g. Pink Pony Club")
        with col2:
            artist_input = st.text_input("Artist", placeholder="e.g. Chappell Roan")
            
    with input_tab2:
        link_input = st.text_input("Spotify or Apple Music Link", placeholder="https://open.spotify.com/track/...")
        
    note_input = st.text_input("Add a note (optional) 💭", placeholder="e.g. The bridge on this song is insane!")
    playlist_selection = st.radio("Whose playlist is this for?", ["Hannah", "Alyssa"], horizontal=True)
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        save_clicked = st.button("Search & Save ✨", use_container_width=True)
    with btn_col2:
        generic_clicked = st.button("Generic Search 🔍", use_container_width=True)
        
    if save_clicked or generic_clicked:
        search_title, search_artist = None, None
        
        if link_input:
            with st.spinner("Extracting info from link..."):
                details = get_details_from_link(link_input)
                if details:
                    search_title, search_artist = details
                else:
                    st.error("Couldn't extract the song from that link. Ensure it's a direct track link!")
        elif song_input and artist_input:
            search_title = song_input
            search_artist = artist_input
        else:
            st.warning("Please enter a song and artist, or paste a link!")
            
        if search_title and search_artist:
            with st.spinner(f"Hunting for '{search_title}'..."):
                new_song = fetch_song_data(search_title, search_artist)
                
                if new_song:
                    if save_clicked:
                        new_song["Playlist"] = playlist_selection
                        new_song["Listened"] = False 
                        new_song["Rating"] = ""
                        new_song["Review"] = ""
                        new_song["Reviewer"] = ""
                        new_song["Date Reviewed"] = ""
                        new_song["Note"] = note_input
                        
                        if not df.empty and new_song["Spotify ID"] in df["Spotify ID"].values and new_song["Spotify ID"] != "":
                            st.warning(f"You already have '{new_song['Title']}' in the vault!")
                        else:
                            new_row_df = pd.DataFrame([new_song])
                            updated_df = pd.concat([new_row_df, df], ignore_index=True)
                            conn.update(worksheet="Sheet1", data=updated_df)
                            
                            st.success(f"Added '{new_song['Title']}' to {playlist_selection}'s vault! 🎉")
                            st.cache_data.clear()
                            st.rerun()
                    elif generic_clicked:
                        st.success("Search complete! (Not saved to vault)")
                        render_song_card(
                            new_song["Title"], 
                            new_song["Artist"], 
                            new_song["Spotify ID"], 
                            new_song["Spotify URL"], 
                            new_song["Apple URL"],
                            note=note_input
                        )
                else:
                    st.error("Couldn't find that exact song. Check the spelling and try again!")

st.divider()

# --- MAIN 3-TAB LAYOUT (Hannah's List, Alyssa's List, Reviews Archive) ---
st.write("### The Vault & Archive 💖")

unreviewed_df = df[df["Review"] == ""]
reviewed_df = df[df["Review"] != ""]

df_hannah = unreviewed_df[unreviewed_df["Playlist"] == "Hannah"]
df_alyssa = unreviewed_df[unreviewed_df["Playlist"] == "Alyssa"]

tab_hannah, tab_alyssa, tab_archive = st.tabs(["🌸 Hannah's List", "🎧 Alyssa's List", "📖 Reviews Archive"])

# --- TAB 1: HANNAH'S LIST ---
with tab_hannah:
    if df_hannah.empty:
        st.info("Hannah's vault is empty!")
    else:
        for index, row in df_hannah.iterrows():
            render_song_card(
                row.get("Title"), row.get("Artist"), row.get("Spotify ID"), 
                row.get("Spotify URL"), row.get("Apple URL"), note=row.get("Note", "")
            )
            
            with st.expander("💭 Add/Edit Note"):
                new_note = st.text_input("Update your note:", value=row.get("Note", ""), key=f"h_note_{index}")
                if st.button("Save Note 💾", key=f"h_save_note_{index}"):
                    df.at[index, "Note"] = new_note
                    conn.update(worksheet="Sheet1", data=df)
                    st.cache_data.clear()
                    st.rerun()

            with st.expander("✍️ Rate & Review"):
                st.write(f"Did you listen to **{row.get('Title')}**?")
                reviewer_name = st.radio("Who is reviewing?", ["Hannah", "Alyssa"], key=f"h_who_{index}", horizontal=True)
                user_rating = st.slider("Rating", 1, 5, 5, key=f"h_rate_{index}")
                user_review = st.text_area("What did you think?", key=f"h_rev_{index}")
                
                colA, colB = st.columns(2)
                with colA:
                    if st.button("Submit Review ✅", key=f"h_sub_{index}"):
                        if user_review.strip() == "":
                            st.error("Please write a quick review!")
                        else:
                            df.at[index, "Rating"] = str(user_rating)
                            df.at[index, "Review"] = user_review
                            df.at[index, "Reviewer"] = reviewer_name
                            df.at[index, "Listened"] = True
                            df.at[index, "Date Reviewed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            conn.update(worksheet="Sheet1", data=df)
                            st.cache_data.clear()
                            st.rerun()
                with colB:
                    if st.button("Delete Song 🗑️", key=f"del_h_{index}"):
                        df = df.drop(index)
                        conn.update(worksheet="Sheet1", data=df)
                        st.cache_data.clear()
                        st.rerun()
            st.write("")

# --- TAB 2: ALYSSA'S LIST ---
with tab_alyssa:
    if df_alyssa.empty:
        st.info("Alyssa's vault is empty!")
    else:
        for index, row in df_alyssa.iterrows():
            render_song_card(
                row.get("Title"), row.get("Artist"), row.get("Spotify ID"), 
                row.get("Spotify URL"), row.get("Apple URL"), note=row.get("Note", "")
            )
            
            with st.expander("💭 Add/Edit Note"):
                new_note = st.text_input("Update your note:", value=row.get("Note", ""), key=f"a_note_{index}")
                if st.button("Save Note 💾", key=f"a_save_note_{index}"):
                    df.at[index, "Note"] = new_note
                    conn.update(worksheet="Sheet1", data=df)
                    st.cache_data.clear()
                    st.rerun()

            with st.expander("✍️ Rate & Review"):
                st.write(f"Did you listen to **{row.get('Title')}**?")
                reviewer_name = st.radio("Who is reviewing?", ["Hannah", "Alyssa"], key=f"a_who_{index}", horizontal=True)
                user_rating = st.slider("Rating", 1, 5, 5, key=f"a_rate_{index}")
                user_review = st.text_area("What did you think?", key=f"a_rev_{index}")
                
                colA, colB = st.columns(2)
                with colA:
                    if st.button("Submit Review ✅", key=f"a_sub_{index}"):
                        if user_review.strip() == "":
                            st.error("Please write a quick review!")
                        else:
                            df.at[index, "Rating"] = str(user_rating)
                            df.at[index, "Review"] = user_review
                            df.at[index, "Reviewer"] = reviewer_name
                            df.at[index, "Listened"] = True
                            df.at[index, "Date Reviewed"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            conn.update(worksheet="Sheet1", data=df)
                            st.cache_data.clear()
                            st.rerun()
                with colB:
                    if st.button("Delete Song 🗑️", key=f"del_a_{index}"):
                        df = df.drop(index)
                        conn.update(worksheet="Sheet1", data=df)
                        st.cache_data.clear()
                        st.rerun()
            st.write("")

# --- TAB 3: REVIEWS ARCHIVE ---
with tab_archive:
    if reviewed_df.empty:
        st.info("No reviews yet! Go to Hannah's or Alyssa's list and review a song.")
    else:
        reviewed_df["Sort_Date"] = reviewed_df["Date Reviewed"].replace("", pd.NA).fillna(reviewed_df["Date Added"])
        reviewed_df = reviewed_df.sort_values(by="Sort_Date", ascending=False)
        
        tab_h_rev, tab_a_rev = st.tabs(["🌸 Hannah's Reviews", "🎧 Alyssa's Reviews"])
        
        with tab_h_rev:
            h_rev_df = reviewed_df[reviewed_df["Reviewer"] == "Hannah"]
            if h_rev_df.empty:
                st.info("Hannah hasn't left any reviews yet!")
            else:
                for index, row in h_rev_df.iterrows():
                    render_song_card(
                        row.get("Title"), row.get("Artist"), row.get("Spotify ID"), 
                        row.get("Spotify URL"), row.get("Apple URL"), 
                        row.get("Rating"), row.get("Review"), row.get("Reviewer"), row.get("Note", "")
                    )
                    if st.button("Delete Record 🗑️", key=f"del_hrev_{index}"):
                        df = df.drop(index)
                        conn.update(worksheet="Sheet1", data=df)
                        st.cache_data.clear()
                        st.rerun()
                    st.write("")
        
        with tab_a_rev:
            a_rev_df = reviewed_df[reviewed_df["Reviewer"] == "Alyssa"]
            if a_rev_df.empty:
                st.info("Alyssa hasn't left any reviews yet!")
            else:
                for index, row in a_rev_df.iterrows():
                    render_song_card(
                        row.get("Title"), row.get("Artist"), row.get("Spotify ID"), 
                        row.get("Spotify URL"), row.get("Apple URL"), 
                        row.get("Rating"), row.get("Review"), row.get("Reviewer"), row.get("Note", "")
                    )
                    if st.button("Delete Record 🗑️", key=f"del_arev_{index}"):
                        df = df.drop(index)
                        conn.update(worksheet="Sheet1", data=df)
                        st.cache_data.clear()
                        st.rerun()
                    st.write("")