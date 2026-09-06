# BUET Mosque Tafseer Video Renderer

Automated end-to-end renderer for weekly **BUET Central Mosque Tafseer Halaqah** videos and podcast episodes.

This tool transforms a weekly Quran tafseer lecture audio file and metadata JSON into:
1. **Full Program Video** (`output/final_video_YYYY_MM_DD.mp4`): 1080p @ 30 fps complete video featuring animated title intro, synchronized Quran recitation slides (Arabic + Bengali translation), seamless looping desk background with watermark, and animated extro.
2. **Master Podcast Audio** (`output/final_audio_YYYY_MM_DD.mp3`): 48 kHz stereo 192 kbps audio track containing the full speech, trailing silence, and invitation outro—ready for Spotify, Apple Podcasts, and Google Podcasts.

---

## Architecture Highlights

* **Remotion + Chromium**: Renders smooth, spring-animated React components for the Intro, Quran verse scroll, and Extro cards.
* **FFmpeg Hardware-Accurate Looping**: Uses a modular stream-copy loop architecture that processes 30+ minutes of video in less than 5 minutes without redundant CPU encoding.
* **Separated Video & Audio Pipelines**: Generates both standalone podcast master MP3 and final composite MP4 in exact sample-accurate sync.
* **Clean Single Source of Truth**: Slide assets live in `remotion/src/` for Remotion's bundler and are referenced directly by the Python pipeline, eliminating duplicate media files.

---

## Project Structure

```text
.
├── assets/                          # Global video & typography assets
│   ├── fonts/                       # Custom font files (.ttf)
│   │   ├── arabic.ttf               # KFGQPC Uthmanic Script HAFS font
│   │   ├── bengali.ttf              # SolaimanLipi font
│   │   └── shokuntola.ttf           # Shokuntola font for title/watermark
│   └── speech_bg.mp4                # Looping 1080p desk/window speech background
├── data/
│   └── quran_taisirul_bengali.json  # Complete Quran Arabic & Bengali database
├── inputs/                          # Weekly variable inputs (Drop weekly files here!)
│   ├── tafsir_YYYY_MM_DD.example.json # Example template (tracked in git)
│   ├── tafsir_YYYY_MM_DD.json       # Weekly metadata & verse timestamps
│   └── *.mp3                        # Exactly ONE speech lecture audio file
├── output/                          # Generated video and audio files
│   ├── final_video_YYYY_MM_DD.mp4   # Master 1080p video
│   ├── final_audio_YYYY_MM_DD.mp3   # Master podcast audio
│   └── ...                          # Intermediate cached clips
├── python/
│   └── render_verses.py             # Master orchestrator script
├── remotion/                        # React Remotion compositions & slide assets
│   ├── src/
│   │   ├── intro_bg.png             # Twilight mosque backdrop for Intro card
│   │   ├── verses_bg.png            # Quran recitation backdrop
│   │   ├── extro_invite.mp3         # Outro invitation voice audio
│   │   ├── extro_verse.mp3          # Outro closing Quran recitation
│   │   ├── IntroSlide.tsx           # Intro title card animation
│   │   ├── VerseSlide.tsx           # Quran verse scroll & translations
│   │   ├── ExtroSlide.tsx           # Closing invitation card animations
│   │   └── SpeechWatermark.tsx      # Top-left transparent watermark
├── docker-compose.yml               # Docker Compose service definition
└── Dockerfile                       # Node 20 + Debian + Chromium + FFmpeg image
```

---

## Quickstart (Using Docker)

### 1. Prerequisites
Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) (macOS, Windows, or Linux). Ensure Docker is running.

### 2. Prepare Weekly Inputs
In the `inputs/` folder, place:
1. **Exactly one audio file** (`.mp3`, `.wav`, or `.m4a`) containing the lecture speech.
2. **One JSON file** named `tafsir_YYYY_MM_DD.json` (e.g., `inputs/tafsir_2026_09_02.json`). You can copy `inputs/tafsir_YYYY_MM_DD.example.json` to get started.

### 3. Build the Docker Image (First Time Only)
```bash
docker compose build
```

### 4. Render the Full Program
Run the complete pipeline inside the Docker container:
```bash
docker compose run --rm verse-renderer python3 python/render_verses.py /app/inputs/tafsir_2026_09_02.json
```
*(If no file path is specified, the script automatically detects the `tafsir_*.json` file in `inputs/`)*

### 5. Collect Output Files
Once finished, find your outputs in the `output/` folder:
* 🎬 `output/final_video_YYYY_MM_DD.mp4`
* 🎧 `output/final_audio_YYYY_MM_DD.mp3`

---

## Selective Execution Flags

You can run individual parts of the pipeline to preview or test changes rapidly:

| Flag | Purpose | Typical Run Time |
| :--- | :--- | :--- |
| *(default)* | Runs full end-to-end pipeline (Intro + Speech + Audio + Extro + Assembly) | ~1.5 minutes |
| `--assemble-only` | Assembles master video and audio from existing cached clips | ~15 seconds |
| `--audio-only` | Renders only the master podcast audio (`.mp3`) | ~10 seconds |
| `--speech-only` | Renders only Scene 2 (Main Speech video with watermark) | ~35 seconds |
| `--intro-only` | Renders only Scene 1 (Remotion Intro + Quran Verses) | ~40 seconds |
| `--extro-only` | Renders only Scene 3 (Remotion Extro invitation cards) | ~15 seconds |
| `--watermark-only`| Renders only the 1080p transparent watermark PNG | ~2 seconds |

**Example (re-assembling existing clips):**
```bash
docker compose run --rm verse-renderer python3 python/render_verses.py --assemble-only /app/inputs/tafsir_2026_09_02.json
```

**Example (generating podcast audio only):**
```bash
docker compose run --rm verse-renderer python3 python/render_verses.py --audio-only /app/inputs/tafsir_2026_09_02.json
```

---

## Input JSON Format

### CRITICAL: Audio Timestamp Synchronization

> **Important**: The `start` and `end` timestamps for each verse **MUST be taken directly from the main speech audio file (`inputs/*.mp3`)**, measured in seconds from the very beginning (`00:00.000`) of that audio file.
>
> **How to get timestamps:**
> 1. Open your speech audio file in an audio player or editor (such as Audacity, QuickTime, or VLC).
> 2. Note the exact timestamp where the speaker begins reciting the first verse (e.g., at `00:15.057` -> enter `15.057`).
> 3. Note when each verse ends and the next starts (e.g., `20.680`, `31.700`, `38.230`).
>
> **Why this matters:**
> The pipeline uses the `start` timestamp of the first verse to dynamically set the duration of the animated Intro Title Card. This guarantees that the transition from the Title Card into the Quran verse slide occurs at the exact millisecond the speaker recites that verse in the audio!

---

### Format 1: Standard Mode (`"mode": "standard"`)

Use standard mode when reciting complete Quranic verses that exist directly in the database (`data/quran_taisirul_bengali.json`). Arabic text and Bengali translations are automatically looked up using `verse_key` (e.g., `"3:47"`, `"18:1"`).

```json
{
  "mode": "standard",
  "intro": {
    "title": "তাফসীরুল কুরআন",
    "surah_name": "সূরা আলে-ইমরান",
    "verse_range": "৪৭-৪৮",
    "date": "২৬ আগস্ট ২০২৬",
    "speaker": "মুফতি রাশেদুর রহমান"
  },
  "verses": [
    {
      "verse_key": "3:47",
      "start": 15.057,
      "end": 31.700
    },
    {
      "verse_key": "3:48",
      "start": 31.700,
      "end": 38.230
    }
  ]
}
```

---

### Format 2: Custom Mode (`"mode": "custom"`)

Use custom mode when:
* **Splitting long verses**: When the speaker pauses midway through a long verse, you can break the verse into parts (e.g., `3:47 (১ম অংশ)` and `3:47 (২য় অংশ)`) so the viewer can follow along on screen in sync with the recitation.
* **Custom wording**: You wish to provide custom Arabic text or specific Bengali phrasing/transliteration.
* In custom mode, database lookup is completely bypassed; text is rendered exactly as specified in the JSON.

```json
{
  "mode": "custom",
  "intro": {
    "title": "তাফসীরুল কুরআন",
    "surah_name": "সূরা আলে-ইমরান",
    "verse_range": "৪৭-৪৮",
    "date": "২৬ আগস্ট ২০২৬",
    "speaker": "মুফতি রাশেদুর রহমান"
  },
  "verses": [
    {
      "verse_key": "3:47 (১ম অংশ)",
      "arabic": "قَالَتْ رَبِّ أَنَّىٰ يَكُونُ لِى وَلَدٌ وَلَمْ يَمْسَسْنِى بَشَرٌ",
      "bengali": "মারইয়াম বলল, ‘হে আমার প্রতিপালক! কীভাবে আমার পুত্র হবে, অথচ আমাকে কোন মানব স্পর্শ করেনি’।",
      "start": 15.057,
      "end": 20.680
    },
    {
      "verse_key": "3:47 (২য় অংশ)",
      "arabic": "قَالَ كَذَٰلِكِ ٱللَّهُ يَخْلُقُ مَا يَشَآءُ ۚ إِذَا قَضَىٰٓ أَمْرًا فَإِنَّمَا يَقُولُ لَهُۥ كُن فَيَكُونُ",
      "bengali": "তিনি বললেন, ‘এভাবেই’ আল্লাহ সৃজন করেন যা তিনি ইচ্ছে করেন, তিনি যখন কিছু স্থির করেন তখন বলেন, ‘‘হয়ে যাও’’ সুতরাং তা হয়ে যায়।",
      "start": 20.680,
      "end": 31.700
    },
    {
      "verse_key": "3:48",
      "arabic": "وَيُعَلِّمُهُ ٱلْكِتَـٰبَ وَٱلْحِكْمَةَ وَٱلتَّوْরَىٰةَ وَٱلْإِنجِيلَ",
      "bengali": "আর তিনি তাকে কিতাব, হিকমাত, তাওরাত ও ইঞ্জিল শিক্ষা দেবেন।",
      "start": 31.700,
      "end": 38.230
    }
  ]
}
```

---

## Asset Management & Architecture

* **Remotion Single Source of Truth**: Remotion components bundle slide-specific graphics and audio assets (`intro_bg.png`, `verses_bg.png`, `extro_invite.mp3`, `extro_verse.mp3`) directly from `remotion/src/`. The Python script accesses these via `find_asset()`, avoiding redundant asset duplicates.
* **Global Assets**: Common fonts (`assets/fonts/`) and the looping video background (`assets/speech_bg.mp4`) are kept under `assets/`.
* **Outro Audio Volume Control**: You can adjust the relative volume of outro audio clips at the top of `python/render_verses.py` and `remotion/src/ExtroScene.tsx`:
  - `EXTRO_INVITE_VOLUME = 1.0` (invitation voice clip)
  - `EXTRO_VERSE_VOLUME = 0.6` (closing recitation clip, set to 60% by default)

---

## Tips & Troubleshooting

* **Live Code Updates**: Code directories (`python/`, `remotion/src/`, `inputs/`, `output/`, `assets/`) are mounted as live Docker volumes. You **do not** need to rebuild the Docker image after editing Python or Remotion code.
* **Audio Constraint**: Ensure there is **strictly one** speech audio clip inside `inputs/`. If multiple audio files are found, the script will halt with an error to prevent using the wrong audio.
* **Disk Space**: Clean up old intermediate files in `output/` periodically if running low on disk space.
