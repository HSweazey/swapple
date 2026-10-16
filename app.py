import streamlit as st
import requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import html
from PIL import Image
import streamlit.components.v1 as components
import os
import re
import unicodedata
from difflib import SequenceMatcher

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
APPLE_STOREFRONT = "us"
AUTO_MATCH_SCORE = 88
AMBIGUITY_MARGIN = 4


def spotify_client() -> spotipy.Spotify:
    auth_manager = SpotifyClientCredentials(
        client_id=st.secrets["SPOTIFY_CLIENT_ID"],
        client_secret=st.secrets["SPOTIFY_CLIENT_SECRET"],
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def spotify_track_data(track: dict) -> dict:
    """Keep the original Spotify recording's identifying metadata."""
    images = track.get("album", {}).get("images", [])
    return {
        "spotify_id": track["id"],
        "spotify_url": track["external_urls"]["spotify"],
        "title": track["name"],
        "artist": track["artists"][0]["name"],
        "duration_ms": track.get("duration_ms"),
        "explicit": track.get("explicit"),
        "isrc": track.get("external_ids", {}).get("isrc"),
        "album_id": track.get("album", {}).get("id"),
        "album_art": images[0]["url"] if images else None,
    }


def get_spotify_track_from_link(link: str) -> dict | None:
    match = re.search(r"spotify\.com/track/([A-Za-z0-9]+)", link)
    if not match:
        return None
    try:
        return spotify_track_data(spotify_client().track(match.group(1)))
    except Exception:
        return None


def get_spotify_track_info(song_title: str, artist: str) -> dict | None:
    try:
        sp = spotify_client()
        results = sp.search(q=f"track:{song_title} artist:{artist}", type="track", limit=5)
        items = results.get("tracks", {}).get("items", [])
        if not items:
            results = sp.search(q=f"{song_title} {artist}", type="track", limit=5)
            items = results.get("tracks", {}).get("items", [])
        return spotify_track_data(items[0]) if items else None
    except Exception:
        return None


def apple_track_from_link(link: str) -> dict | None:
    # Apple uses both album links with ?i=<track id> and direct /song/.../<id>
    # links, so accept either form.
    track_match = re.search(r"[?&]i=(\d+)", link)
    if not track_match:
        track_match = re.search(r"/song/(?:[^/?#]+/)*(\d+)(?:[?#]|$)", link)
    if not track_match:
        return None
    storefront_match = re.search(r"music\.apple\.com/([a-z]{2})/", link, re.IGNORECASE)
    storefront = storefront_match.group(1).lower() if storefront_match else APPLE_STOREFRONT
    try:
        response = requests.get(
            "https://itunes.apple.com/lookup",
            params={"id": track_match.group(1), "country": storefront},
            timeout=5,
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        return apple_result_data(results[0]) if results else None
    except requests.RequestException:
        return None


def normalize(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(char for char in value if not unicodedata.combining(char))
    value = value.casefold().replace("&", " and ")
    # \W is Unicode-aware, so non-Latin titles (Hangul, kana, Cyrillic...) keep
    # their letters instead of collapsing to an empty string.
    return re.sub(r"[\W_]+", " ", value).strip()


def version_flags(title: str) -> set[str]:
    title = normalize(title)
    patterns = {
        "live": r"\blive\b",
        "remaster": r"\bremaster(?:ed)?\b",
        "acoustic": r"\bacoustic\b",
        "instrumental": r"\binstrumental\b",
        "radio_edit": r"\bradio edit\b",
        "extended": r"\bextended\b",
        "sped_up": r"\bsped up\b",
        "slowed": r"\bslowed\b",
    }
    return {name for name, pattern in patterns.items() if re.search(pattern, title)}


def similarity(left: str, right: str) -> float:
    left, right = normalize(left), normalize(right)
    # Two empty strings would otherwise score as a perfect 1.0 match.
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def duration_score(spotify_ms: int | None, apple_ms: int | None) -> float:
    if not spotify_ms or not apple_ms:
        return 0.5
    difference = abs(spotify_ms - apple_ms)
    if difference <= 1_500:
        return 1.0
    if difference <= 4_000:
        return 0.95
    if difference <= 8_000:
        return 0.8
    if difference <= 15_000:
        return 0.55
    if difference <= 30_000:
        return 0.2
    return 0.0


def apple_result_data(track: dict) -> dict:
    artwork_url = track.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
    return {
        "apple_id": str(track.get("trackId", "")),
        "apple_url": track.get("trackViewUrl", ""),
        "title": track.get("trackName", ""),
        "artist": track.get("artistName", ""),
        "album": track.get("collectionName", ""),
        "duration_ms": track.get("trackTimeMillis"),
        # "explicit", "cleaned" (censored version) or "notExplicit".
        "explicitness": track.get("trackExplicitness"),
        "album_art": artwork_url or None,
    }


def score_apple_candidate(spotify_data: dict, apple_data: dict) -> dict:
    title_match = similarity(spotify_data["title"], apple_data["title"])
    artist_match = similarity(spotify_data["artist"], apple_data["artist"])
    length_match = duration_score(spotify_data.get("duration_ms"), apple_data.get("duration_ms"))
    score = 100 * (0.55 * title_match + 0.30 * artist_match + 0.15 * length_match)

    spotify_versions = version_flags(spotify_data["title"])
    apple_versions = version_flags(apple_data["title"])
    if spotify_versions == apple_versions:
        score += 3
    else:
        score -= 12

    # Explicit and clean editions share title, artist and length, so without
    # this they always tie and force a manual pick.
    spotify_explicit = spotify_data.get("explicit")
    apple_explicitness = apple_data.get("explicitness")
    if spotify_explicit is not None and apple_explicitness:
        if spotify_explicit and apple_explicitness == "cleaned":
            score -= 8
        elif not spotify_explicit and apple_explicitness == "explicit":
            score -= 8

    # The UPC lookup returns the same album Spotify has, which separates the
    # album cut from an otherwise identical single or compilation release.
    if apple_data.get("upc_match"):
        score += 5

    apple_data.update({
        # Unclamped score for ranking: clamping to 100 would turn near-perfect
        # candidates back into ties.
        "rank_score": score,
        "score": max(0, min(100, round(score))),
        "title_match": title_match,
        "artist_match": artist_match,
        "duration_match": length_match,
    })
    return apple_data


def get_spotify_album_upc(spotify_data: dict) -> str | None:
    """Get the album's UPC, a useful cross-store identifier without Apple auth."""
    album_id = spotify_data.get("album_id")
    if not album_id:
        return None
    try:
        album = spotify_client().album(album_id)
        return album.get("external_ids", {}).get("upc")
    except Exception:
        return None


def itunes_lookup_by_upc(upc: str) -> list[dict]:
    try:
        response = requests.get(
            "https://itunes.apple.com/lookup",
            params={"upc": upc, "country": APPLE_STOREFRONT, "entity": "song"},
            timeout=5,
        )
        response.raise_for_status()
        # The first result describes the album; the remaining song results are
        # candidates for the Spotify recording.
        return [
            track for track in response.json().get("results", [])
            if track.get("kind") == "song"
        ]
    except requests.RequestException:
        return []


def find_apple_candidates(spotify_data: dict) -> list[dict]:
    try:
        raw_results = []
        upc_ids = set()
        upc = get_spotify_album_upc(spotify_data)
        if upc:
            upc_tracks = itunes_lookup_by_upc(upc)
            upc_ids = {str(track.get("trackId", "")) for track in upc_tracks}
            raw_results.extend(upc_tracks)

        # UPC is the preferred path. Text search remains a fallback for albums
        # that do not share a UPC across Spotify and the iTunes Store.
        for term in (f"{spotify_data['title']} {spotify_data['artist']}", spotify_data["title"]):
            response = requests.get(
                "https://itunes.apple.com/search",
                params={
                    "term": term,
                    "country": APPLE_STOREFRONT,
                    "media": "music",
                    "entity": "song",
                    "limit": 10,
                },
                timeout=5,
            )
            response.raise_for_status()
            raw_results.extend(response.json().get("results", []))

        seen_ids = set()
        candidates = []
        for track in raw_results:
            apple_data = apple_result_data(track)
            apple_id = apple_data["apple_id"]
            if not apple_data["apple_url"] or not apple_id or apple_id in seen_ids:
                continue
            seen_ids.add(apple_id)
            apple_data["upc_match"] = apple_id in upc_ids
            candidate = score_apple_candidate(spotify_data, apple_data)
            # Never offer unrelated results just because iTunes returned them.
            # Artist names may vary because of featured performers, but the title
            # itself needs to be a strong match.
            if candidate["title_match"] >= 0.75 and candidate["artist_match"] >= 0.35:
                candidates.append(candidate)
        return sorted(candidates, key=lambda candidate: candidate["rank_score"], reverse=True)
    except requests.RequestException:
        return []


def is_confident_match(candidates: list[dict]) -> bool:
    if not candidates:
        return False
    best = candidates[0]
    runner_up = candidates[1] if len(candidates) > 1 else None
    if best["rank_score"] < AUTO_MATCH_SCORE:
        return False
    return not runner_up or best["rank_score"] - runner_up["rank_score"] >= AMBIGUITY_MARGIN


def build_song_data(spotify_data: dict | None, apple_data: dict | None) -> dict | None:
    if not spotify_data and not apple_data:
        return None
    return {
        "Title": spotify_data["title"] if spotify_data else apple_data["title"],
        "Artist": spotify_data["artist"] if spotify_data else apple_data["artist"],
        "Spotify ID": spotify_data["spotify_id"] if spotify_data else "",
        "Spotify URL": spotify_data["spotify_url"] if spotify_data else "",
        "Apple URL": apple_data["apple_url"] if apple_data else "",
        "Album Art": spotify_data["album_art"] if spotify_data else apple_data["album_art"],
        "Date Added": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def html_text(value) -> str:
    """Escape user/API text for the card HTML.

    Newlines become <br> because a blank line would end Streamlit's HTML block
    and dump the rest of the card as raw text; "$" is escaped so it isn't
    treated as LaTeX.
    """
    if value is None or pd.isna(value):
        return ""
    text = html.escape(str(value)).replace("$", "&#36;")
    return "<br>".join(line.strip() for line in text.splitlines())


def html_attr(value) -> str:
    return html.escape(str(value), quote=True)


def render_song_card(title, artist, spotify_id, spotify_url, apple_url, rating=None, review_text=None, reviewer=None, note=None):
    card_html = f"""<div class="gallery-card">
<h4 style="margin-bottom: 5px; margin-top: 0px; color: #333;">{html_text(title)}</h4>
<p style="margin-top: 0px; margin-bottom: 15px; color: #666; font-style: italic;">{html_text(artist)}</p>"""

    if pd.notna(note) and str(note).strip() != "":
        card_html += f"""
        <div class="note-box">
            <p style="margin: 0; font-size: 13px; color: #d63384;"><strong>💭 Note:</strong> {html_text(note)}</p>
        </div>
        """

    if pd.notna(spotify_id) and spotify_id != "":
        card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="https://open.spotify.com/embed/track/{html_attr(spotify_id)}" width="100%" height="80" frameBorder="0" allowfullscreen="" allow="autoplay; clipboard-write; encrypted-media; fullscreen; picture-in-picture" loading="lazy"></iframe>"""

    if pd.notna(apple_url) and apple_url != "":
        apple_embed_url = str(apple_url).replace("music.apple.com", "embed.music.apple.com")
        card_html += f"""<iframe style="border-radius:12px; margin-top: 5px;" src="{html_attr(apple_embed_url)}" width="100%" height="150" frameBorder="0" allowfullscreen="" allow="autoplay *; encrypted-media *;" loading="lazy"></iframe>"""

    if pd.notna(review_text) and str(review_text).strip() != "":
        try:
            star_count = int(float(rating))
            stars = "⭐" * star_count
        except (ValueError, TypeError):
            stars = "⭐"

        rev_name = reviewer if pd.notna(reviewer) and str(reviewer).strip() else "Unknown"
        card_html += f"""
        <div class="review-box">
            <strong>{html_text(rev_name)}'s Rating:</strong> {stars}<br>
            <p style="margin-top:5px; margin-bottom:0; font-size:14px; color:#444;">"{html_text(review_text)}"</p>
        </div>
        """

    card_html += '<div class="link-container">'
    if pd.notna(apple_url) and apple_url != "":
        card_html += f'<a href="{html_attr(apple_url)}" target="_blank" class="apple-link">Apple 🍎</a>'
    if pd.notna(spotify_url) and spotify_url != "":
        card_html += f'<a href="{html_attr(spotify_url)}" target="_blank" class="spotify-link">Spotify 🟢</a>'
    card_html += '</div></div>'

    # Drop indentation and whitespace-only lines: markdown treats a blank line
    # as the end of the HTML block (e.g. a note followed by a review with no embeds).
    card_html = "\n".join(line.strip() for line in card_html.splitlines() if line.strip())
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


def finish_song(new_song: dict, action: str, playlist: str, note: str) -> None:
    """Save a resolved song or show the preview for a generic search."""
    if action == "save":
        new_song["Playlist"] = playlist
        new_song["Listened"] = False
        new_song["Rating"] = ""
        new_song["Review"] = ""
        new_song["Reviewer"] = ""
        new_song["Date Reviewed"] = ""
        new_song["Note"] = note

        if (not df.empty and new_song["Spotify ID"]
                and new_song["Spotify ID"] in df["Spotify ID"].values):
            st.warning(f"You already have '{new_song['Title']}' in the vault!")
            return

        updated_df = pd.concat([pd.DataFrame([new_song]), df], ignore_index=True)
        conn.update(worksheet="Sheet1", data=updated_df)
        st.success(f"Added '{new_song['Title']}' to {playlist}'s vault! 🎉")
        st.session_state.apple_match_pending = None
        st.cache_data.clear()
        st.rerun()

    st.session_state.apple_match_pending = None
    st.success("Search complete! (Not saved to vault)")
    render_song_card(
        new_song["Title"], new_song["Artist"], new_song["Spotify ID"],
        new_song["Spotify URL"], new_song["Apple URL"], note=note,
    )


if "apple_match_pending" not in st.session_state:
    st.session_state.apple_match_pending = None


def mark_input_source(source: str) -> None:
    """Remember which tab was edited last, since both tabs keep their values."""
    st.session_state.input_source = source

# --- MAIN APP UI ---
st.title("🌸 Our Music Hub 🌸")

# --- INPUT SECTION ---
with st.container():
    st.write("### Drop a new rec! 🎧")
    
    input_tab1, input_tab2 = st.tabs(["📝 Type it out", "🔗 Paste a link"])
    
    with input_tab1:
        col1, col2 = st.columns(2)
        with col1:
            song_input = st.text_input(
                "Song Title", placeholder="e.g. Pink Pony Club",
                on_change=mark_input_source, args=("typed",),
            )
        with col2:
            artist_input = st.text_input(
                "Artist", placeholder="e.g. Chappell Roan",
                on_change=mark_input_source, args=("typed",),
            )

    with input_tab2:
        link_input = st.text_input(
            "Spotify or Apple Music Link", placeholder="https://open.spotify.com/track/...",
            on_change=mark_input_source, args=("link",),
        )
        
    note_input = st.text_input("Add a note (optional) 💭", placeholder="e.g. The bridge on this song is insane!")
    playlist_selection = st.radio("Whose playlist is this for?", ["Hannah", "Alyssa"], horizontal=True)
    
    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        save_clicked = st.button("Search & Save ✨", use_container_width=True)
    with btn_col2:
        generic_clicked = st.button("Generic Search 🔍", use_container_width=True)
        
    if save_clicked or generic_clicked:
        st.session_state.apple_match_pending = None
        st.session_state.pop("apple_match_selection", None)
        action = "save" if save_clicked else "preview"
        spotify_data = None
        known_apple_data = None

        # If both tabs are filled in, use whichever one was edited most recently.
        has_typed = bool(song_input and artist_input)
        if link_input and has_typed:
            use_link = st.session_state.get("input_source", "link") == "link"
        else:
            use_link = bool(link_input)

        with st.spinner("Finding the right recording..."):
            if use_link:
                if "spotify.com" in link_input:
                    # A Spotify URL identifies the precise Spotify recording: never search it again.
                    spotify_data = get_spotify_track_from_link(link_input)
                elif "music.apple.com" in link_input:
                    # An Apple Music URL is already an exact Apple selection.
                    known_apple_data = apple_track_from_link(link_input)
                    if known_apple_data:
                        spotify_data = get_spotify_track_info(
                            known_apple_data["title"], known_apple_data["artist"]
                        )
                else:
                    st.error("Please paste a direct Spotify or Apple Music track link.")
            elif has_typed:
                spotify_data = get_spotify_track_info(song_input, artist_input)
            else:
                st.warning("Please enter a song and artist, or paste a link!")

        if use_link and not spotify_data and not known_apple_data:
            st.error("Couldn't extract that song. Ensure the link is for a single track.")
        elif spotify_data or known_apple_data:
            if known_apple_data:
                finish_song(
                    build_song_data(spotify_data, known_apple_data), action,
                    playlist_selection, note_input,
                )
            elif spotify_data:
                with st.spinner(f"Matching '{spotify_data['title']}' on Apple Music..."):
                    candidates = find_apple_candidates(spotify_data)

                if is_confident_match(candidates):
                    finish_song(
                        build_song_data(spotify_data, candidates[0]), action,
                        playlist_selection, note_input,
                    )
                else:
                    # Streamlit reruns after a button click, so retain the match options in session state.
                    st.session_state.apple_match_pending = {
                        "spotify_data": spotify_data,
                        "candidates": candidates,
                        "action": action,
                        "playlist": playlist_selection,
                        "note": note_input,
                    }
                    st.rerun()
        elif has_typed:
            st.error("Couldn't find that song on Spotify. Check the spelling and try again!")

    pending_match = st.session_state.apple_match_pending
    if pending_match:
        candidates = pending_match["candidates"]
        st.warning("I couldn't confidently choose the Apple Music version. Please pick one.")
        st.caption(
            f"Spotify source: {pending_match['spotify_data']['title']} — "
            f"{pending_match['spotify_data']['artist']}"
        )

        choices = list(range(len(candidates))) + [None]

        def candidate_label(choice):
            if choice is None:
                return "No Apple Music match — save Spotify only"
            candidate = candidates[choice]
            seconds = round((candidate.get("duration_ms") or 0) / 1000)
            duration = f" • {seconds // 60}:{seconds % 60:02d}" if seconds else ""
            album = f" • {candidate['album']}" if candidate.get("album") else ""
            return (
                f"{candidate['title']} — {candidate['artist']}{album}{duration} "
                f"(match: {candidate['score']}%)"
            )

        selection = st.selectbox(
            "Apple Music match",
            choices,
            format_func=candidate_label,
            key="apple_match_selection",
        )
        choice_col, cancel_col = st.columns(2)
        with choice_col:
            if st.button("Use this match ✨", key="confirm_apple_match"):
                apple_data = candidates[selection] if selection is not None else None
                new_song = build_song_data(pending_match["spotify_data"], apple_data)
                finish_song(
                    new_song, pending_match["action"], pending_match["playlist"],
                    pending_match["note"],
                )
        with cancel_col:
            if st.button("Cancel", key="cancel_apple_match"):
                st.session_state.apple_match_pending = None
                st.rerun()

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
                    
                    with st.expander("✏️ Edit Review"):
                        curr_rev_name = row.get("Reviewer", "Hannah")
                        rev_idx = 0 if curr_rev_name == "Hannah" else 1
                        
                        try:
                            curr_rate = int(float(row.get("Rating", 5)))
                        except:
                            curr_rate = 5
                            
                        new_rev_name = st.radio("Who is reviewing?", ["Hannah", "Alyssa"], index=rev_idx, key=f"edit_who_h_{index}", horizontal=True)
                        new_rate = st.slider("Rating", 1, 5, curr_rate, key=f"edit_rate_h_{index}")
                        new_rev_text = st.text_area("What did you think?", value=row.get("Review", ""), key=f"edit_text_h_{index}")
                        
                        colA, colB = st.columns(2)
                        with colA:
                            if st.button("Save Changes ✅", key=f"edit_save_h_{index}"):
                                if new_rev_text.strip() == "":
                                    st.error("Please write a quick review!")
                                else:
                                    df.at[index, "Reviewer"] = new_rev_name
                                    df.at[index, "Rating"] = str(new_rate)
                                    df.at[index, "Review"] = new_rev_text
                                    conn.update(worksheet="Sheet1", data=df)
                                    st.cache_data.clear()
                                    st.rerun()
                        with colB:
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
                    
                    with st.expander("✏️ Edit Review"):
                        curr_rev_name = row.get("Reviewer", "Alyssa")
                        rev_idx = 0 if curr_rev_name == "Hannah" else 1
                        
                        try:
                            curr_rate = int(float(row.get("Rating", 5)))
                        except:
                            curr_rate = 5
                            
                        new_rev_name = st.radio("Who is reviewing?", ["Hannah", "Alyssa"], index=rev_idx, key=f"edit_who_a_{index}", horizontal=True)
                        new_rate = st.slider("Rating", 1, 5, curr_rate, key=f"edit_rate_a_{index}")
                        new_rev_text = st.text_area("What did you think?", value=row.get("Review", ""), key=f"edit_text_a_{index}")
                        
                        colA, colB = st.columns(2)
                        with colA:
                            if st.button("Save Changes ✅", key=f"edit_save_a_{index}"):
                                if new_rev_text.strip() == "":
                                    st.error("Please write a quick review!")
                                else:
                                    df.at[index, "Reviewer"] = new_rev_name
                                    df.at[index, "Rating"] = str(new_rate)
                                    df.at[index, "Review"] = new_rev_text
                                    conn.update(worksheet="Sheet1", data=df)
                                    st.cache_data.clear()
                                    st.rerun()
                        with colB:
                            if st.button("Delete Record 🗑️", key=f"del_arev_{index}"):
                                df = df.drop(index)
                                conn.update(worksheet="Sheet1", data=df)
                                st.cache_data.clear()
                                st.rerun()
                    st.write("")
