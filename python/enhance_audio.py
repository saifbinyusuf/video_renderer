#!/usr/bin/env python3
"""Automated audio enhancement workflow using Adobe Podcast Enhance Speech via Microsoft Edge.

Workflow:
  1. Detects a raw audio clip (e.g. inputs/12. BUET Tafsir 2026-11-11-raw.mp3).
  2. Checks duration via ffprobe; if > 29.5 minutes, splits near a silence pause into equal chunks.
  3. Opens https://podcast.adobe.com/en/enhance in Microsoft Edge (dedicated persistent profile).
  4. Uploads each chunk sequentially, waits for Adobe enhancement, and downloads the enhanced MP3.
  5. Joins downloaded chunks (if split) and saves the final MP3 without the "-raw" suffix.
  6. Uploads the raw clip to Google Drive (separate account, e.g. icb.mail.info@gmail.com).
  7. Archives the original raw clip to inputs/raw_archive/ (or deletes it with --delete-raw).
"""

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

ADOBE_ENHANCE_URL = "https://podcast.adobe.com/en/enhance"
EDGE_APP_EXECUTABLE = Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")
DEFAULT_PROFILE_DIR = Path.home() / ".config" / "buet-tafsir-renderer" / "edge-profile"

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
INPUTS_DIR = PROJECT_ROOT / "inputs"
OUTPUT_DIR = PROJECT_ROOT / "output"

# Google Drive Upload Defaults (separate from Adobe Podcast account)
DEFAULT_DRIVE_FOLDER_ID = os.environ.get("DRIVE_RAW_FOLDER_ID", "1GtOYA7-UkNrsS6yxUdpKPuO0qf6DtJb3")
DEFAULT_DRIVE_ACCOUNT = os.environ.get("DRIVE_ACCOUNT_EMAIL", "icb.mail.info@gmail.com")
DRIVE_CLIENT_SECRET_FILE = PROJECT_ROOT / os.environ.get("YOUTUBE_CLIENT_SECRET_FILE", "client_secret.json")
DRIVE_TOKEN_FILE = PROJECT_ROOT / "token_drive.json"
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
DRIVE_OAUTH_PORT = 8085

AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
RAW_SUFFIX_RE = re.compile(r"(?:[-_\s]+raw)$", re.IGNORECASE)

DEFAULT_MAX_CHUNK_MIN = 29.5   # Safe margin under Adobe's 30-minute free-tier cap
DEFAULT_TIMEOUT_MIN = 20.0     # Max wait time per chunk for Adobe processing
SILENCE_WINDOW_SEC = 15.0      # +/- search window around target split point


def get_media_duration(path: Path) -> float:
    """Probes media duration in seconds using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


def probe_audio_stream(path: Path) -> dict:
    """Returns first audio stream metadata dict via ffprobe, or raises if none exists."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "a:0",
        "-show_entries", "stream=codec_name,sample_rate,channels,bit_rate",
        "-of", "json",
        str(path),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    streams = json.loads(res.stdout).get("streams", [])
    if not streams:
        raise ValueError(f"No audio stream found in {path}")
    return streams[0]


def resolve_raw_audio(input_arg: str | None, inputs_dir: Path = INPUTS_DIR) -> Path:
    """Resolves explicit input path or auto-detects a unique *-raw.<ext> file in inputs/."""
    if input_arg:
        for candidate in (Path(input_arg), PROJECT_ROOT / input_arg, inputs_dir / input_arg):
            if candidate.exists() and candidate.is_file():
                if candidate.suffix.lower() not in AUDIO_EXTENSIONS:
                    raise ValueError(f"Unsupported audio file extension: {candidate.name}")
                return candidate.resolve()
        raise FileNotFoundError(f"Input audio file not found: {input_arg}")

    if not inputs_dir.exists():
        raise FileNotFoundError(f"Inputs directory not found: {inputs_dir}")

    raw_candidates = sorted(
        f for f in inputs_dir.iterdir()
        if f.is_file()
        and not f.name.startswith(".")
        and f.suffix.lower() in AUDIO_EXTENSIONS
        and RAW_SUFFIX_RE.search(f.stem)
    )
    if not raw_candidates:
        raise FileNotFoundError(
            f"No '*-raw.<ext>' audio file found in {inputs_dir}. "
            "Place a raw clip like '12. BUET Tafsir 2026-11-11-raw.mp3' in inputs/ or pass a file path."
        )
    if len(raw_candidates) > 1:
        names = [f.name for f in raw_candidates]
        raise ValueError(
            f"Multiple raw audio files found in {inputs_dir}: {names}. "
            "Specify the exact file path as an argument."
        )
    return raw_candidates[0].resolve()


def derive_output_path(raw_path: Path, output_arg: str | None = None) -> Path:
    """Derives the enhanced .mp3 output path by stripping the '-raw' suffix."""
    if output_arg:
        p = Path(output_arg)
        if not p.is_absolute():
            p = PROJECT_ROOT / p
        return p.resolve()

    if RAW_SUFFIX_RE.search(raw_path.stem):
        clean_stem = RAW_SUFFIX_RE.sub("", raw_path.stem).rstrip(" -_")
    else:
        clean_stem = f"{raw_path.stem}_enhanced"

    return (raw_path.parent / f"{clean_stem}.mp3").resolve()


def find_silence_split_point(
    audio_path: Path,
    target_sec: float,
    min_sec: float,
    max_sec: float,
    window_sec: float = SILENCE_WINDOW_SEC,
) -> float:
    """Finds the silence midpoint closest to target_sec within [min_sec, max_sec]."""
    win_start = max(min_sec, target_sec - window_sec)
    win_end = min(max_sec, target_sec + window_sec)
    win_dur = win_end - win_start
    if win_dur <= 1.0:
        return target_sec

    cmd = [
        "ffmpeg", "-v", "info",
        "-ss", f"{win_start:.3f}",
        "-t", f"{win_dur:.3f}",
        "-i", str(audio_path),
        "-af", "silencedetect=noise=-30dB:d=0.25",
        "-f", "null", "-",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    stderr = res.stderr or ""

    starts: list[float] = []
    midpoints: list[float] = []
    for line in stderr.splitlines():
        m_start = re.search(r"silence_start:\s*([0-9.]+)", line)
        if m_start:
            starts.append(float(m_start.group(1)))
        m_end = re.search(r"silence_end:\s*([0-9.]+)", line)
        if m_end and starts:
            s_start = starts.pop(0)
            s_end = float(m_end.group(1))
            mid = win_start + (s_start + s_end) / 2.0
            if min_sec < mid < max_sec:
                midpoints.append(mid)

    if not midpoints:
        return target_sec

    best = min(midpoints, key=lambda t: abs(t - target_sec))
    return best


def split_audio(audio_path: Path, temp_dir: Path, max_chunk_sec: float) -> list[Path]:
    """Splits audio into silence-aligned MP3 chunks if duration exceeds max_chunk_sec."""
    duration = get_media_duration(audio_path)
    if duration <= max_chunk_sec:
        print(f"[Audio] Duration {duration / 60:.2f} min <= {max_chunk_sec / 60:.1f} min limit -> no split needed.")
        return [audio_path]

    num_chunks = math.ceil(duration / max_chunk_sec)
    print(
        f"[Audio] Duration {duration / 60:.2f} min exceeds {max_chunk_sec / 60:.1f} min -> "
        f"splitting into {num_chunks} chunks..."
    )

    boundaries = [0.0]
    for idx in range(1, num_chunks):
        ideal = duration * (idx / num_chunks)
        prev = boundaries[-1]
        # Guarantee current chunk <= max_chunk_sec and remaining chunks can each fit in max_chunk_sec
        remaining_chunks = num_chunks - idx
        min_allowed = max(prev + 1.0, duration - remaining_chunks * max_chunk_sec + 1.0)
        max_allowed = min(duration - 1.0, prev + max_chunk_sec - 1.0)
        clamped_ideal = min(max(ideal, min_allowed), max_allowed)
        split_pt = find_silence_split_point(audio_path, clamped_ideal, min_allowed, max_allowed)
        boundaries.append(split_pt)
    boundaries.append(duration)

    temp_dir.mkdir(parents=True, exist_ok=True)
    chunk_paths: list[Path] = []
    for i in range(num_chunks):
        start_sec = boundaries[i]
        seg_dur = boundaries[i + 1] - start_sec
        chunk_path = temp_dir / f"raw_part_{i + 1:02d}.mp3"
        cmd = [
            "ffmpeg", "-y", "-v", "error",
            "-ss", f"{start_sec:.3f}",
            "-t", f"{seg_dur:.3f}",
            "-i", str(audio_path),
            "-vn",
            "-c:a", "libmp3lame",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            str(chunk_path),
        ]
        subprocess.run(cmd, check=True)
        print(f"  • Chunk {i + 1}/{num_chunks}: {start_sec:.1f}s -> {boundaries[i + 1]:.1f}s ({seg_dur / 60:.2f} min)")
        chunk_paths.append(chunk_path)

    return chunk_paths


def run_manual_edge_login(profile_dir: Path):
    """Launches unmodified Microsoft Edge with the dedicated profile for one-time Adobe/Google login."""
    if not EDGE_APP_EXECUTABLE.exists():
        raise FileNotFoundError(f"Microsoft Edge executable not found at: {EDGE_APP_EXECUTABLE}")

    profile_dir.mkdir(parents=True, exist_ok=True)
    print("\n" + "=" * 68)
    print("Microsoft Edge One-Time Adobe Podcast Sign-In")
    print("=" * 68)
    print(f"Profile directory: {profile_dir}")
    print("1. A dedicated Microsoft Edge window will open to Adobe Podcast Enhance.")
    print("2. Sign in with your Google account (e.g. saifsearcher@gmail.com).")
    print("3. Confirm you can see the Enhance Speech upload screen.")
    print("4. Return here and press Enter (or quit Edge with Cmd+Q) to save & close.")
    print("=" * 68 + "\n")

    proc = subprocess.Popen(
        [
            str(EDGE_APP_EXECUTABLE),
            f"--user-data-dir={profile_dir}",
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-edgeupdater",
            ADOBE_ENHANCE_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    try:
        input("Press Enter once you are signed in and see the Enhance upload screen...")
    except (EOFError, KeyboardInterrupt):
        pass

    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()

    print("[Login] Edge closed cleanly. Session saved to dedicated profile.")


def _find_visible_locator(page, selectors: list[str], timeout_ms: int = 2000):
    """Returns the first locator matching one of selectors that is visible within timeout_ms."""
    for sel in selectors:
        loc = page.locator(sel).first
        try:
            if loc.is_visible(timeout=timeout_ms):
                return loc
        except Exception:
            continue
    return None


def _is_logged_in_enhance_ready(page) -> bool:
    """Checks whether Adobe Enhance Speech upload UI is loaded and user is signed in."""
    url = page.url.lower()
    if any(k in url for k in ("auth.services.adobe.com", "accounts.google.com", "ims-na1.adobelogin.com")):
        return False

    # Look for file input or upload button without a prominent Sign In gate
    upload_selectors = [
        'input[type="file"]',
        'button:has-text("Choose files")',
        'button:has-text("Upload")',
        'sp-button:has-text("Choose files")',
        'sp-button:has-text("Upload")',
    ]
    for sel in upload_selectors:
        try:
            if page.locator(sel).count() > 0:
                return True
        except Exception:
            continue
    return False


def _upload_chunk(page, chunk_path: Path):
    """Uploads an audio file to the Adobe Podcast Enhance page."""
    # Prefer direct hidden/visible file input when available (works across Shadow DOM in Playwright)
    file_inputs = page.locator('input[type="file"]')
    if file_inputs.count() > 0:
        file_inputs.first.set_input_files(str(chunk_path))
        return

    # Fallback: click Upload / Choose files button via file chooser event
    trigger_selectors = [
        'button:has-text("Choose files")',
        'button:has-text("Upload")',
        'sp-button:has-text("Choose files")',
        'sp-button:has-text("Upload")',
        '[aria-label*="Upload" i]',
        '[aria-label*="Choose" i]',
    ]
    btn = _find_visible_locator(page, trigger_selectors, timeout_ms=5000)
    if btn is None:
        raise RuntimeError("Could not locate file upload input or Upload button on Adobe Podcast Enhance.")

    with page.expect_file_chooser(timeout=15000) as fc_info:
        btn.click()
    fc_info.value.set_files(str(chunk_path))


def _wait_and_download(page, download_dest: Path, timeout_sec: float) -> Path:
    """Waits until Adobe finishes enhancing and downloads the processed file."""
    # Allow Adobe's UI to transition from idle/previous clip to uploading/enhancing state
    time.sleep(3.0)

    download_selectors = [
        'button:has-text("Download"):not([disabled])',
        'a:has-text("Download")',
        'sp-button:has-text("Download"):not([disabled])',
        '[aria-label*="Download" i]:not([disabled])',
    ]
    busy_texts = ("Enhancing speech", "Uploading")

    deadline = time.time() + timeout_sec
    last_log = 0.0
    dl_button = None

    while time.time() < deadline:
        # Check for daily limit / file error messages early
        for err_text in ("daily limit", "exceeds", "something went wrong", "too long", "unsupported"):
            try:
                err_loc = page.get_by_text(err_text, exact=False).first
                if err_loc.is_visible(timeout=200):
                    msg = err_loc.inner_text(timeout=500).strip()
                    raise RuntimeError(f"Adobe Podcast reported an error: {msg}")
            except RuntimeError:
                raise
            except Exception:
                pass

        is_busy = False
        for busy in busy_texts:
            try:
                if page.get_by_text(busy, exact=False).first.is_visible(timeout=200):
                    is_busy = True
                    break
            except Exception:
                continue

        if not is_busy:
            for sel in download_selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.is_visible(timeout=300) and loc.is_enabled(timeout=300):
                        dl_button = loc
                        break
                except Exception:
                    continue

        if dl_button is not None:
            break

        now = time.time()
        if now - last_log >= 15.0:
            elapsed = int(timeout_sec - (deadline - now))
            print(f"    ... still enhancing ({elapsed}s elapsed)")
            last_log = now
        time.sleep(2.0)

    if dl_button is None:
        raise TimeoutError(f"Timed out after {timeout_sec / 60:.1f} min waiting for Download button.")

    print("    Enhancement complete! Downloading...")
    with page.expect_download(timeout=180000) as dl_info:
        dl_button.click()
    download = dl_info.value
    suggested_ext = Path(download.suggested_filename).suffix or ".mp3"
    final_dest = download_dest.with_suffix(suggested_ext)
    download.save_as(str(final_dest))
    print(f"    Downloaded: {final_dest.name} ({final_dest.stat().st_size / (1024 * 1024):.1f} MB)")
    return final_dest


def enhance_chunks_in_edge(
    chunks: list[Path],
    temp_dir: Path,
    profile_dir: Path,
    timeout_min: float = DEFAULT_TIMEOUT_MIN,
) -> list[Path]:
    """Drives Microsoft Edge via Playwright to enhance each audio chunk sequentially."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ImportError(
            "Playwright is not installed. Run: pip3 install playwright"
        ) from exc

    profile_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    downloaded_files: list[Path] = []
    timeout_sec = timeout_min * 60.0

    with sync_playwright() as p:
        print(f"[Edge] Launching Microsoft Edge with profile: {profile_dir}")
        context = p.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            channel="msedge",
            headless=False,
            accept_downloads=True,
            ignore_default_args=["--use-mock-keychain", "--password-store=basic"],
            viewport=None,
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(ADOBE_ENHANCE_URL, wait_until="domcontentloaded", timeout=60000)

            # Give Adobe's SPA + silent IMS token refresh time to hydrate (reload once if stalled)
            ready = False
            for attempt, wait_sec in enumerate((12.0, 10.0), start=1):
                hydrate_deadline = time.time() + wait_sec
                while time.time() < hydrate_deadline:
                    if _is_logged_in_enhance_ready(page):
                        ready = True
                        break
                    time.sleep(1.0)
                if ready:
                    break
                if attempt == 1:
                    print("[Edge] Waiting for Adobe silent session refresh (reloading once)...")
                    page.reload(wait_until="domcontentloaded", timeout=60000)

            if not ready:
                print("\n[Auth] Adobe Podcast Enhance upload screen not detected (sign-in may be required).")
                print("       Sign in inside the open Edge window, or cancel and run:")
                print("       python3 python/enhance_audio.py --login-only")
                login_deadline = time.time() + 300
                while time.time() < login_deadline:
                    if _is_logged_in_enhance_ready(page):
                        break
                    time.sleep(2.0)
                if not _is_logged_in_enhance_ready(page):
                    debug_shot = temp_dir / "adobe_login_timeout.png"
                    page.screenshot(path=str(debug_shot), full_page=True)
                    raise TimeoutError(
                        f"Timed out waiting for Adobe Podcast login/upload UI. Screenshot saved: {debug_shot}"
                    )

            for idx, chunk in enumerate(chunks, start=1):
                print(f"[Enhance {idx}/{len(chunks)}] Uploading {chunk.name}...")
                if idx > 1:
                    page.goto(ADOBE_ENHANCE_URL, wait_until="domcontentloaded", timeout=60000)
                    time.sleep(3.0)
                    # Clear any persisted previous clip in UI if a Delete/Remove/Upload another button exists
                    clear_btn = _find_visible_locator(
                        page,
                        [
                            'button:has-text("Upload another")',
                            'button:has-text("Delete")',
                            'button[aria-label*="Delete" i]',
                            'button[aria-label*="Remove" i]',
                            'sp-action-button[aria-label*="Delete" i]',
                        ],
                        timeout_ms=2500,
                    )
                    if clear_btn is not None and page.locator('input[type="file"]').count() == 0:
                        clear_btn.click()
                        time.sleep(1.5)

                try:
                    _upload_chunk(page, chunk)
                    dest = temp_dir / f"enhanced_part_{idx:02d}.mp3"
                    dl_path = _wait_and_download(page, dest, timeout_sec=timeout_sec)
                    downloaded_files.append(dl_path)
                except Exception:
                    debug_shot = temp_dir / f"adobe_error_part_{idx:02d}.png"
                    try:
                        page.screenshot(path=str(debug_shot), full_page=True)
                        print(f"[Debug] Saved error screenshot to: {debug_shot}")
                    except Exception:
                        pass
                    raise
        finally:
            context.close()

    return downloaded_files


def join_and_save(enhanced_files: list[Path], output_path: Path):
    """Saves single enhanced MP3 directly or joins multiple chunks into a clean 48 kHz stereo MP3."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_out = output_path.with_name(f".{output_path.stem}.tmp.mp3")

    try:
        if len(enhanced_files) == 1 and enhanced_files[0].suffix.lower() == ".mp3":
            print(f"[Output] Copying enhanced MP3 directly -> {output_path.name}")
            shutil.copy2(enhanced_files[0], tmp_out)
        elif len(enhanced_files) == 1:
            print(f"[Output] Transcoding {enhanced_files[0].name} -> {output_path.name} (48 kHz stereo 192 kbps MP3)...")
            cmd = [
                "ffmpeg", "-y", "-v", "error",
                "-i", str(enhanced_files[0]),
                "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                str(tmp_out),
            ]
            subprocess.run(cmd, check=True)
        else:
            print(f"[Output] Joining {len(enhanced_files)} enhanced chunks -> {output_path.name}...")
            cmd = ["ffmpeg", "-y", "-v", "error"]
            filter_parts = []
            concat_inputs = []
            for idx, fpath in enumerate(enhanced_files):
                cmd.extend(["-i", str(fpath)])
                filter_parts.append(f"[{idx}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{idx}]")
                concat_inputs.append(f"[a{idx}]")
            filter_complex = (
                ";".join(filter_parts)
                + ";"
                + "".join(concat_inputs)
                + f"concat=n={len(enhanced_files)}:v=0:a=1[outa]"
            )
            cmd.extend([
                "-filter_complex", filter_complex,
                "-map", "[outa]",
                "-c:a", "libmp3lame", "-b:a", "192k", "-ar", "48000", "-ac", "2",
                str(tmp_out),
            ])
            subprocess.run(cmd, check=True)

        tmp_out.replace(output_path)
    finally:
        if tmp_out.exists():
            tmp_out.unlink()


def verify_output(output_path: Path, expected_duration: float):
    """Validates that output_path exists, has a valid audio stream, and has plausible duration."""
    if not output_path.exists() or output_path.stat().st_size == 0:
        raise RuntimeError(f"Output file is missing or empty: {output_path}")

    stream = probe_audio_stream(output_path)
    actual_duration = get_media_duration(output_path)
    drift = abs(actual_duration - expected_duration)
    if actual_duration < expected_duration * 0.5:
        raise RuntimeError(
            f"Enhanced output duration ({actual_duration:.1f}s) is far shorter than raw input ({expected_duration:.1f}s)."
        )
    if drift > max(5.0, expected_duration * 0.03):
        print(
            f"[Verify] Warning: duration differs from raw input by {drift:.1f}s "
            f"(raw={expected_duration:.1f}s, enhanced={actual_duration:.1f}s)."
        )
    print(
        f"[Verify] OK: {output_path.name} ({stream.get('codec_name')}, "
        f"{stream.get('sample_rate')} Hz, {stream.get('channels')}ch, {actual_duration / 60:.2f} min)"
    )


class _ReusableThreadingHTTPServer(ThreadingHTTPServer):
    """Multi-threaded local OAuth callback server that will not deadlock on idle browser sockets."""
    allow_reuse_address = True
    daemon_threads = True


def _run_drive_oauth_server(flow, login_hint: str, port: int = DRIVE_OAUTH_PORT, timeout_seconds: int = 180):
    """Runs a threaded local OAuth callback server for Google Drive authorization."""
    flow.redirect_uri = f"http://localhost:{port}/"
    auth_kwargs = {"prompt": "consent", "access_type": "offline"}
    if login_hint:
        auth_kwargs["login_hint"] = login_hint
    auth_url, _ = flow.authorization_url(**auth_kwargs)

    received_event = threading.Event()
    result = {"path": None, "error": None}
    result_lock = threading.Lock()

    class _CallbackHandler(BaseHTTPRequestHandler):
        def setup(self):
            self.request.settimeout(5.0)
            super().setup()

        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            params = urllib.parse.parse_qs(parsed.query)
            if "code" in params or "error" in params:
                with result_lock:
                    if not received_event.is_set():
                        result["path"] = self.path
                        result["error"] = params.get("error", [None])[0]
                        received_event.set()
                msg = (
                    "<html><body><h2>Google Drive authorization failed</h2>"
                    "<p>Check the terminal for details.</p></body></html>"
                    if result["error"]
                    else "<html><body><h2>Google Drive authorization complete!</h2>"
                    "<p>You may close this tab and return to the terminal.</p></body></html>"
                ).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(msg)))
                self.send_header("Connection", "close")
                self.end_headers()
                self.wfile.write(msg)
            else:
                self.send_response(204)
                self.send_header("Connection", "close")
                self.end_headers()

    server = _ReusableThreadingHTTPServer(("127.0.0.1", port), _CallbackHandler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    try:
        print("\n" + "=" * 68)
        print("Google Drive Authorization Required (One-Time Setup)")
        print("=" * 68)
        print(f"1. Open this URL in your browser and sign in as: {login_hint}")
        print(f"   {auth_url}")
        print("2. Click 'Allow' — authorization will complete automatically.")
        print("=" * 68 + "\n", flush=True)
        if not received_event.wait(timeout=timeout_seconds):
            raise TimeoutError(f"Timed out after {timeout_seconds}s waiting for Google Drive OAuth callback.")
    finally:
        server.shutdown()
        server.server_close()

    if result["error"]:
        raise RuntimeError(f"Google Drive OAuth returned error: {result['error']}")

    authorization_response = f"https://localhost:{port}{result['path']}"
    flow.fetch_token(authorization_response=authorization_response)
    return flow.credentials


def get_drive_service(drive_account: str = DEFAULT_DRIVE_ACCOUNT):
    """Authenticates and returns a Google Drive API v3 service using token_drive.json."""
    try:
        import google.auth.transport.requests
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "Google Drive dependencies are missing on host Python. "
            "Run: pip3 install google-api-python-client google-auth-oauthlib"
        ) from exc

    creds = None
    if DRIVE_TOKEN_FILE.exists() and DRIVE_TOKEN_FILE.is_file() and DRIVE_TOKEN_FILE.stat().st_size > 0:
        try:
            creds = Credentials.from_authorized_user_file(str(DRIVE_TOKEN_FILE), DRIVE_SCOPES)
        except Exception as exc:
            print(f"[Drive Auth] Warning: could not load {DRIVE_TOKEN_FILE.name}: {exc}")
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            print("[Drive Auth] Refreshing expired Google Drive access token...")
            try:
                creds.refresh(google.auth.transport.requests.Request())
            except Exception as exc:
                print(f"[Drive Auth] Stored refresh token invalid/revoked ({exc}); starting fresh login...")
                creds = None

        if not creds or not creds.valid:
            if not DRIVE_CLIENT_SECRET_FILE.exists() or DRIVE_CLIENT_SECRET_FILE.stat().st_size == 0:
                raise FileNotFoundError(
                    f"Google OAuth client secret not found at: {DRIVE_CLIENT_SECRET_FILE}"
                )
            flow = InstalledAppFlow.from_client_secrets_file(str(DRIVE_CLIENT_SECRET_FILE), DRIVE_SCOPES)
            creds = _run_drive_oauth_server(flow, login_hint=drive_account)

        DRIVE_TOKEN_FILE.write_text(creds.to_json(), encoding="utf-8")
        print(f"[Drive Auth] Saved credentials to {DRIVE_TOKEN_FILE.name} for future headless uploads.")

    return build("drive", "v3", credentials=creds)


def verify_drive_folder(drive, folder_id: str) -> str:
    """Verifies Drive API access and target folder existence; returns folder name."""
    from googleapiclient.errors import HttpError

    try:
        meta = drive.files().get(
            fileId=folder_id,
            fields="id,name,mimeType",
            supportsAllDrives=True,
        ).execute()
    except HttpError as exc:
        detail = str(exc)
        if "accessNotConfigured" in detail or "has not been used" in detail:
            raise RuntimeError(
                "Google Drive API is not enabled on your Google Cloud project yet. "
                "Enable it using the link in the error above, wait ~1 minute, and retry."
            ) from exc
        raise
    return meta.get("name", folder_id)


def upload_raw_to_drive(
    raw_path: Path,
    folder_id: str = DEFAULT_DRIVE_FOLDER_ID,
    drive_account: str = DEFAULT_DRIVE_ACCOUNT,
) -> str:
    """Uploads raw audio clip to the target Google Drive folder using resumable chunked upload."""
    from googleapiclient.http import MediaFileUpload

    drive = get_drive_service(drive_account=drive_account)
    folder_name = verify_drive_folder(drive, folder_id)

    mime_type = mimetypes.guess_type(raw_path.name)[0] or "audio/mpeg"
    size_mb = raw_path.stat().st_size / (1024 * 1024)
    print(f"[Drive] Uploading {raw_path.name} ({size_mb:.1f} MB) -> Drive folder '{folder_name}'...")

    body = {
        "name": raw_path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(
        str(raw_path),
        mimetype=mime_type,
        chunksize=10 * 1024 * 1024,
        resumable=True,
    )
    request = drive.files().create(
        body=body,
        media_body=media,
        fields="id,name,webViewLink",
        supportsAllDrives=True,
    )

    response = None
    last_pct = -1
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            if pct != last_pct:
                print(f"        Uploaded: {pct}%")
                last_pct = pct

    file_id = response["id"]
    link = response.get("webViewLink") or f"https://drive.google.com/file/d/{file_id}/view"
    print(f"[Drive] Upload complete! {link}")
    return link


def handle_raw_file(raw_path: Path, delete_raw: bool = False):
    """Moves the raw input clip to inputs/raw_archive/ or deletes it when delete_raw=True."""
    if delete_raw:
        raw_path.unlink()
        print(f"[Cleanup] Deleted raw file: {raw_path.name}")
        return

    archive_dir = raw_path.parent / "raw_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    dest = archive_dir / raw_path.name
    if dest.exists():
        stamp = time.strftime("%Y%m%d_%H%M%S")
        dest = archive_dir / f"{raw_path.stem}_{stamp}{raw_path.suffix}"
    shutil.move(str(raw_path), str(dest))
    print(f"[Cleanup] Archived raw file -> {dest.relative_to(PROJECT_ROOT) if dest.is_relative_to(PROJECT_ROOT) else dest}")


def main():
    parser = argparse.ArgumentParser(
        description="Enhance weekly lecture audio via Adobe Podcast Enhance Speech in Microsoft Edge."
    )
    parser.add_argument(
        "input_audio",
        nargs="?",
        default=None,
        help="Path to raw audio clip (default: auto-detect *-raw.<ext> in inputs/)",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional explicit output MP3 path (default: strip '-raw' in inputs/)",
    )
    parser.add_argument(
        "--login-only",
        action="store_true",
        help="Open dedicated Microsoft Edge profile to sign into Adobe Podcast, then exit",
    )
    parser.add_argument(
        "--drive-login-only",
        action="store_true",
        help="Complete one-time Google Drive OAuth login (icb.mail.info@gmail.com) and verify folder access",
    )
    parser.add_argument(
        "--upload-raw-only",
        action="store_true",
        help="Only upload the specified/detected raw audio clip to Google Drive (skip Adobe Enhance)",
    )
    parser.add_argument(
        "--skip-drive",
        action="store_true",
        help="Skip uploading the raw clip to Google Drive after enhancement",
    )
    parser.add_argument(
        "--drive-folder-id",
        default=DEFAULT_DRIVE_FOLDER_ID,
        help=f"Target Google Drive folder ID for raw clip backup (default: {DEFAULT_DRIVE_FOLDER_ID})",
    )
    parser.add_argument(
        "--drive-account",
        default=DEFAULT_DRIVE_ACCOUNT,
        help=f"Google account email hint for Drive upload (default: {DEFAULT_DRIVE_ACCOUNT})",
    )
    parser.add_argument(
        "--profile-dir",
        default=str(DEFAULT_PROFILE_DIR),
        help=f"Dedicated Edge user-data-dir (default: {DEFAULT_PROFILE_DIR})",
    )
    parser.add_argument(
        "--max-chunk-min",
        type=float,
        default=DEFAULT_MAX_CHUNK_MIN,
        help=f"Max duration in minutes per chunk before splitting (default: {DEFAULT_MAX_CHUNK_MIN})",
    )
    parser.add_argument(
        "--timeout-min",
        type=float,
        default=DEFAULT_TIMEOUT_MIN,
        help=f"Max minutes to wait per chunk for Adobe processing (default: {DEFAULT_TIMEOUT_MIN})",
    )
    parser.add_argument(
        "--delete-raw",
        action="store_true",
        help="Delete the raw input clip instead of moving it to inputs/raw_archive/",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output file if it already exists",
    )
    parser.add_argument(
        "--keep-temp",
        action="store_true",
        help="Keep temporary split/downloaded chunks in output/.enhance_tmp/",
    )
    args = parser.parse_args()

    profile_dir = Path(args.profile_dir).expanduser().resolve()

    if args.login_only:
        run_manual_edge_login(profile_dir)
        return

    if args.drive_login_only:
        drive = get_drive_service(drive_account=args.drive_account)
        folder_name = verify_drive_folder(drive, args.drive_folder_id)
        print(f"[Drive Auth] Verified access to Drive folder: '{folder_name}' ({args.drive_folder_id})")
        return

    raw_path = resolve_raw_audio(args.input_audio)

    if args.upload_raw_only:
        upload_raw_to_drive(raw_path, folder_id=args.drive_folder_id, drive_account=args.drive_account)
        return

    output_path = derive_output_path(raw_path, args.output)

    if output_path.exists() and not args.force:
        raise FileExistsError(
            f"Output file already exists: {output_path}. Pass --force to overwrite."
        )

    raw_duration = get_media_duration(raw_path)
    print("=" * 64)
    print("BUET Mosque Tafseer Audio Enhancement Plan:")
    print(f"  • Raw input:    {raw_path.name} ({raw_duration / 60:.2f} min)")
    print(f"  • Output MP3:   {output_path.name}")
    print(f"  • Chunk cap:    {args.max_chunk_min:.2f} min")
    print(f"  • Drive backup: {'SKIP (--skip-drive)' if args.skip_drive else f'{args.drive_account} -> folder {args.drive_folder_id}'}")
    print(f"  • Raw cleanup:  {'DELETE (--delete-raw)' if args.delete_raw else 'Move to inputs/raw_archive/'}")
    print("=" * 64)

    temp_dir = OUTPUT_DIR / ".enhance_tmp"
    if temp_dir.exists():
        shutil.rmtree(temp_dir, ignore_errors=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    try:
        chunks = split_audio(raw_path, temp_dir, max_chunk_sec=args.max_chunk_min * 60.0)
        enhanced_files = enhance_chunks_in_edge(
            chunks=chunks,
            temp_dir=temp_dir,
            profile_dir=profile_dir,
            timeout_min=args.timeout_min,
        )
        join_and_save(enhanced_files, output_path)
        verify_output(output_path, expected_duration=raw_duration)
        if not args.skip_drive:
            upload_raw_to_drive(raw_path, folder_id=args.drive_folder_id, drive_account=args.drive_account)
        handle_raw_file(raw_path, delete_raw=args.delete_raw)
        print(f"\n[Done] Enhanced audio ready at: {output_path}")
    finally:
        if not args.keep_temp and temp_dir.exists():
            shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
