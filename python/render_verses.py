import json
import subprocess
from pathlib import Path

FPS = 30
TRANSITION_FRAMES = 15  # must match VerseSequence.tsx's TRANSITION_FRAMES

DATA_PATH = Path("/app/data/quran_taisirul_bengali.json")
REMOTION_DIR = Path("/app/remotion")
BG_IMAGE = Path("/app/assets/verses_bg.png")
OUTPUT_DIR = Path("/app/output")


def load_verse_db(path=DATA_PATH):
    with open(path, encoding="utf-8") as f:
        entries = json.load(f)
    return {e["verse_key"]: e for e in entries}


def build_props(week_input, db):
    verses = []
    for v in week_input["verses"]:
        entry = db.get(v["verse_key"])
        if entry is None:
            raise KeyError(f"Verse key not found in database: {v['verse_key']}")
        duration_sec = v["end"] - v["start"]
        if duration_sec <= 0:
            raise ValueError(f"Non-positive duration for {v['verse_key']}: {duration_sec}")
        verses.append({
            "verseKey": v["verse_key"],
            "arabic": entry["arabic_text"],
            "bengali": entry["bengali_translation"],
            "durationInFrames": round(duration_sec * FPS),
        })
    return {"verses": verses}


def render_transparent_clip(props, out_path: Path):
    props_path = REMOTION_DIR / "tmp_props.json"
    props_path.write_text(json.dumps(props), encoding="utf-8")

    cmd = [
        "npx", "remotion", "render",
        "src/index.ts", "VerseSequence",
        str(out_path),
        f"--props={props_path}",
        "--browser-executable=/usr/bin/chromium",
        "--pixel-format=yuva444p10le",
    ]
    subprocess.run(cmd, cwd=REMOTION_DIR, check=True)


def composite_over_background(transparent_clip: Path, bg_image: Path, out_path: Path):
    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(bg_image),
        "-i", str(transparent_clip),
        "-filter_complex",
        "[0:v]scale=1920:1080[bg];[bg][1:v]overlay=shortest=1:format=auto[out]",
        "-map", "[out]",
        "-pix_fmt", "yuv420p",
        str(out_path),
    ]
    subprocess.run(cmd, check=True)


def main(week_input_path: str):
    week_input = json.loads(Path(week_input_path).read_text(encoding="utf-8"))
    db = load_verse_db()
    props = build_props(week_input, db)

    OUTPUT_DIR.mkdir(exist_ok=True)
    transparent_path = OUTPUT_DIR / "verses_transparent.mov"
    final_path = OUTPUT_DIR / "verses_clip.mp4"

    print(f"[1/2] Rendering {len(props['verses'])} verses with Remotion (transparent, filmBurn transitions)...")
    render_transparent_clip(props, transparent_path)

    print("[2/2] Compositing over verses_bg.png with ffmpeg...")
    composite_over_background(transparent_path, BG_IMAGE, final_path)

    print(f"Done: {final_path}")


if __name__ == "__main__":
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else "/app/inputs/week_2026_09_02.json")
