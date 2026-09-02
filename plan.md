## Project layout

```
project/
├── Dockerfile
├── docker-compose.yml
├── data/
│   └── quran_taisirul_bengali.json
├── assets/
│   ├── verses_bg.png
│   └── fonts/
│       ├── arabic.ttf
│       └── bengali.ttf
├── remotion/
│   ├── package.json
│   ├── remotion.config.ts
│   ├── public/
│   │   └── fonts/          # symlink/copy of assets/fonts at build time
│   └── src/
│       ├── index.ts
│       ├── Root.tsx
│       ├── VerseSequence.tsx
│       ├── VerseSlide.tsx
│       └── FilmBurnTransition.tsx
├── inputs/
│   └── week_2026_09_02.json
├── python/
│   └── render_verses.py
└── output/
```

I'm splitting the pipeline as: **Remotion renders text-only, transparent, with the filmBurn transitions** → **ffmpeg composites that over `verses_bg.png` afterward**. This keeps Remotion simple (it never touches your background image) and keeps compositing/timing logic in Python where it's easier to debug.

---

## 1. Remotion project

### `remotion/package.json`
```json
{
  "name": "verse-renderer",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "render": "remotion render"
  },
  "dependencies": {
    "@remotion/cli": "4.0.190",
    "@remotion/fonts": "4.0.190",
    "@remotion/transitions": "4.0.190",
    "react": "18.3.1",
    "react-dom": "18.3.1",
    "remotion": "4.0.190"
  }
}
```
*(Pin versions like this — Remotion ships breaking API changes between majors, and the `@remotion/transitions` custom-presentation API below matches 4.0.x.)*

### `remotion/src/index.ts`
```ts
import { registerRoot } from "remotion";
import { RemotionRoot } from "./Root";

registerRoot(RemotionRoot);
```

### `remotion/src/FilmBurnTransition.tsx`
A "film burn" isn't a Remotion built-in (built-ins are fade/wipe/slide/flip/clockWipe/iris), so this implements it as a custom presentation: a warm radial flash peaking mid-transition, plus the outgoing/incoming slide fading through it.

```tsx
import React from "react";
import { interpolate } from "remotion";
import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";

type FilmBurnProps = {
  intensity?: number;
};

const FilmBurnPresentation: React.FC
  TransitionPresentationComponentProps<FilmBurnProps>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const intensity = passedProps.intensity ?? 1;

  // Flash peaks in the middle of the transition, fades at both ends
  const flash =
    interpolate(presentationProgress, [0, 0.5, 1], [0, 1, 0]) * intensity;

  const opacity =
    presentationDirection === "entering"
      ? interpolate(presentationProgress, [0, 0.4, 1], [0, 0.2, 1])
      : interpolate(presentationProgress, [0, 0.6, 1], [1, 0.8, 0]);

  return (
    <div style={{ position: "absolute", width: "100%", height: "100%", opacity }}>
      {children}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 50% 50%, rgba(255,205,120,0.95) 0%, rgba(255,120,0,0.65) 40%, rgba(0,0,0,0) 72%)",
          mixBlendMode: "screen",
          opacity: flash,
        }}
      />
    </div>
  );
};

export const filmBurn = (
  props: FilmBurnProps = {}
): TransitionPresentation<FilmBurnProps> => ({
  component: FilmBurnPresentation,
  props,
});
```

### `remotion/src/VerseSlide.tsx`
Loads your two custom `.ttf` files, renders Arabic above / Bengali below, centered, yellow, with glow + shadow.

```tsx
import React, { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";

let fontsLoaded = false;

export const VerseSlide: React.FC<{ arabic: string; bengali: string }> = ({
  arabic,
  bengali,
}) => {
  const [handle] = useState(() =>
    fontsLoaded ? null : delayRender("Loading verse fonts")
  );

  useEffect(() => {
    if (fontsLoaded) return;
    Promise.all([
      loadFont({
        family: "ArabicFont",
        url: staticFile("fonts/arabic.ttf"),
        weight: "700",
      }),
      loadFont({
        family: "BengaliFont",
        url: staticFile("fonts/bengali.ttf"),
        weight: "700",
      }),
    ]).then(() => {
      fontsLoaded = true;
      if (handle !== null) continueRender(handle);
    });
  }, [handle]);

  return (
    <AbsoluteFill
      style={{
        backgroundColor: "transparent",
        justifyContent: "center",
        alignItems: "center",
      }}
    >
      <div style={{ textAlign: "center", maxWidth: "85%" }}>
        <div
          style={{
            fontFamily: "ArabicFont",
            fontSize: 88,
            color: "#FFD700",
            direction: "rtl",
            lineHeight: 1.6,
            textShadow:
              "0 0 12px rgba(255,215,0,0.85), 0 0 30px rgba(255,180,0,0.5), 2px 2px 6px rgba(0,0,0,0.75)",
          }}
        >
          {arabic}
        </div>
        <div
          style={{
            fontFamily: "BengaliFont",
            fontSize: 44,
            color: "#FFD700",
            marginTop: 36,
            lineHeight: 1.5,
            textShadow: "2px 2px 6px rgba(0,0,0,0.75)",
          }}
        >
          {bengali}
        </div>
      </div>
    </AbsoluteFill>
  );
};
```

### `remotion/src/VerseSequence.tsx`
```tsx
import React, { Fragment } from "react";
import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { filmBurn } from "./FilmBurnTransition";
import { VerseSlide } from "./VerseSlide";

export const TRANSITION_FRAMES = 15;

export type VerseInput = {
  verseKey: string;
  arabic: string;
  bengali: string;
  durationInFrames: number;
};

export const VerseSequence: React.FC<{ verses: VerseInput[] }> = ({ verses }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <TransitionSeries>
        {verses.map((v, i) => (
          <Fragment key={v.verseKey}>
            <TransitionSeries.Sequence durationInFrames={v.durationInFrames}>
              <VerseSlide arabic={v.arabic} bengali={v.bengali} />
            </TransitionSeries.Sequence>
            {i < verses.length - 1 && (
              <TransitionSeries.Transition
                presentation={filmBurn({ intensity: 1 })}
                timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
              />
            )}
          </Fragment>
        ))}
      </TransitionSeries>
    </AbsoluteFill>
  );
};
```
Note: `TransitionSeries` **overlaps** adjacent sequences by the transition duration — total composition length is `sum(durations) - (n-1) * TRANSITION_FRAMES`, not the plain sum. The Root's `calculateMetadata` below handles this automatically so you never compute it by hand in Python.

### `remotion/src/Root.tsx`
```tsx
import React from "react";
import { Composition } from "remotion";
import { VerseSequence, VerseInput, TRANSITION_FRAMES } from "./VerseSequence";

const FPS = 30;
const WIDTH = 1920;
const HEIGHT = 1080;

export const RemotionRoot: React.FC = () => {
  return (
    <Composition
      id="VerseSequence"
      component={VerseSequence}
      fps={FPS}
      width={WIDTH}
      height={HEIGHT}
      defaultProps={{ verses: [] as VerseInput[] }}
      calculateMetadata={({ props }) => {
        const verses = props.verses as VerseInput[];
        const totalContent = verses.reduce((sum, v) => sum + v.durationInFrames, 0);
        const totalTransitionOverlap = Math.max(verses.length - 1, 0) * TRANSITION_FRAMES;
        const durationInFrames = Math.max(totalContent - totalTransitionOverlap, FPS);
        return { durationInFrames };
      }}
    />
  );
};
```

### `remotion/remotion.config.ts`
```ts
import { Config } from "@remotion/cli/config";

Config.setVideoImageFormat("png");   // per-frame quality for the alpha channel
Config.setCodec("prores");
Config.setProResProfile("4444");     // ProRes 4444 = real alpha channel, high quality
```

---

## 2. Dockerfile

```dockerfile
FROM node:20-bookworm

# Headless Chromium deps (for Remotion) + ffmpeg + python for the driver script
RUN apt-get update && apt-get install -y \
    ffmpeg python3 python3-pip \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libxkbcommon0 \
    libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libasound2 \
    libpango-1.0-0 libcairo2 libatspi2.0-0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY remotion/package.json ./remotion/package.json
RUN cd remotion && npm install

COPY remotion ./remotion
COPY assets ./assets
COPY data ./data
COPY python ./python

# Fonts must live under remotion/public/ for staticFile() to find them
RUN mkdir -p remotion/public/fonts && cp assets/fonts/*.ttf remotion/public/fonts/

RUN pip3 install --break-system-packages ffmpeg-python

# Pre-download Remotion's bundled headless browser so first render isn't slow
RUN cd remotion && npx remotion browser ensure

CMD ["bash"]
```

### `docker-compose.yml`
```yaml
services:
  verse-renderer:
    build: .
    volumes:
      - ./inputs:/app/inputs
      - ./output:/app/output
      - ./data:/app/data
      - ./assets:/app/assets
    tty: true
```

Build it:
```bash
docker compose build
docker compose run --rm verse-renderer bash
```

---

## 3. Python driver

### `inputs/week_2026_09_02.json`
```json
{
  "verses": [
    { "verse_key": "2:45", "start": 5.14, "end": 9.68 },
    { "verse_key": "2:46", "start": 9.68, "end": 13.23 }
  ]
}
```

### `python/render_verses.py`
```python
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
```