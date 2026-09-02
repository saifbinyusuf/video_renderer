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
