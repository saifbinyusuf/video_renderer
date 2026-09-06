import React from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  useCurrentFrame,
  useVideoConfig,
  interpolate,
  Easing,
} from "remotion";
import { VerseSlide } from "./VerseSlide";
import { IntroSlide, IntroData } from "./IntroSlide";
import introBg from "./intro_bg.png";
import scrollBg from "./verses_bg.png";

export const FPS = 30;
export const FADE_FRAMES = 30; // Verse text fade

export type VerseInput = {
  verseKey?: string;
  arabic: string;
  bengali: string;
  durationInFrames: number;
};

export type VerseSequenceProps = {
  intro?: IntroData;
  firstVerseStartSec?: number;
  verses: VerseInput[];
};

const FadeInOutSlide: React.FC<{
  durationInFrames: number;
  arabic: string;
  bengali: string;
}> = ({ durationInFrames, arabic, bengali }) => {
  const frame = useCurrentFrame();
  const fade = Math.min(FADE_FRAMES, Math.floor(durationInFrames / 3));

  const opacity = interpolate(
    frame,
    [0, fade, Math.max(fade, durationInFrames - fade), durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <VerseSlide arabic={arabic} bengali={bengali} />
    </AbsoluteFill>
  );
};

export const VerseSequence: React.FC<VerseSequenceProps> = ({
  intro,
  firstVerseStartSec = 15.057,
  verses = [],
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  // -------------------------------------------------------------
  // 1. TIMELINE CALCULATIONS
  // -------------------------------------------------------------
  const firstVerseFrame = Math.max(
    Math.round(firstVerseStartSec * FPS),
    150 // Floor (5s) for intro choreography
  );

  // Opening Phase:
  // - 0s to 2.0s (0 to 60 frames): Clean mosque background image only
  // - 2.0s to 3.25s (60 to 98 frames): Dark overlay fades in AND text splits OUTWARD (1.25s / 38 frames)
  const INTRO_DELAY_FRAMES = 60; // 2.0 seconds clean opening
  const INTRO_SPLIT_OUT_FRAMES = 38; // 1.25 seconds split out
  const introAppearStart = INTRO_DELAY_FRAMES;
  const introAppearEnd = introAppearStart + INTRO_SPLIT_OUT_FRAMES;

  // Pre-Verse Transition Phase (working backward from firstVerseFrame):
  // - Scroll Opening: 1.25s = 38 frames (unrolls outward from center)
  // - Dark Overlay Fade-Out: 1.0s = 30 frames (0.65 -> 0)
  // - Intro Text Splits Inward to vanish: 1.25s = 38 frames
  const SCROLL_OPEN_LEN = 38; // 1.25 seconds
  const OVERLAY_FADE_LEN = 30; // 1.0 second
  const TEXT_VANISH_LEN = 38; // 1.25 seconds

  const scrollOpenEnd = firstVerseFrame;
  const scrollOpenStart = scrollOpenEnd - SCROLL_OPEN_LEN;
  const overlayFadeEnd = scrollOpenStart;
  const overlayFadeStart = overlayFadeEnd - OVERLAY_FADE_LEN;
  const textVanishEnd = overlayFadeStart;
  const textVanishStart = textVanishEnd - TEXT_VANISH_LEN;

  // Verses Phase:
  const totalVersesFrames = verses.reduce(
    (sum, v) => sum + v.durationInFrames,
    0
  );
  const lastVerseEndFrame = firstVerseFrame + totalVersesFrames;

  // Scene Ending Transition:
  // - 1.0s hold on scroll after last verse: 30 frames
  // - Scroll closing (splits in to vanish): 1.25s = 38 frames
  // - 1.0s clean hold on mosque background before crossfade: 30 frames
  const SCROLL_CLOSE_START = lastVerseEndFrame + 30;
  const SCROLL_CLOSE_END = SCROLL_CLOSE_START + 38;

  // -------------------------------------------------------------
  // 2. ANIMATION CALCULATIONS
  // -------------------------------------------------------------

  // A. Dark Overlay Opacity:
  let overlayOpacity = 0;
  if (frame >= introAppearStart && frame < overlayFadeEnd) {
    if (frame < introAppearEnd) {
      overlayOpacity = interpolate(
        frame,
        [introAppearStart, introAppearEnd],
        [0, 0.65],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
    } else if (frame >= overlayFadeStart) {
      overlayOpacity = interpolate(
        frame,
        [overlayFadeStart, overlayFadeEnd],
        [0.65, 0],
        { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
      );
    } else {
      overlayOpacity = 0.65;
    }
  }

  // B. Intro Text Entrance: Split Outward across text bounds (50% -> 0%) over 1.25s
  const textEnterProgress = interpolate(
    frame,
    [introAppearStart, introAppearEnd],
    [0, 1],
    {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  // C. Intro Text Exit: Split Inward to center (0% -> 50%) over 1.25s
  const textVanishProgress = interpolate(
    frame,
    [textVanishStart, textVanishEnd],
    [0, 1],
    {
      easing: Easing.inOut(Easing.cubic),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  let isIntroTextVisible = false;
  let introTextInsetX = 50;

  if (frame >= introAppearStart && frame < textVanishEnd) {
    isIntroTextVisible = true;
    if (frame < introAppearEnd) {
      introTextInsetX = (1 - textEnterProgress) * 50;
    } else if (frame >= textVanishStart) {
      introTextInsetX = textVanishProgress * 50;
    } else {
      introTextInsetX = 0;
    }
  }

  // D. Scroll Opening: Unroll from center 50% -> 0% over 1.25s / 38 frames
  const openProgress = interpolate(
    frame,
    [scrollOpenStart, scrollOpenEnd],
    [0, 1],
    {
      easing: Easing.bezier(0.16, 1, 0.3, 1),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  // E. Scroll Closing: Roll into center 0% -> 50% over 1.25s / 38 frames
  const closeProgress = interpolate(
    frame,
    [SCROLL_CLOSE_START, SCROLL_CLOSE_END],
    [0, 1],
    {
      easing: Easing.in(Easing.cubic),
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  let isScrollVisible = false;
  let scrollInsetX = 50;

  if (frame >= scrollOpenStart && frame < SCROLL_CLOSE_END) {
    isScrollVisible = true;
    if (frame < scrollOpenEnd) {
      scrollInsetX = (1 - openProgress) * 50;
    } else if (frame >= SCROLL_CLOSE_START) {
      scrollInsetX = closeProgress * 50;
    } else {
      scrollInsetX = 0;
    }
  }

  // -------------------------------------------------------------
  // 3. RENDER
  // -------------------------------------------------------------
  let currentStartFrame = firstVerseFrame;

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* 1. BASE LAYER: Mosque Twilight Image */}
      <Img
        src={introBg}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />

      {/* 2. DARK OVERLAY */}
      {overlayOpacity > 0 && (
        <AbsoluteFill
          style={{
            backgroundColor: "#000000",
            opacity: overlayOpacity,
          }}
        />
      )}

      {/* 3. INTRO TEXT */}
      {intro && isIntroTextVisible && (
        <IntroSlide
          {...intro}
          textClipPath={`inset(0% ${introTextInsetX}% 0% ${introTextInsetX}%)`}
        />
      )}

      {/* 4. SCROLL BANNER */}
      {isScrollVisible && (
        <Img
          src={scrollBg}
          style={{
            position: "absolute",
            width: "100%",
            height: "100%",
            objectFit: "contain",
            clipPath: `inset(0% ${scrollInsetX}% 0% ${scrollInsetX}%)`,
            filter: "drop-shadow(0 15px 30px rgba(0, 0, 0, 0.85))",
          }}
        />
      )}

      {/* 5. VERSES SEQUENCE */}
      {verses.map((v, index) => {
        const startFrame = currentStartFrame;
        currentStartFrame += v.durationInFrames;

        return (
          <Sequence
            key={`${v.verseKey || "verse"}-${index}`}
            from={startFrame}
            durationInFrames={v.durationInFrames}
          >
            <FadeInOutSlide
              durationInFrames={v.durationInFrames}
              arabic={v.arabic}
              bengali={v.bengali}
            />
          </Sequence>
        );
      })}

      {/* 6. SCENE EXIT: Smooth fade to black in the final 30 frames (1.0s) */}
      {frame >= durationInFrames - 30 && (
        <AbsoluteFill
          style={{
            backgroundColor: "#000000",
            opacity: interpolate(
              frame,
              [durationInFrames - 30, durationInFrames],
              [0, 1],
              { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
            ),
          }}
        />
      )}
    </AbsoluteFill>
  );
};
