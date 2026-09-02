import React from "react";
import { AbsoluteFill, Img, Sequence, useCurrentFrame, interpolate } from "remotion";
import { VerseSlide } from "./VerseSlide";
import bg from "./verses_bg.png";

export const FADE_FRAMES = 30; // 1 second fade

export type VerseInput = {
  verseKey: string;
  arabic: string;
  bengali: string;
  durationInFrames: number;
};

const FadeInOutSlide: React.FC<{ durationInFrames: number; arabic: string; bengali: string }> = ({ durationInFrames, arabic, bengali }) => {
  const frame = useCurrentFrame();

  const opacity = interpolate(
    frame,
    [0, FADE_FRAMES, durationInFrames - FADE_FRAMES, durationInFrames],
    [0, 1, 1, 0],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  return (
    <AbsoluteFill style={{ opacity }}>
      <VerseSlide arabic={arabic} bengali={bengali} />
    </AbsoluteFill>
  );
};

export const VerseSequence: React.FC<{ verses: VerseInput[] }> = ({ verses }) => {
  let currentStartFrame = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <Img src={bg} style={{ position: "absolute", width: "100%", height: "100%", objectFit: "cover" }} />
      {verses.map((v) => {
        const startFrame = currentStartFrame;
        currentStartFrame += v.durationInFrames;
        
        return (
          <Sequence key={v.verseKey} from={startFrame} durationInFrames={v.durationInFrames}>
            <FadeInOutSlide durationInFrames={v.durationInFrames} arabic={v.arabic} bengali={v.bengali} />
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
