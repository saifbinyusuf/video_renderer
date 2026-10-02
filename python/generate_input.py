#!/usr/bin/env python3
"""Automated Quran verse timestamp extraction and weekly tafsir input JSON generator.

Uses Groq API:
  - Phase 1: Whisper Large v3 (speech-to-text with word-level timestamps & pause detection)
  - Phase 2: Qwen 3.8 27B (verse alignment, pause-aware splitting, Bengali symmetry)
"""

import argparse
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path
import requests

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_PATH = PROJECT_ROOT / "data" / "quran_taisirul_bengali.json"
INPUTS_DIR = PROJECT_ROOT / "inputs"

# Bengali Digits & Months Mapping
BENGALI_DIGITS = str.maketrans("0123456789", "০১২৩৪৫৬৭৮৯")
BENGALI_MONTHS = {
    1: "জানুয়ারি", 2: "ফেব্রুয়ারি", 3: "মার্চ", 4: "এপ্রিল",
    5: "মে", 6: "জুন", 7: "জুলাই", 8: "আগস্ট",
    9: "সেপ্টেম্বর", 10: "অক্টোবর", 11: "নভেম্বর", 12: "ডিসেম্বর"
}

SURAH_NAMES_BN = {
    1: "সূরা আল-ফাতিহা", 2: "সূরা আল-বাকারা", 3: "সূরা আলে-ইমরান", 4: "সূরা আন-নিসা",
    5: "সূরা আল-মায়িদাহ", 6: "সূরা আল-আনআম", 7: "সূরা আল-আ'রাফ", 8: "সূরা আল-আনফাল",
    9: "সূরা আত-তাওবাহ", 10: "সূরা ইউনুস", 11: "সূরা হুদ", 12: "সূরা ইউসুফ",
    13: "সূরা আর-রাদ", 14: "সূরা ইবরাহীম", 15: "সূরা আল-হিজর", 16: "সূরা আন-নাহল",
    17: "সূরা বনী ইসরাঈল", 18: "সূরা আল-কাহফ", 19: "সূরা মারইয়াম", 20: "সূরা ত্বা-হা",
    21: "সূরা আল-আম্বিয়া", 22: "সূরা আল-হাজ্জ", 23: "সূরা আল-মু'মিনূন", 24: "সূরা আন-নূর",
    25: "সূরা আল-ফুরকান", 26: "সূরা আশ-শুআরা", 27: "সূরা আন-নামল", 28: "সূরা আল-কাসাস",
    29: "সূরা আল-আনকাবূত", 30: "সূরা আর-রূম", 31: "সূরা লুকমান", 32: "সূরা আস-সাজদাহ",
    33: "সূরা আল-আহযাব", 34: "সূরা সাবা", 35: "সূরা ফাতির", 36: "সূরা ইয়াসীন",
    37: "সূরা আস-সাফফাত", 38: "সূরা সোয়াদ", 39: "সূরা আয-যুমার", 40: "সূরা গাফির",
    41: "সূরা ফুসসিলাত", 42: "সূরা আশ-শূরা", 43: "সূরা আয-যুখরুফ", 44: "সূরা আদ-দুখান",
    45: "সূরা আল-জাসিয়াহ", 46: "সূরা আল-আহকাফ", 47: "সূরা মুহাম্মদ", 48: "সূরা আল-ফাতহ",
    49: "সূরা আল-হুজুরাত", 50: "সূরা ক্বাফ", 51: "সূরা আয-যারিয়াত", 52: "সূরা আত-তূর",
    53: "সূরা আন-নাজম", 54: "সূরা আল-ক্বামার", 55: "সূরা আর-রহমান", 56: "সূরা আল-ওয়াকিয়াহ",
    57: "সূরা আল-হাদীদ", 58: "সূরা আল-মুজাদালাহ", 59: "সূরা আল-হাশর", 60: "সূরা আল-মুমতাহিনাহ",
    61: "সূরা আস-সফ", 62: "সূরা আল-জুমুআহ", 63: "সূরা আল-মুনাফিকুন", 64: "সূরা আত-তাগাবুন",
    65: "সূরা আত-ত্বালাক", 66: "সূরা আত-তাহরীম", 67: "সূরা আল-মুলক", 68: "সূরা আল-কলম",
    69: "সূরা আল-হাক্কাহ", 70: "সূরা আল-মাআরিজ", 71: "সূরা নূহ", 72: "সূরা আল-জিন",
    73: "সূরা আল-মুযযাম্মিল", 74: "সূরা আল-মুদ্দাসসির", 75: "সূরা আল-কিয়ামাহ", 76: "সূরা আদ-দাহর",
    77: "সূরা আল-মুরসালাত", 78: "সূরা আন-নাবা", 79: "সূরা আন-নাযিআত", 80: "সূরা আবাসা",
    81: "সূরা আত-তাকভীর", 82: "সূরা আল-ইনফিতার", 83: "সূরা আল-মুতাফফিফীন", 84: "সূরা আল-ইনশিকাক",
    85: "সূরা আল-বুরুজ", 86: "সূরা আত-তারিক", 87: "সূরা আল-আ'লা", 88: "সূরা আল-গাশিয়াহ",
    89: "সূরা আল-ফজর", 90: "সূরা আল-বালাদ", 91: "সূরা আশ-শামস", 92: "সূরা আল-লায়ল",
    93: "সূরা আদ-দুহা", 94: "সূরা আল-ইনশিরাহ", 95: "সূরা আত-তীন", 96: "সূরা আল-আলাক",
    97: "সূরা আল-ক্বদর", 98: "সূরা আল-বাইয়িনাহ", 99: "সূরা আল-যিলযাল", 100: "সূরা আল-আদিয়াত",
    101: "সূরা আল-কারিয়াহ", 102: "সূরা আত-তাকাসুর", 103: "সূরা আল-আসর", 104: "সূরা আল-হুমাযাহ",
    105: "সূরা আল-ফীল", 106: "সূরা কুরাইশ", 107: "সূরা আল-মাউন", 108: "সূরা আল-কাওসার",
    109: "সূরা আল-কাফিরুন", 110: "সূরা আন-নাসর", 111: "সূরা আল-লাহাব", 112: "সূরা আল-ইখলাস",
    113: "সূরা আল-ফালাক", 114: "সূরা আন-নাস"
}


def load_groq_api_key() -> str:
    """Retrieves GROQ_API_KEY from environment or .env file."""
    api_key = os.environ.get("GROQ_API_KEY")
    if api_key:
        return api_key.strip()

    env_paths = [PROJECT_ROOT / ".env", Path(".env")]
    for p in env_paths:
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith("GROQ_API_KEY") and "=" in line:
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key

    raise ValueError(
        "GROQ_API_KEY not found! Please set it in your .env file or as an environment variable."
    )


def parse_timestamp(val: str | float) -> float:
    """Parses timestamp in seconds or MM:SS format."""
    if isinstance(val, (int, float)):
        return float(val)
    val = str(val).strip()
    if ":" in val:
        parts = val.split(":")
        if len(parts) == 2:
            return float(parts[0]) * 60 + float(parts[1])
        elif len(parts) == 3:
            return float(parts[0]) * 3600 + float(parts[1]) * 60 + float(parts[2])
    return float(val)


def to_bengali_number(n: int | str) -> str:
    return str(n).translate(BENGALI_DIGITS)


def find_speech_audio(inputs_dir: Path) -> Path:
    """Finds the speech audio file in inputs directory."""
    audio_extensions = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
    files = [
        f for f in inputs_dir.iterdir()
        if f.is_file() and f.suffix.lower() in audio_extensions and not f.name.startswith(".")
    ]
    if not files:
        raise FileNotFoundError(f"No audio file found in {inputs_dir}")
    if len(files) > 1:
        # If multiple, pick the one matching Tafsir pattern or the first one
        tafsir_files = [f for f in files if "tafsir" in f.name.lower()]
        return tafsir_files[0] if tafsir_files else files[0]
    return files[0]


def extract_date_from_filename(filename: str) -> tuple[str, str]:
    """Extracts YYYY-MM-DD from filename and formats it in Bengali."""
    m = re.search(r"(\d{4})[-_](\d{2})[-_](\d{2})", filename)
    if not m:
        return "YYYY_MM_DD", "তারিখ অনির্ধারিত"
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    iso_date = f"{year:04d}_{month:02d}_{day:02d}"
    bn_day = to_bengali_number(day)
    bn_month = BENGALI_MONTHS.get(month, "")
    bn_year = to_bengali_number(year)
    bn_date = f"{bn_day} {bn_month} {bn_year}"
    return iso_date, bn_date


def load_target_verses(surah_num: int, start_v: int, end_v: int) -> list[dict]:
    """Loads target verses from the Quran database."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Quran database not found at {DATA_PATH}")
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    db = {e["verse_key"]: e for e in data}

    verses = []
    for v in range(start_v, end_v + 1):
        key = f"{surah_num}:{v}"
        entry = db.get(key)
        if not entry:
            raise KeyError(f"Verse {key} not found in database {DATA_PATH}")
        verses.append(entry)
    return verses


def slice_audio(audio_path: Path, start_sec: float, end_sec: float, out_path: Path) -> Path:
    """Slices the audio segment using ffmpeg."""
    duration = end_sec - start_sec
    if duration <= 0:
        raise ValueError(f"Invalid slice duration: start={start_sec}s, end={end_sec}s")

    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_sec),
        "-t", str(duration),
        "-i", str(audio_path),
        "-ar", "16000",
        "-ac", "1",
        "-c:a", "pcm_s16le",
        str(out_path)
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    return out_path


def run_groq_whisper(slice_wav_path: Path, api_key: str, slice_start_sec: float) -> list[dict]:
    """Transcribes sliced audio via Groq Whisper with word-level timestamps."""
    url = "https://api.groq.com/openai/v1/audio/transcriptions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    }

    print("[Phase 1/2] Calling Groq Whisper Large v3 for word-level transcription...")
    with open(slice_wav_path, "rb") as f:
        files = {
            "file": ("audio.wav", f, "audio/wav"),
            "model": (None, "whisper-large-v3"),
            "language": (None, "ar"),
            "response_format": (None, "verbose_json"),
            "timestamp_granularities[]": (None, "word"),
        }
        res = requests.post(url, headers=headers, files=files, timeout=60)

    if res.status_code != 200:
        raise RuntimeError(f"Groq Whisper API failed ({res.status_code}): {res.text}")

    data = res.json()
    raw_words = data.get("words", [])
    if not raw_words:
        raise ValueError("Groq Whisper returned no words. Check the audio slice range.")

    # Offset timestamps by slice_start_sec to align with full audio
    words = []
    for w in raw_words:
        words.append({
            "word": w["word"].strip(),
            "start": round(slice_start_sec + float(w["start"]), 2),
            "end": round(slice_start_sec + float(w["end"]), 2),
        })

    return words


def build_annotated_word_stream(words: list[dict]) -> tuple[list[dict | str], float]:
    """Annotates acoustic pauses and repeated transition words."""
    annotated = []
    for i, w in enumerate(words):
        annotated.append({"w": w["word"], "s": w["start"], "e": w["end"]})
        if i < len(words) - 1:
            next_w = words[i + 1]
            gap = round(next_w["start"] - w["end"], 2)
            if gap >= 0.35:
                annotated.append(f"[PAUSE: {gap}s]")
            if next_w["word"] == w["word"]:
                annotated.append(f"[REPETITION: '{w['word']}']")

    final_word_end = words[-1]["end"]
    return annotated, final_word_end


def run_groq_alignment(
    api_key: str,
    annotated_words: list[dict | str],
    target_verses: list[dict],
    max_words_per_segment: int = 15,
) -> list[dict]:
    """Phase 2: Uses Qwen 3.8 27B to align verses and symmetrically split long verses."""
    # Programmatic pre-analysis of verses
    analyzed_verses = []
    for v in target_verses:
        words = v["arabic_text"].split()
        count = len(words)
        needs_split = count > max_words_per_segment
        info = {
            "verse_key": v["verse_key"],
            "word_count": count,
            "needs_split": needs_split,
            "arabic_text": v["arabic_text"],
            "bengali_translation": v["bengali_translation"],
        }
        if needs_split:
            info["min_segments"] = math.ceil(count / max_words_per_segment)
            info["instruction"] = (
                f"Contains {count} words (> {max_words_per_segment} max). "
                f"MUST be split into at least {info['min_segments']} segments."
            )
        analyzed_verses.append(info)

    prompt = f"""You are an expert Quran audio synchronization assistant for an automated video generator.

### AUDIO TRANSCRIPTION WITH WORD TIMESTAMPS & ACOUSTIC PAUSES:
{json.dumps(annotated_words, ensure_ascii=False)}

### TARGET QURAN VERSES (FROM DATABASE):
{json.dumps(analyzed_verses, ensure_ascii=False, indent=2)}

### SEGMENTATION PRIORITIES & RULES:
1. MAX WORDS CONSTRAINT:
   - No segment may contain more than {max_words_per_segment} Arabic words.
   - Do NOT split artificially (e.g. 20 words into 15 + 5). Balance the segments naturally at pause points.

2. CANONICAL TEXT INTEGRITY (CRITICAL):
   - The "arabic" and "bengali" text in the output MUST be clean, exact sequential partition of the canonical verse text from the database.
   - Do NOT duplicate words in the Arabic text (e.g., if the speaker repeated a transition word like "تعالوا" after taking a breath, the on-screen text for the next segment starts from the next unique word: "ندع ابناءنا...").

3. PRIORITY 1 — SPEAKER ACOUSTIC PAUSES & REPETITIONS:
   - When a verse needs splitting (`needs_split: true`), locate the acoustic pauses (`[PAUSE: ...s]`) within that verse.
   - Split at these speaker breath pause boundaries (e.g., in 3:61, after "تعالوا" and after "وانفسكم").

4. PRIORITY 2 — MEANINGFUL SEMANTIC SPLIT:
   - Each segment must form a complete grammatical clause in Arabic.
   - Symmetrically split the Bengali translation at the exact corresponding clause boundary so the Bengali text matches that segment's Arabic meaning.

5. UNSPLIT VERSES (needs_split: false) — STRICT:
   - If a verse is marked `needs_split: false`, you MUST NOT split it. Keep it as a SINGLE unsplit entry:
     {{"mode": "verse", "verse_key": "<key>", "start": <float>}}
   - ONLY verses marked `needs_split: true` are permitted to be split. Never split a verse with `needs_split: false`.

6. OUTPUT SCHEMA:
   - Output ONLY the "start" timestamp for each segment (do NOT output "end").
   - For unsplit verses:
     {{"mode": "verse", "verse_key": "3:60", "start": 16.72}}
   - For split verses:
     {{"mode": "custom_text", "verse_key": "3:61 (১ম অংশ)", "arabic": "...", "bengali": "...", "start": 22.08}},
     {{"mode": "custom_text", "verse_key": "3:61 (২য় অংশ)", "arabic": "...", "bengali": "...", "start": 30.46}},
     ...

Return valid JSON with top-level key "verses".
"""

    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko)"
    }
    payload = {
        "model": "qwen/qwen3.8-27b",
        "messages": [
            {"role": "system", "content": "You are a precise JSON generator. Output valid JSON only."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1,
    }

    print("[Phase 2/2] Calling Groq Qwen 3.8 27B for semantic verse alignment & splitting...")
    max_retries = 3
    for attempt in range(max_retries):
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        if res.status_code == 200:
            break
        elif res.status_code == 429:
            # Check if rate limited
            wait_time = 6.0
            try:
                err_data = res.json().get("error", {})
                msg = err_data.get("message", "")
                m = re.search(r"try again in (\d+\.?\d*)s", msg)
                if m:
                    wait_time = float(m.group(1)) + 1.0
            except Exception:
                pass
            print(f"[Rate limit hit] Waiting {wait_time:.1f}s before retry ({attempt + 1}/{max_retries})...")
            import time
            time.sleep(wait_time)
        else:
            raise RuntimeError(f"Groq Qwen API failed ({res.status_code}): {res.text}")
    else:
        raise RuntimeError(f"Groq Qwen API failed after {max_retries} retries ({res.status_code}): {res.text}")

    resp_json = res.json()
    content = resp_json["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    raw_verses = parsed.get("verses", [])
    if not raw_verses:
        raise ValueError(f"Model returned no 'verses' array: {content}")

    return raw_verses


def post_process_timestamps(
    raw_verses: list[dict], final_word_end: float, user_end_sec: float | None = None
) -> list[dict]:
    """Chains timestamps: end[i] = start[i+1], and sets final verse end."""
    verses = []
    for item in raw_verses:
        clean_item = dict(item)
        if "start" in clean_item:
            clean_item["start"] = round(float(clean_item["start"]), 2)
        # Remove any model-generated end to maintain single source of truth
        clean_item.pop("end", None)
        verses.append(clean_item)

    # Chain starts to previous ends
    for i in range(len(verses) - 1):
        verses[i]["end"] = verses[i + 1]["start"]

    # Final verse end timestamp:
    # Use Whisper's last word end time (or user_end_sec if closer to audio cutoff)
    if user_end_sec and abs(user_end_sec - final_word_end) < 1.0:
        final_end = round(user_end_sec, 2)
    else:
        final_end = round(final_word_end, 2)

    verses[-1]["end"] = final_end
    return verses


def validate_verses(verses: list[dict], max_words: int = 15):
    """Validates segment constraints and durations."""
    for i, v in enumerate(verses):
        s = v.get("start", 0)
        e = v.get("end", 0)
        if e <= s:
            raise ValueError(f"Segment #{i+1} ({v.get('verse_key')}) has invalid duration: start={s}, end={e}")

        if v.get("mode") == "custom_text":
            arabic = v.get("arabic", "")
            words = arabic.split()
            if len(words) > max_words + 3:  # Allow small grace for conjunctives
                print(f"[Warning] Segment {v.get('verse_key')} has {len(words)} words (recommended <= {max_words}).")


def main():
    parser = argparse.ArgumentParser(
        description="Automated Quran verse timestamp extraction using Groq Whisper + Qwen."
    )
    parser.add_argument("--surah", type=int, required=True, help="Surah number (e.g. 3)")
    parser.add_argument(
        "--verses", type=str, required=True,
        help="Verse range (e.g. '60-63' or '60')"
    )
    parser.add_argument(
        "--start", type=str, required=True,
        help="Start timestamp for slicing the recitation audio (e.g. 16.11 or '00:16.11')"
    )
    parser.add_argument(
        "--end", type=str, required=True,
        help="End timestamp for slicing the recitation audio (e.g. 68.0 or '01:08.0')"
    )
    parser.add_argument("--audio", type=str, default=None, help="Path to input audio file")
    parser.add_argument("--output", type=str, default=None, help="Path to save output JSON")
    parser.add_argument("--speaker", type=str, default="মুফতি রাশেদুর রহমান", help="Speaker name")
    parser.add_argument("--title", type=str, default="তাফসীরুল কুরআন", help="Halaqah title")
    parser.add_argument("--surah-name", type=str, default=None, help="Custom Bengali Surah name override")
    parser.add_argument("--date", type=str, default=None, help="Custom Bengali date override")
    parser.add_argument("--max-words", type=int, default=15, help="Max words per segment (default: 15)")

    args = parser.parse_args()

    api_key = load_groq_api_key()

    # Parse verse range
    v_parts = args.verses.split("-")
    start_v = int(v_parts[0])
    end_v = int(v_parts[1]) if len(v_parts) > 1 else start_v

    # Parse start and end timestamps
    start_sec = parse_timestamp(args.start)
    end_sec = parse_timestamp(args.end)

    # Locate audio file
    if args.audio:
        audio_path = Path(args.audio)
    else:
        audio_path = find_speech_audio(INPUTS_DIR)

    iso_date, auto_bn_date = extract_date_from_filename(audio_path.name)
    bn_date = args.date or auto_bn_date

    # Surah name in Bengali
    bn_surah_name = args.surah_name or SURAH_NAMES_BN.get(args.surah, f"সূরা {args.surah}")

    # Verse range in Bengali
    if start_v == end_v:
        bn_verse_range = to_bengali_number(start_v)
    else:
        bn_verse_range = f"{to_bengali_number(start_v)}-{to_bengali_number(end_v)}"

    # Output file path
    if args.output:
        out_json_path = Path(args.output)
    else:
        out_json_path = INPUTS_DIR / f"tafsir_{iso_date}.json"

    print(f"==================================================")
    print(f" Audio File    : {audio_path.name}")
    print(f" Surah & Verses: Surah {args.surah} ({bn_surah_name}), Verses {args.verses} ({bn_verse_range})")
    print(f" Audio Slice   : {start_sec:.2f}s -> {end_sec:.2f}s ({end_sec - start_sec:.2f}s)")
    print(f" Output JSON   : {out_json_path}")
    print(f"==================================================")

    # Load target verses from DB
    target_verses = load_target_verses(args.surah, start_v, end_v)

    # Create temporary slice in scratch dir
    scratch_dir = PROJECT_ROOT / "output" / "scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    slice_wav = scratch_dir / f"slice_{args.surah}_{start_v}_{end_v}.wav"

    try:
        slice_audio(audio_path, start_sec, end_sec, slice_wav)

        # Phase 1: Whisper STT
        words = run_groq_whisper(slice_wav, api_key, start_sec)
        annotated_words, final_word_end = build_annotated_word_stream(words)
        print(f"[Phase 1/2] Whisper recognized {len(words)} words (Audio end: {final_word_end:.2f}s)")

        # Phase 2: Qwen Alignment & Splitting
        raw_verses = run_groq_alignment(
            api_key=api_key,
            annotated_words=annotated_words,
            target_verses=target_verses,
            max_words_per_segment=args.max_words,
        )

        # Step 5: Post-processing (Chain start -> previous end)
        final_verses = post_process_timestamps(raw_verses, final_word_end, end_sec)
        validate_verses(final_verses, args.max_words)

        # Assemble full JSON
        full_config = {
            "intro": {
                "title": args.title,
                "surah_name": bn_surah_name,
                "verse_range": bn_verse_range,
                "date": bn_date,
                "speaker": args.speaker,
            },
            "verses": final_verses,
        }

        # Save to output file
        out_json_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump(full_config, f, ensure_ascii=False, indent=2)

        print(f"\n[Success] Generated {len(final_verses)} segments:")
        for idx, v in enumerate(final_verses):
            v_key = v.get("verse_key", f"item_{idx+1}")
            s = v.get("start")
            e = v.get("end")
            dur = e - s
            mode = v.get("mode", "verse")
            print(f"  {idx+1}. {v_key:<16} | {s:5.2f}s -> {e:5.2f}s ({dur:4.2f}s) | mode: {mode}")

        print(f"\nConfiguration saved to: {out_json_path}")

    finally:
        if slice_wav.exists():
            slice_wav.unlink()


if __name__ == "__main__":
    main()
