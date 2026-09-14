#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BUET Mosque Tafseer - Standalone Automated YouTube Publisher

Automates:
  1. Title and description generation from tafsir input JSON.
  2. 1920x1080 thumbnail generation via Remotion with custom typography.
  3. Video upload to YouTube (resumable chunked upload).
  4. Custom thumbnail upload.
  5. Insertion into the channel playlist.

Usage in Docker:
  docker compose run --rm -p 8080:8080 verse-renderer python3 python/publish_youtube.py [inputs/tafsir_YYYY_MM_DD.json]
  docker compose run --rm verse-renderer python3 python/publish_youtube.py --dry-run
  docker compose run --rm verse-renderer python3 python/publish_youtube.py --thumbnail-only
"""

import os
import sys
import json
import time
import argparse
import subprocess
import urllib.parse
import threading
from pathlib import Path

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

import google.auth.transport.requests
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUT_DIR = PROJECT_ROOT / "output"
REMOTION_DIR = PROJECT_ROOT / "remotion"
CLIENT_SECRET_FILE = PROJECT_ROOT / os.environ.get("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
TOKEN_FILE = PROJECT_ROOT / "token.json"

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube"
]


def resolve_input_file(path_str: str = None) -> Path:
    if path_str:
        p = Path(path_str)
        if p.exists():
            return p
        if (PROJECT_ROOT / path_str).exists():
            return PROJECT_ROOT / path_str
        if (INPUTS_DIR / path_str).exists():
            return INPUTS_DIR / path_str
        raise FileNotFoundError(f"Input file not found: {path_str}")

    candidates = sorted([
        f for f in INPUTS_DIR.glob("tafsir_*.json")
        if not f.name.endswith(".example.json") and "example" not in f.name
    ])
    if candidates:
        return candidates[-1]

    raise FileNotFoundError("No input JSON file found in inputs/ directory.")


def extract_date_suffix(file_path: Path) -> str:
    name = file_path.stem
    if name.startswith("tafsir_"):
        return name.replace("tafsir_", "")
    return "latest"


def find_browser_executable() -> str:
    env_path = os.environ.get("REMOTION_CHROMIUM_EXECUTABLE_PATH")
    if env_path and Path(env_path).exists():
        return env_path
    
    candidates = [
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    ]
    for c in candidates:
        if Path(c).exists():
            return c
    return ""


def generate_thumbnail(intro_data: dict, out_thumbnail_path: Path):
    print(f"[Thumbnail] Generating 1920x1080 thumbnail -> {out_thumbnail_path.name}...")
    out_thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    
    props_path = REMOTION_DIR / "tmp_thumb_props.json"
    props_path.write_text(json.dumps(intro_data, ensure_ascii=False, indent=2), encoding="utf-8")
    
    cmd = [
        "npx", "remotion", "still",
        "src/index.ts", "Thumbnail",
        str(out_thumbnail_path.resolve()),
        f"--props={props_path.resolve()}",
        "--image-format=jpeg",
        "--jpeg-quality=95"
    ]
    browser_path = find_browser_executable()
    if browser_path:
        cmd.append(f"--browser-executable={browser_path}")
        
    try:
        subprocess.run(cmd, cwd=REMOTION_DIR, check=True)
    finally:
        if props_path.exists():
            props_path.unlink()
            
    if not out_thumbnail_path.exists():
        raise FileNotFoundError(f"Failed to generate thumbnail at {out_thumbnail_path}")
    print(f"[Thumbnail] Created successfully: {out_thumbnail_path} ({out_thumbnail_path.stat().st_size // 1024} KB)")


def extract_code_from_redirect(user_input: str) -> str:
    raw = user_input.strip()
    if "code=" in raw:
        parsed = urllib.parse.urlparse(raw)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            return params["code"][0]
    return raw


def get_authenticated_service():
    creds = None
    if TOKEN_FILE.exists() and TOKEN_FILE.stat().st_size > 0:
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)
        except Exception as e:
            print(f"[Auth] Warning: Could not load {TOKEN_FILE.name}: {e}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[Auth] Refreshing expired access token...")
            creds.refresh(google.auth.transport.requests.Request())
        else:
            if not CLIENT_SECRET_FILE.exists() or CLIENT_SECRET_FILE.stat().st_size == 0:
                raise FileNotFoundError(
                    f"OAuth client secret file not found at: {CLIENT_SECRET_FILE}\n"
                    "Please download client_secret.json from Google Cloud Console and place it in the project root."
                )

            print(f"[Auth] Initiating one-time OAuth 2.0 authorization using {CLIENT_SECRET_FILE.name}...")
            flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRET_FILE), SCOPES)
            flow.redirect_uri = "http://localhost:8080/"
            auth_url, _ = flow.authorization_url(prompt="consent", access_type="offline")

            print("\n" + "=" * 65)
            print("🔑 YouTube Authorization Required (One-Time Setup)")
            print("=" * 65)
            print("1. Open this URL in your browser:\n")
            print(f"   {auth_url}\n")
            print("2. Sign in with your YouTube channel Google Account and click \x27Allow\x27.")
            print("3. If you ran Docker with \x27-p 8080:8080\x27, the browser will redirect")
            print("   to localhost:8080 and automatically complete authorization.")
            print("4. If the page shows \x27Site can\x27t be reached\x27, simply copy the FULL")
            print("   redirect URL from the address bar and paste it below.")
            print("=" * 65 + "\n")

            creds = None
            server_error = [None]
            server_creds = [None]

            def run_server():
                try:
                    server_creds[0] = flow.run_local_server(
                        host="localhost",
                        port=8080,
                        bind_addr="0.0.0.0",
                        open_browser=False,
                        timeout_seconds=90
                    )
                except Exception as ex:
                    server_error[0] = ex

            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()

            try:
                user_code = input("Waiting for redirect (or paste redirect URL / auth code here): ").strip()
                if user_code:
                    clean_code = extract_code_from_redirect(user_code)
                    flow.fetch_token(code=clean_code)
                    creds = flow.credentials
            except (EOFError, KeyboardInterrupt):
                pass

            if not creds:
                server_thread.join(timeout=30)
                creds = server_creds[0]

            if not creds:
                raise RuntimeError("Failed to complete YouTube OAuth authorization. Please try again.")

        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print(f"[Auth] Saved credentials to {TOKEN_FILE.name} for future headless runs.")

    return build("youtube", "v3", credentials=creds)


def upload_video_file(youtube, video_path: Path, title: str, description: str, tags: list, privacy_status: str) -> str:
    print(f"[Upload] Uploading {video_path.name} ({video_path.stat().st_size / (1024*1024):.1f} MB)...")
    print(f"         Title: {title}")
    print(f"         Privacy: {privacy_status}")

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": "27",
            "defaultLanguage": "bn",
            "defaultAudioLanguage": "bn",
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        }
    }

    media = MediaFileUpload(
        str(video_path),
        chunksize=10 * 1024 * 1024,
        resumable=True
    )

    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media
    )

    response = None
    last_reported_pct = -1
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            if pct != last_reported_pct:
                print(f"         Uploaded: {pct}%")
                last_reported_pct = pct

    video_id = response.get("id")
    print(f"[Upload] Finished! Video ID: {video_id}")
    return video_id


def set_video_thumbnail(youtube, video_id: str, thumbnail_path: Path):
    print(f"[Thumbnail] Uploading custom thumbnail {thumbnail_path.name}...")
    media = MediaFileUpload(str(thumbnail_path))
    youtube.thumbnails().set(
        videoId=video_id,
        media_body=media
    ).execute()
    print("[Thumbnail] Thumbnail applied successfully.")


def add_video_to_playlist(youtube, video_id: str, playlist_id: str):
    if not playlist_id:
        print("[Playlist] No playlist ID provided, skipping playlist addition.")
        return
    print(f"[Playlist] Adding video {video_id} to playlist {playlist_id}...")
    body = {
        "snippet": {
            "playlistId": playlist_id,
            "resourceId": {
                "kind": "youtube#video",
                "videoId": video_id
            }
        }
    }
    try:
        youtube.playlistItems().insert(
            part="snippet",
            body=body
        ).execute()
        print(f"[Playlist] Successfully added to playlist: https://www.youtube.com/playlist?list={playlist_id}")
    except HttpError as e:
        print(f"[Playlist] Warning: Could not add to playlist ({e})")


def main():
    parser = argparse.ArgumentParser(description="BUET Mosque Tafseer - YouTube Publisher")
    parser.add_argument("input_json", nargs="?", help="Path to input JSON (defaults to latest)")
    parser.add_argument("--video-path", help="Path to final video MP4 (defaults to output/final_video_YYYY_MM_DD.mp4)")
    parser.add_argument("--playlist-id", help="Target YouTube playlist ID (overrides .env YOUTUBE_PLAYLIST_ID)")
    parser.add_argument(
        "--privacy",
        choices=["public", "unlisted", "private"],
        default=os.environ.get("YOUTUBE_PRIVACY_STATUS", "public"),
        help="Privacy status (default: public)"
    )
    parser.add_argument("--thumbnail-only", action="store_true", help="Generate thumbnail only and exit")
    parser.add_argument("--dry-run", action="store_true", help="Generate thumbnail and print metadata without uploading")

    args = parser.parse_args()

    input_file = resolve_input_file(args.input_json)
    print(f"[Input] Using configuration: {input_file.name}")
    date_suffix = extract_date_suffix(input_file)

    with open(input_file, encoding="utf-8") as f:
        config = json.load(f)

    intro = config.get("intro", {})
    surah_name = intro.get("surah_name", "সূরা আলে-ইমরান")
    verse_range = intro.get("verse_range", "")
    speaker = intro.get("speaker", "মুফতি রাশেদুর রহমান")
    date_str = intro.get("date", "")

    # Format Title
    title = f"তাফসীরুল কুরআনঃ {surah_name}, আয়াত {verse_range} | {speaker} | বুয়েট কেন্দ্রীয় মসজিদ"

    # Format Description
    description = (
        f"{surah_name}, আয়াত {verse_range} এর ওপর সংক্ষিপ্ত তাফসীর আলোচনা।\n"
        f"আলোচকঃ {speaker}, খতিব, বুয়েট কেন্দ্রীয় মসজিদ।\n"
        f"প্রতি বুধবার বাদ এশা বুয়েট কেন্দ্রীয় মসজিদে এই তাফসীর হালাকাহ অনুষ্ঠিত হয়।\n\n"
        f"#তাফসীর #কুরআন #বুয়েট_কেন্দ্রীয়_মসজিদ #মুফতি_রাশেদুর_রহমান #Tafsir #BUETMosque"
    )

    tags = [
        "তাফসীর",
        "কুরআন",
        "বুয়েট কেন্দ্রীয় মসজিদ",
        "মুফতি রাশেদুর রহমান",
        "তাফসীরুল কুরআন",
        "BUET Mosque",
        "Tafsir",
        surah_name
    ]

    thumbnail_path = OUTPUT_DIR / f"thumbnail_{date_suffix}.jpg"
    generate_thumbnail(intro, thumbnail_path)

    if args.thumbnail_only:
        print(f"\n[Done] Thumbnail generated at: {thumbnail_path}")
        return

    # Locate Video
    if args.video_path:
        video_path = Path(args.video_path)
    else:
        video_path = OUTPUT_DIR / f"final_video_{date_suffix}.mp4"

    print("\n" + "=" * 60)
    print("YouTube Publishing Summary:")
    print(f"  • Video file:    {video_path}")
    print(f"  • Thumbnail:     {thumbnail_path}")
    print(f"  • Title:         {title}")
    print(f"  • Privacy:       {args.privacy}")
    playlist_id = args.playlist_id or os.environ.get("YOUTUBE_PLAYLIST_ID", "").strip()
    status_str = playlist_id if playlist_id else "(None specified in .env)"
    print(f"  • Playlist ID:   {status_str}")
    print("  • Description:")
    for line in description.splitlines():
        print(f"      {line}")
    print("=" * 60 + "\n")

    if args.dry_run:
        print("[Dry Run] Skipped upload and playlist insertion. Metadata and thumbnail verified!")
        return

    if not video_path.exists():
        raise FileNotFoundError(
            f"Video file not found at: {video_path}\n"
            "Please render the video first using python/render_verses.py before publishing."
        )

    # Authenticate and publish
    youtube = get_authenticated_service()
    video_id = upload_video_file(youtube, video_path, title, description, tags, args.privacy)
    set_video_thumbnail(youtube, video_id, thumbnail_path)
    if playlist_id:
        add_video_to_playlist(youtube, video_id, playlist_id)

    video_url = f"https://youtu.be/{video_id}"
    print("\n" + "*" * 60)
    print(f"🎉 SUCCESS! Video published to YouTube:")
    print(f"👉 Link: {video_url}")
    if playlist_id:
        print(f"👉 Playlist: https://www.youtube.com/playlist?list={playlist_id}")
    print("*" * 60 + "\n")


if __name__ == "__main__":
    main()
