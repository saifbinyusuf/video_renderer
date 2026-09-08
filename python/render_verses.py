import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

FPS = 30
SILENCE_DURATION = 1.5  # 1.5s silence after speech ends before extro begins
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}

# Channel Watermark Controls (Bottom-Right Logo)
CHANNEL_LOGO_WIDTH = 180
CHANNEL_LOGO_OPACITY = 0.5
CHANNEL_LOGO_RIGHT = 50
CHANNEL_LOGO_BOTTOM = 40

# Extro Audio Volume Controls (e.g. 1.0 = 100%, 0.8 = 80%, 1.2 = 120%)
EXTRO_INVITE_VOLUME = 1.0
EXTRO_VERSE_VOLUME = 0.3

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def find_asset(filename: str) -> Path:
    """Finds an asset checking remotion/src first, then assets (Docker or Host)."""
    candidates = [
        REMOTION_DIR / "src" / filename,
        PROJECT_ROOT / "remotion" / "src" / filename,
        Path("/app/remotion/src") / filename,
        ASSETS_DIR / filename,
        PROJECT_ROOT / "assets" / filename,
        Path("/app/assets") / filename,
    ]
    for c in candidates:
        if c.exists():
            return c
    raise FileNotFoundError(f"Asset '{filename}' not found in remotion/src or assets.")


def resolve_path(docker_path_str: str, fallback_path: Path) -> Path:
    p = Path(docker_path_str)
    if p.exists():
        return p
    return fallback_path


DATA_PATH = resolve_path("/app/data/quran_taisirul_bengali.json", PROJECT_ROOT / "data" / "quran_taisirul_bengali.json")
REMOTION_DIR = resolve_path("/app/remotion", PROJECT_ROOT / "remotion")
OUTPUT_DIR = resolve_path("/app/output", PROJECT_ROOT / "output")
INPUTS_DIR = resolve_path("/app/inputs", PROJECT_ROOT / "inputs")
ASSETS_DIR = resolve_path("/app/assets", PROJECT_ROOT / "assets")


def find_speech_audio(inputs_dir: Path) -> Path:
    """Finds and validates the speech audio clip in inputs directory.
    There must be exactly one audio clip. If 0 or >1, throws an error.
    """
    audio_files = [
        f for f in inputs_dir.iterdir()
        if f.is_file() and f.suffix.lower() in AUDIO_EXTENSIONS and not f.name.startswith(".")
    ]

    if len(audio_files) == 0:
        raise FileNotFoundError(
            f"No audio file found in inputs directory '{inputs_dir}'. "
            f"Exactly one speech audio clip must be present."
        )
    if len(audio_files) > 1:
        names = [f.name for f in audio_files]
        raise ValueError(
            f"Multiple audio files found in inputs directory '{inputs_dir}': {names}. "
            f"There can be exactly one clip in this directory."
        )

    return audio_files[0]


def get_media_duration(path: Path) -> float:
    """Probes media duration using ffprobe in seconds."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return float(res.stdout.strip())


def load_verse_db(path=DATA_PATH):
    if not Path(path).exists():
        raise FileNotFoundError(
            print("[Warning] Quran database not found. If all verses use 'custom_text' mode, the database is not needed.")
        )
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["verse_key"]: e for e in entries}


def build_props(tafsir_input, db=None):
    default_mode = str(tafsir_input.get("mode", "verse")).strip().lower()
    if default_mode == "standard":
        default_mode = "verse"
    elif default_mode == "custom":
        default_mode = "custom_text"

    items = tafsir_input.get("segments") or tafsir_input.get("verses", [])

    if not items:
        raise ValueError("No verses or segments found in input file.")

    intro = tafsir_input.get("intro")

    first_verse_start = 15.057
    if "start" in items[0]:
        try:
            first_verse_start = float(items[0]["start"])
        except (ValueError, TypeError):
            first_verse_start = 15.057

    verses = []
    for idx, v in enumerate(items):
        if "end" in v and "start" in v:
            duration_sec = float(v["end"]) - float(v["start"])
        elif "duration" in v:
            duration_sec = float(v["duration"])
        else:
            raise KeyError(f"Item #{idx + 1} must specify either 'start' and 'end' or 'duration'.")

        if duration_sec <= 0:
            raise ValueError(f"Non-positive duration for item #{idx + 1}: {duration_sec}s")

        # Per-verse mode resolution: "verse" (fetch from DB) or "custom_text" (take provided text)
        item_mode = str(v.get("mode") or v.get("type") or "").strip().lower()
        if item_mode in ("standard", "db", "quran"):
            item_mode = "verse"
        elif item_mode in ("custom", "text"):
            item_mode = "custom_text"

        has_custom_text = (
            ("arabic" in v or "arabic_text" in v)
            and ("bengali" in v or "bengali_translation" in v or "translation" in v)
        )

        if not item_mode:
            if has_custom_text:
                item_mode = "custom_text"
            elif "verse_key" in v or "verseKey" in v:
                item_mode = "verse"
            else:
                item_mode = default_mode

        if item_mode == "custom_text":
            arabic = v.get("arabic") or v.get("arabic_text")
            bengali = v.get("bengali") or v.get("bengali_translation") or v.get("translation")
            if not arabic:
                raise ValueError(f"Item #{idx + 1} ('custom_text' mode) missing 'arabic' text.")
            if not bengali:
                raise ValueError(f"Item #{idx + 1} ('custom_text' mode) missing 'bengali' translation.")
            verse_key = v.get("verse_key") or v.get("verseKey") or v.get("label") or f"custom_{idx + 1}"
        elif item_mode == "verse":
            verse_key = v.get("verse_key") or v.get("verseKey")
            if not verse_key:
                raise KeyError(f"Item #{idx + 1} ('verse' mode) missing 'verse_key'.")
            if db is None:
                db = load_verse_db()
            entry = db.get(verse_key)
            if entry is None:
                raise KeyError(f"Verse key not found in database: {verse_key}")
            arabic = entry["arabic_text"]
            bengali = entry["bengali_translation"]
        else:
            raise ValueError(
                f"Item #{idx + 1} has unrecognized mode: '{item_mode}'. Must be 'verse' or 'custom_text'."
            )

        verses.append({
            "verseKey": str(verse_key),
            "arabic": arabic.strip(),
            "bengali": bengali.strip(),
            "durationInFrames": round(duration_sec * FPS),
        })

    return {
        "intro": intro,
        "firstVerseStartSec": first_verse_start,
        "verses": verses,
    }


def calculate_intro_duration(props: dict) -> tuple[int, float]:
    """Calculates intro scene frames and duration matching Remotion metadata."""
    verses = props.get("verses", [])
    first_verse_start = props.get("firstVerseStartSec", 15.057)
    first_verse_frame = max(round(first_verse_start * FPS), 150)
    total_verses_frames = sum(v["durationInFrames"] for v in verses)
    # 30 hold + 38 scroll close + 30 mosque hold (fading to black in final 30 frames)
    intro_frames = max(first_verse_frame + total_verses_frames + 30 + 38 + 30, FPS)
    intro_sec = intro_frames / float(FPS)
    return intro_frames, intro_sec


def write_clean_config():
    config_path = REMOTION_DIR / "tmp_config.ts"
    config_path.write_text(
        'import { Config } from "@remotion/cli/config";\n\nConfig.setCodec("h264");\n',
        encoding="utf-8"
    )
    return config_path


def render_intro_scene(props: dict, speech_audio_path: Path, intro_duration: float, out_path: Path):
    """Step 1: Render Remotion VerseSequence and mux speech audio from t=0 to intro_duration."""
    props_path = REMOTION_DIR / "tmp_intro_props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")
    config_path = write_clean_config()

    raw_intro = OUTPUT_DIR / "intro_raw.mp4"

    cmd = [
        "npx", "remotion", "render",
        "src/index.ts", "VerseSequence",
        str(raw_intro),
        f"--props={props_path}",
        f"--config={config_path}",
        "--codec=h264",
    ]
    chromium_path = os.environ.get("REMOTION_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")
    if Path(chromium_path).exists():
        cmd.append(f"--browser-executable={chromium_path}")

    print(f"[Scene 1/3] Rendering Intro + Verses sequence ({intro_duration:.2f}s) via Remotion...")
    subprocess.run(cmd, cwd=REMOTION_DIR, check=True)

    print(f"[Scene 1/3] Muxing speech audio (0.0s -> {intro_duration:.2f}s) into intro clip...")
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_intro),
        "-ss", "0",
        "-t", f"{intro_duration:.3f}",
        "-i", str(speech_audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        "-shortest",
        str(out_path)
    ]
    subprocess.run(mux_cmd, check=True)

    if raw_intro.exists():
        raw_intro.unlink()
    print(f"[Scene 1/3] Finished: {out_path.name}")


def render_watermark_still(surah_name: str, verse_range: str, out_path: Path):
    """Step 2: Render 1920x1080 transparent PNG watermark using Remotion Still."""
    props = {
        "surah_name": surah_name,
        "verse_range": verse_range,
    }
    props_path = REMOTION_DIR / "tmp_watermark_props.json"
    props_path.write_text(json.dumps(props, ensure_ascii=False, indent=2), encoding="utf-8")

    cmd = [
        "npx", "remotion", "still",
        "src/index.ts", "SpeechWatermark",
        str(out_path),
        f"--props={props_path}",
    ]
    chromium_path = os.environ.get("REMOTION_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")
    if Path(chromium_path).exists():
        cmd.append(f"--browser-executable={chromium_path}")

    print(f"[Watermark] Rendering top-left watermark still ({surah_name}, আয়াত {verse_range})...")
    subprocess.run(cmd, cwd=REMOTION_DIR, check=True)
    print(f"[Watermark] Finished: {out_path.name}")


def render_extro_scene(out_path: Path):
    """Step 3: Render Extro scene (~13.7s) via Remotion."""
    config_path = write_clean_config()
    raw_extro = OUTPUT_DIR / "extro_raw.mp4"

    cmd = [
        "npx", "remotion", "render",
        "src/index.ts", "ExtroScene",
        str(raw_extro),
        f"--config={config_path}",
        "--codec=h264",
    ]
    chromium_path = os.environ.get("REMOTION_CHROMIUM_EXECUTABLE_PATH", "/usr/bin/chromium")
    if Path(chromium_path).exists():
        cmd.append(f"--browser-executable={chromium_path}")

    print("[Scene 3/3] Rendering Extro scene (~13.7s) via Remotion...")
    subprocess.run(cmd, cwd=REMOTION_DIR, check=True)

    norm_cmd = [
        "ffmpeg", "-y",
        "-i", str(raw_extro),
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-ac", "2",
        str(out_path)
    ]
    subprocess.run(norm_cmd, check=True)

    if raw_extro.exists():
        raw_extro.unlink()
    print(f"[Scene 3/3] Finished: {out_path.name}")


def get_video_frame_count(path: Path) -> int:
    """Gets total video frames using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=nb_frames",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, check=True)
        val = res.stdout.strip()
        if val.isdigit():
            return int(val)
    except Exception:
        pass
    dur = get_media_duration(path)
    return max(1, round(dur * FPS))


def render_speech_scene(
    speech_bg_path: Path,
    watermark_path: Path,
    speech_audio_path: Path,
    intro_duration: float,
    speech_audio_remaining: float,
    speech_scene_duration: float,
    out_path: Path,
    channel_logo_path: Path = None
):
    """Step 4: Render Scene 2 (Main Speech) using Option A Loop Stream-Copy.
    - Encodes Head (152 frames / ~5.07s) with fade-in and watermark fade
    - Encodes Body loop unit (152 frames / ~5.07s) with watermark
    - Encodes Tail (remainder frames) with fade-out
    - Stream-copies sequence with -c copy in ~3-4 seconds
    - Muxes speech audio with silence padding in ~1.5 seconds
    Total render time: ~8 seconds (down from ~7.5 minutes).
    """
    if channel_logo_path is None:
        try:
            channel_logo_path = find_asset("icb_logo.png")
        except Exception:
            channel_logo_path = None

    has_logo = channel_logo_path is not None and channel_logo_path.exists()
    logo_overlay_pos = f"W-w-{CHANNEL_LOGO_RIGHT}:H-h-{CHANNEL_LOGO_BOTTOM}"

    total_speech_frames = round(speech_scene_duration * FPS)
    loop_frames = get_video_frame_count(speech_bg_path)
    if loop_frames <= 0:
        loop_frames = 152

    print(
        f"[Scene 2/3] Rendering Main Speech scene ({speech_scene_duration:.2f}s / "
        f"{total_speech_frames} frames) via Loop Stream-Copy..."
    )

    try:
        temp_head = OUTPUT_DIR / "temp_speech_head.mp4"
        temp_body = OUTPUT_DIR / "temp_speech_body.mp4"
        temp_tail = OUTPUT_DIR / "temp_speech_tail.mp4"
        temp_video_raw = OUTPUT_DIR / "temp_speech_video_raw.mp4"
        speech_concat_list = OUTPUT_DIR / "speech_loop_concat.txt"

        head_frames = min(loop_frames, total_speech_frames)
        remaining_frames = total_speech_frames - head_frames

        if remaining_frames > 0:
            num_loops = remaining_frames // loop_frames
            tail_frames = remaining_frames % loop_frames
            if tail_frames < 60 and num_loops > 0:
                tail_frames += loop_frames
                num_loops -= 1
        else:
            num_loops = 0
            tail_frames = 0

        assert head_frames + (num_loops * loop_frames) + tail_frames == total_speech_frames

        scale_filter = f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps={FPS}"

        # 1. Head Segment (152 frames)
        if has_logo:
            head_filter = (
                f"[0:v]{scale_filter}[bg];"
                f"[bg]fade=t=in:st=0:d=1.0[bg_faded];"
                f"[1:v]fade=t=in:st=1.0:d=0.5:alpha=1[wm];"
                f"[2:v]scale={CHANNEL_LOGO_WIDTH}:-1,format=rgba,colorchannelmixer=aa={CHANNEL_LOGO_OPACITY}[logo];"
                f"[bg_faded][wm]overlay=0:0[bg_wm];"
                f"[bg_wm][logo]overlay={logo_overlay_pos}[outv]"
            )
            cmd_head = [
                "ffmpeg", "-y",
                "-i", str(speech_bg_path),
                "-loop", "1", "-i", str(watermark_path),
                "-loop", "1", "-i", str(channel_logo_path),
                "-filter_complex", head_filter,
                "-map", "[outv]",
                "-vframes", str(head_frames),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-video_track_timescale", "90000",
                str(temp_head)
            ]
        else:
            head_filter = (
                f"[0:v]{scale_filter}[bg];"
                f"[bg]fade=t=in:st=0:d=1.0[bg_faded];"
                f"[1:v]fade=t=in:st=1.0:d=0.5:alpha=1[wm];"
                f"[bg_faded][wm]overlay=0:0[outv]"
            )
            cmd_head = [
                "ffmpeg", "-y",
                "-i", str(speech_bg_path),
                "-loop", "1", "-i", str(watermark_path),
                "-filter_complex", head_filter,
                "-map", "[outv]",
                "-vframes", str(head_frames),
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                "-pix_fmt", "yuv420p", "-r", str(FPS),
                "-video_track_timescale", "90000",
                str(temp_head)
            ]
        subprocess.run(cmd_head, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 2. Body Unit (152 frames) - only if loops are needed
        if num_loops > 0:
            if has_logo:
                body_filter = (
                    f"[0:v]{scale_filter}[bg];"
                    f"[2:v]scale={CHANNEL_LOGO_WIDTH}:-1,format=rgba,colorchannelmixer=aa={CHANNEL_LOGO_OPACITY}[logo];"
                    f"[bg][1:v]overlay=0:0[bg_wm];"
                    f"[bg_wm][logo]overlay={logo_overlay_pos}[outv]"
                )
                cmd_body = [
                    "ffmpeg", "-y",
                    "-i", str(speech_bg_path),
                    "-loop", "1", "-i", str(watermark_path),
                    "-loop", "1", "-i", str(channel_logo_path),
                    "-filter_complex", body_filter,
                    "-map", "[outv]",
                    "-vframes", str(loop_frames),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-video_track_timescale", "90000",
                    str(temp_body)
                ]
            else:
                body_filter = (
                    f"[0:v]{scale_filter}[bg];"
                    f"[bg][1:v]overlay=0:0[outv]"
                )
                cmd_body = [
                    "ffmpeg", "-y",
                    "-i", str(speech_bg_path),
                    "-loop", "1", "-i", str(watermark_path),
                    "-filter_complex", body_filter,
                    "-map", "[outv]",
                    "-vframes", str(loop_frames),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-video_track_timescale", "90000",
                    str(temp_body)
                ]
            subprocess.run(cmd_body, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 3. Tail Segment (tail_frames) - with fade-out in final 30 frames (1.0s)
        if tail_frames > 0:
            tail_sec = tail_frames / float(FPS)
            tail_fade_st = max(0.0, tail_sec - 1.0)
            if has_logo:
                tail_filter = (
                    f"[0:v]{scale_filter}[bg];"
                    f"[bg][1:v]overlay=0:0[bg_wm];"
                    f"[bg_wm]fade=t=out:st={tail_fade_st:.3f}:d=1.0[bg_faded];"
                    f"[2:v]scale={CHANNEL_LOGO_WIDTH}:-1,format=rgba,colorchannelmixer=aa={CHANNEL_LOGO_OPACITY}[logo];"
                    f"[bg_faded][logo]overlay={logo_overlay_pos}[outv]"
                )
                cmd_tail = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", str(speech_bg_path),
                    "-loop", "1", "-i", str(watermark_path),
                    "-loop", "1", "-i", str(channel_logo_path),
                    "-filter_complex", tail_filter,
                    "-map", "[outv]",
                    "-vframes", str(tail_frames),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-video_track_timescale", "90000",
                    str(temp_tail)
                ]
            else:
                tail_filter = (
                    f"[0:v]{scale_filter}[bg];"
                    f"[bg][1:v]overlay=0:0[with_wm];"
                    f"[with_wm]fade=t=out:st={tail_fade_st:.3f}:d=1.0[outv]"
                )
                cmd_tail = [
                    "ffmpeg", "-y",
                    "-stream_loop", "-1", "-i", str(speech_bg_path),
                    "-loop", "1", "-i", str(watermark_path),
                    "-filter_complex", tail_filter,
                    "-map", "[outv]",
                    "-vframes", str(tail_frames),
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
                    "-pix_fmt", "yuv420p", "-r", str(FPS),
                    "-video_track_timescale", "90000",
                    str(temp_tail)
                ]
            subprocess.run(cmd_tail, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 4. Concat manifest
        with open(speech_concat_list, "w", encoding="utf-8") as f:
            f.write(f"file '{temp_head.name}'\n")
            for _ in range(num_loops):
                f.write(f"file '{temp_body.name}'\n")
            if tail_frames > 0:
                f.write(f"file '{temp_tail.name}'\n")

        # 5. Stream-copy video assembly
        cmd_assemble = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(speech_concat_list),
            "-c", "copy",
            "-video_track_timescale", "90000",
            str(temp_video_raw)
        ]
        subprocess.run(cmd_assemble, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # 6. Mux speech audio (sliced + padded) into output clip
        audio_filter = f"[0:a]apad=whole_dur={speech_scene_duration:.3f},atrim=0:{speech_scene_duration:.3f}[outa]"
        cmd_mux = [
            "ffmpeg", "-y",
            "-ss", f"{intro_duration:.3f}",
            "-t", f"{speech_audio_remaining:.3f}",
            "-i", str(speech_audio_path),
            "-i", str(temp_video_raw),
            "-filter_complex", audio_filter,
            "-map", "1:v:0",
            "-map", "[outa]",
            "-c:v", "copy",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            "-shortest",
            str(out_path)
        ]
        subprocess.run(cmd_mux, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Cleanup temps
        for tmp in [temp_head, temp_body, temp_tail, temp_video_raw, speech_concat_list]:
            if tmp.exists():
                tmp.unlink()

        print(f"[Scene 2/3] Finished: {out_path.name} ({total_speech_frames} frames via Loop Stream-Copy)")

    except Exception as e:
        print(f"[Scene 2/3] Loop Stream-Copy failed ({e}), falling back to direct render...")
        fade_out_start = max(0.0, speech_scene_duration - 1.0)
        filter_complex = (
            f"[0:v]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,setsar=1,fps={FPS}[bg];"
            f"[bg]fade=t=in:st=0:d=1.0[bg_faded];"
            f"[1:v]fade=t=in:st=1.0:d=0.5:alpha=1[wm];"
            f"[bg_faded][wm]overlay=0:0[with_wm];"
            f"[with_wm]fade=t=out:st={fade_out_start:.3f}:d=1.0,trim=0:{speech_scene_duration:.3f}[outv];"
            f"[2:a]apad=whole_dur={speech_scene_duration:.3f},atrim=0:{speech_scene_duration:.3f}[outa]"
        )
        cmd_fallback = [
            "ffmpeg", "-y",
            "-stream_loop", "-1",
            "-i", str(speech_bg_path),
            "-loop", "1",
            "-i", str(watermark_path),
            "-ss", f"{intro_duration:.3f}",
            "-t", f"{speech_audio_remaining:.3f}",
            "-i", str(speech_audio_path),
            "-filter_complex", filter_complex,
            "-map", "[outv]",
            "-map", "[outa]",
            "-t", f"{speech_scene_duration:.3f}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", "20",
            "-pix_fmt", "yuv420p",
            "-r", str(FPS),
            "-video_track_timescale", "90000",
            "-c:a", "aac",
            "-b:a", "192k",
            "-ar", "48000",
            "-ac", "2",
            str(out_path)
        ]
        subprocess.run(cmd_fallback, check=True)
        print(f"[Scene 2/3] Finished fallback render: {out_path.name}")


def ensure_clip_timescale(clip_path: Path, target_timescale: int = 90000) -> Path:
    """Ensures clip video track timescale matches target (default 90000). Remuxes losslessly if needed."""
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=time_base",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(clip_path)
    ]
    try:
        res = subprocess.run(probe_cmd, capture_output=True, text=True, check=True)
        tb_str = res.stdout.strip()
        if "/" in tb_str:
            timescale = int(tb_str.split("/")[1])
            if timescale != target_timescale:
                print(f"[Assembly] Remuxing {clip_path.name} timescale {timescale} -> {target_timescale} for seamless concat...")
                temp_remux = clip_path.with_name(f"{clip_path.stem}_90k.mp4")
                remux_cmd = [
                    "ffmpeg", "-y",
                    "-i", str(clip_path),
                    "-c", "copy",
                    "-video_track_timescale", str(target_timescale),
                    str(temp_remux)
                ]
                subprocess.run(remux_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                temp_remux.replace(clip_path)
    except Exception as e:
        print(f"[Assembly] Timescale check warning on {clip_path.name}: {e}")
    return clip_path


def render_master_audio(
    speech_audio_path: Path,
    extro_invite_path: Path,
    extro_verse_path: Path,
    out_path: Path,
    silence_dur: float = SILENCE_DURATION
):
    """Renders master continuous podcast audio for the entire program:
    [speech_audio] + [silence_dur] + [extro_invite] + [extro_verse]
    Formatted to 48000Hz stereo MP3 (192kbps).
    """
    filter_complex = (
        f"[0:a]aformat=sample_rates=48000:channel_layouts=stereo,apad=pad_dur={silence_dur:.3f}[a0_padded];"
        f"[1:a]volume={EXTRO_INVITE_VOLUME},aformat=sample_rates=48000:channel_layouts=stereo[a1_fmt];"
        f"[2:a]volume={EXTRO_VERSE_VOLUME},aformat=sample_rates=48000:channel_layouts=stereo[a2_fmt];"
        f"[a0_padded][a1_fmt][a2_fmt]concat=n=3:v=0:a=1[outa]"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", str(speech_audio_path),
        "-i", str(extro_invite_path),
        "-i", str(extro_verse_path),
        "-filter_complex", filter_complex,
        "-map", "[outa]",
        "-c:a", "libmp3lame",
        "-b:a", "192k",
        "-ar", "48000",
        str(out_path)
    ]
    print(f"[Master Audio] Rendering complete podcast audio -> {out_path.name}...")
    subprocess.run(cmd, check=True)

    print(f"[Master Audio] Done! Podcast audio ready at: {out_path}")


def concatenate_scenes(
    intro_path: Path,
    speech_path: Path,
    extro_path: Path,
    master_audio_path: Path,
    final_video_path: Path
):
    """Step 5: Concatenates Scene 1 + 2 + 3 video tracks and muxes with master audio."""
    ensure_clip_timescale(intro_path, 90000)
    ensure_clip_timescale(speech_path, 90000)
    ensure_clip_timescale(extro_path, 90000)

    concat_list_file = OUTPUT_DIR / "concat_list.txt"
    with open(concat_list_file, "w", encoding="utf-8") as f:
        f.write(f"file '{intro_path.name}'\n")
        f.write(f"file '{speech_path.name}'\n")
        f.write(f"file '{extro_path.name}'\n")


    temp_video_track = OUTPUT_DIR / "temp_video_track.mp4"
    cmd_video = [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_list_file),
        "-map", "0:v:0",
        "-c:v", "copy",
        "-video_track_timescale", "90000",
        str(temp_video_track)
    ]

    print(f"[Assembly] Concatenating video scenes into video track...")
    try:
        subprocess.run(cmd_video, check=True)
    except subprocess.CalledProcessError:
        print("[Assembly] Direct stream copy video concat failed. Falling back to filter concat...")
        filter_cmd = [
            "ffmpeg", "-y",
            "-i", str(intro_path),
            "-i", str(speech_path),
            "-i", str(extro_path),
            "-filter_complex",
            "[0:v][1:v][2:v]concat=n=3:v=1:a=0[outv]",
            "-map", "[outv]",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
            "-video_track_timescale", "90000",
            str(temp_video_track)
        ]
        subprocess.run(filter_cmd, check=True)

    print(f"[Assembly] Muxing master audio with assembled video into: {final_video_path.name}...")
    mux_cmd = [
        "ffmpeg", "-y",
        "-i", str(temp_video_track),
        "-i", str(master_audio_path),
        "-map", "0:v:0",
        "-map", "1:a:0",
        "-c:v", "copy",
        "-c:a", "aac",
        "-b:a", "192k",
        "-ar", "48000",
        "-shortest",
        str(final_video_path)
    ]
    subprocess.run(mux_cmd, check=True)

    if temp_video_track.exists():
        temp_video_track.unlink()


    print(f"[Assembly] Done! Final video ready at: {final_video_path}")


def extract_date_suffix(input_path: Path) -> str:
    """Extracts date suffix from input file stem, e.g. week_2026_09_02.json -> 2026_09_02."""
    import re
    stem = input_path.stem
    match = re.search(r'\d{4}[_-]\d{2}[_-]\d{2}', stem)
    if match:
        return match.group(0)
    if stem.startswith("week_"):
        return stem[len("week_"):]
    return stem


def strip_json_comments(text: str) -> str:
    """Strips single-line (//) and multi-line (/* */) comments and trailing commas from JSON."""
    import re
    def replacer(match):
        s = match.group(0)
        if s.startswith("/"):
            return ""
        return s
    pattern = re.compile(
        r"//.*?$|/\*.*?\*/|\x27(?:\\.|[^\\\x27])*\x27|\"(?:\\.|[^\\\"])*\"",
        re.DOTALL | re.MULTILINE
    )
    cleaned = re.sub(pattern, replacer, text)
    cleaned = re.sub(r",\s*([\]\}])", r"\1", cleaned)
    return cleaned


def load_input_json(path: Path) -> dict:
    """Loads input JSON file, automatically supporting comments (// and /* */)."""
    raw_text = path.read_text(encoding="utf-8")
    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        cleaned_text = strip_json_comments(raw_text)
        return json.loads(cleaned_text)


def resolve_input_file(path_str: str) -> Path:
    p = Path(path_str)
    if p.exists():
        return p
    rel = path_str
    if rel.startswith("/app/"):
        rel = rel[len("/app/"):]
    p_proj = PROJECT_ROOT / rel
    if p_proj.exists():
        return p_proj
    p_app = Path("/app") / rel
    if p_app.exists():
        return p_app

    # Auto-detection if default file path does not exist directly
    inputs_dirs = [Path("/app/inputs"), PROJECT_ROOT / "inputs"]
    for idir in inputs_dirs:
        if idir.exists():
            tafsir_files = sorted([
                f for f in idir.glob("tafsir_*.json")
                if not f.name.endswith(".example.json") and f.name != "tafsir_example.json"
            ])
            if len(tafsir_files) == 1:
                return tafsir_files[0]
            week_files = sorted([
                f for f in idir.glob("week_*.json")
                if not f.name.endswith(".example.json")
            ])
            if len(week_files) == 1:
                return week_files[0]

    raise FileNotFoundError(f"Input file not found: {path_str}")


def main():
    parser = argparse.ArgumentParser(description="BUET Mosque Tafseer Complete Video Renderer")
    parser.add_argument(
        "input_json",
        nargs="?",
        default="/app/inputs/tafsir_2026_09_02.json",
        help="Path to tafsir input JSON (default: inputs/tafsir_YYYY_MM_DD.json)"
    )
    parser.add_argument("--intro-only", action="store_true", help="Render only Scene 1 (Intro + Verses)")
    parser.add_argument("--watermark-only", action="store_true", help="Render only Watermark Still PNG")
    parser.add_argument("--extro-only", action="store_true", help="Render only Scene 3 (Extro)")
    parser.add_argument("--speech-only", action="store_true", help="Render only Scene 2 (Main Speech)")
    parser.add_argument("--audio-only", action="store_true", help="Render only Master Podcast Audio")
    parser.add_argument("--assemble-only", action="store_true", help="Only assemble final video and audio from existing clips")
    args = parser.parse_args()

    actual_input_path = resolve_input_file(args.input_json)
    inputs_dir = actual_input_path.parent
    tafsir_input = load_input_json(actual_input_path)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Detect & Validate Speech Audio
    speech_audio_path = find_speech_audio(inputs_dir)
    print(f"[Input Audio] Found unique speech audio clip: {speech_audio_path.name}")

    speech_duration = get_media_duration(speech_audio_path)
    print(f"[Input Audio] Total speech audio duration: {speech_duration:.2f}s ({speech_duration/60:.2f} min)")

    # 2. Build Props & Calculate Durations
    items = tafsir_input.get("segments") or tafsir_input.get("verses", [])
    needs_db = any(
        str(v.get("mode") or v.get("type") or "").strip().lower() in ("verse", "standard", "")
        and not (("arabic" in v or "arabic_text" in v) and ("bengali" in v or "bengali_translation" in v or "translation" in v))
        for v in items
    )
    db = None
    if needs_db:
        try:
            db = load_verse_db()
        except FileNotFoundError:
            print("[Warning] Quran database not found. If all verses use 'custom_text' mode, the database is not needed.")

    props = build_props(tafsir_input, db)
    intro_frames, intro_duration = calculate_intro_duration(props)

    if speech_duration < intro_duration:
        raise ValueError(
            f"Speech audio duration ({speech_duration:.2f}s) is shorter than intro scene ({intro_duration:.2f}s)."
        )

    speech_audio_remaining = speech_duration - intro_duration
    speech_scene_duration = speech_audio_remaining + SILENCE_DURATION

    # Extro duration
    extro_duration = 411 / float(FPS)  # 13.7s

    total_video_duration = intro_duration + speech_scene_duration + extro_duration

    print("=" * 60)
    print("BUET Mosque Tafseer Video Rendering Plan:")
    print(f"  • Scene 1 (Intro + Verses): {intro_duration:.2f}s ({intro_frames} frames)")
    print(f"  • Scene 2 (Main Speech):    {speech_scene_duration:.2f}s ({speech_scene_duration/60:.2f} min)")
    print(f"      - Speech audio:         {speech_audio_remaining:.2f}s")
    print(f"      - Trailing silence:     {SILENCE_DURATION:.2f}s")
    print(f"      - Watermark:            Top-left starting at t=1.0s")
    print(f"  • Scene 3 (Extro):          {extro_duration:.2f}s (411 frames)")
    print(f"  • Total Video Duration:     {total_video_duration:.2f}s ({total_video_duration/60:.2f} min)")
    print("=" * 60)

    date_suffix = extract_date_suffix(actual_input_path)

    intro_clip_path = OUTPUT_DIR / "intro_clip.mp4"
    watermark_png_path = OUTPUT_DIR / "speech_watermark.png"
    extro_clip_path = OUTPUT_DIR / "extro_clip.mp4"
    speech_clip_path = OUTPUT_DIR / "speech_clip.mp4"

    final_video_path = OUTPUT_DIR / f"final_video_{date_suffix}.mp4"
    final_audio_path = OUTPUT_DIR / f"final_audio_{date_suffix}.mp3"

    extro_invite_path = find_asset("extro_invite.mp3")
    extro_verse_path = find_asset("extro_verse.mp3")
    speech_bg_path = find_asset("speech_bg.mp4")
    channel_logo_path = find_asset("icb_logo.png")

    print(f"  • Output Video:             {final_video_path.name}")
    print(f"  • Output Podcast Audio:     {final_audio_path.name}")
    print("=" * 60)

    intro_data = props.get("intro") or {}
    surah_name = intro_data.get("surah_name", "সূরা আলে-ইমরান")
    verse_range = intro_data.get("verse_range", "")

    # Selective Execution
    if args.intro_only:
        render_intro_scene(props, speech_audio_path, intro_duration, intro_clip_path)
        return
    if args.watermark_only:
        render_watermark_still(surah_name, verse_range, watermark_png_path)
        return
    if args.extro_only:
        render_extro_scene(extro_clip_path)
        return
    if args.speech_only:
        if not watermark_png_path.exists():
            render_watermark_still(surah_name, verse_range, watermark_png_path)
        render_speech_scene(
            speech_bg_path, watermark_png_path, speech_audio_path,
            intro_duration, speech_audio_remaining, speech_scene_duration,
            speech_clip_path, channel_logo_path
        )
        return
    if args.audio_only:
        render_master_audio(speech_audio_path, extro_invite_path, extro_verse_path, final_audio_path)
        return
    if args.assemble_only:
        if not final_audio_path.exists():
            render_master_audio(speech_audio_path, extro_invite_path, extro_verse_path, final_audio_path)
        concatenate_scenes(intro_clip_path, speech_clip_path, extro_clip_path, final_audio_path, final_video_path)
        return

    # Full End-to-End Pipeline
    # 1. Scene 1: Intro + Verses
    render_intro_scene(props, speech_audio_path, intro_duration, intro_clip_path)

    # 2. Watermark Still PNG
    render_watermark_still(surah_name, verse_range, watermark_png_path)

    # 3. Scene 3: Extro
    render_extro_scene(extro_clip_path)

    # 4. Scene 2: Main Speech
    render_speech_scene(
        speech_bg_path, watermark_png_path, speech_audio_path,
        intro_duration, speech_audio_remaining, speech_scene_duration,
        speech_clip_path, channel_logo_path
    )

    # 5. Master Podcast Audio: speech + 1.5s silence + extro_invite + extro_verse
    render_master_audio(speech_audio_path, extro_invite_path, extro_verse_path, final_audio_path)

    # 6. Final Video + Audio Assembly
    concatenate_scenes(intro_clip_path, speech_clip_path, extro_clip_path, final_audio_path, final_video_path)


if __name__ == "__main__":
    main()
