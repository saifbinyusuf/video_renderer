import React from "react";
import {
  AbsoluteFill,
  Img,
  Sequence,
  Audio,
  interpolate,
  Easing,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { ExtroInviteSlide, ExtroVerseSlide } from "./ExtroSlide";
import { ChannelWatermark } from "./ChannelWatermark";
import introBg from "./intro_bg.png";
import extroInviteAudio from "./extro_invite.mp3";
import extroVerseAudio from "./extro_verse.mp3";

export const EXTRO_INVITE_FRAMES = 179; // ~5.956s
export const EXTRO_VERSE_FRAMES = 232;  // ~7.732s
export const EXTRO_TOTAL_FRAMES = EXTRO_INVITE_FRAMES + EXTRO_VERSE_FRAMES; // 411 frames (~13.7s)

// Volume multipliers (1.0 = 100%, 0.8 = 80%, etc.)
export const EXTRO_INVITE_VOLUME = 1.0;
export const EXTRO_VERSE_VOLUME = 1.0;

export const ExtroScene: React.FC = () => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();

  const EXTRO_SPLIT_LEN = 38; // 1.25s

  // Scene-level Fade In from black (first 30 frames / 1.0s)
  const sceneFadeIn = interpolate(frame, [0, 30], [1, 0], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Scene-level Fade Out to black (last 30 frames / 1.0s)
  const sceneFadeOut = interpolate(
    frame,
    [durationInFrames - 30, durationInFrames],
    [0, 1],
    {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }
  );

  // Overlay fades in from 0 to 0.65 over 30 frames
  const overlayOpacity = interpolate(frame, [0, 30], [0, 0.65], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // Scene 1: Invite (frame 0 to 179)
  const isScene1 = frame < EXTRO_INVITE_FRAMES;
  let extro1InsetX = 50;
  if (isScene1) {
    if (frame < EXTRO_SPLIT_LEN) {
      const p = interpolate(frame, [0, EXTRO_SPLIT_LEN], [0, 1], {
        easing: Easing.bezier(0.16, 1, 0.3, 1),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      extro1InsetX = (1 - p) * 50;
    } else if (frame >= EXTRO_INVITE_FRAMES - EXTRO_SPLIT_LEN) {
      const p = interpolate(
        frame,
        [EXTRO_INVITE_FRAMES - EXTRO_SPLIT_LEN, EXTRO_INVITE_FRAMES],
        [0, 1],
        {
          easing: Easing.inOut(Easing.cubic),
          extrapolateLeft: "clamp",
          extrapolateRight: "clamp",
        }
      );
      extro1InsetX = p * 50;
    } else {
      extro1InsetX = 0;
    }
  }

  // Scene 2: Verse (frame 179 to 411)
  const isScene2 = frame >= EXTRO_INVITE_FRAMES;
  let extro2InsetX = 50;
  if (isScene2) {
    const scene2Frame = frame - EXTRO_INVITE_FRAMES;
    if (scene2Frame < EXTRO_SPLIT_LEN) {
      const p = interpolate(scene2Frame, [0, EXTRO_SPLIT_LEN], [0, 1], {
        easing: Easing.bezier(0.16, 1, 0.3, 1),
        extrapolateLeft: "clamp",
        extrapolateRight: "clamp",
      });
      extro2InsetX = (1 - p) * 50;
    } else {
      extro2InsetX = 0;
    }
  }

  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      <Img
        src={introBg}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />
      <AbsoluteFill
        style={{
          backgroundColor: "#000000",
          opacity: overlayOpacity,
        }}
      />
      {isScene1 && (
        <ExtroInviteSlide
          textClipPath={`inset(0% ${extro1InsetX}% 0% ${extro1InsetX}%)`}
        />
      )}
      <Sequence from={0} durationInFrames={EXTRO_INVITE_FRAMES}>
        <Audio src={extroInviteAudio} volume={EXTRO_INVITE_VOLUME} />
      </Sequence>

      {isScene2 && (
        <ExtroVerseSlide
          textClipPath={`inset(0% ${extro2InsetX}% 0% ${extro2InsetX}%)`}
        />
      )}
      <Sequence from={EXTRO_INVITE_FRAMES} durationInFrames={EXTRO_VERSE_FRAMES}>
        <Audio src={extroVerseAudio} volume={EXTRO_VERSE_VOLUME} />
      </Sequence>

      {/* Scene-level Fade In overlay */}
      {sceneFadeIn > 0 && (
        <AbsoluteFill
          style={{
            backgroundColor: "#000000",
            opacity: sceneFadeIn,
          }}
        />
      )}

      {/* Scene-level Fade Out overlay */}
      {sceneFadeOut > 0 && (
        <AbsoluteFill
          style={{
            backgroundColor: "#000000",
            opacity: sceneFadeOut,
          }}
        />
      )}

      {/* Persistent Channel Watermark (Top-most layer, 40% opacity) */}
      <ChannelWatermark />
    </AbsoluteFill>
  );
};
