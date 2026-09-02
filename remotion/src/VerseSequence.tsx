import React, { Fragment } from "react";
import { AbsoluteFill } from "remotion";
import { TransitionSeries, linearTiming } from "@remotion/transitions";
import { filmBurn } from "@remotion/transitions/film-burn";
import { VerseSlide } from "./VerseSlide";

export const TRANSITION_FRAMES = 45;

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
                presentation={filmBurn({ seed: i + 1 })}
                timing={linearTiming({ durationInFrames: TRANSITION_FRAMES })}
              />
            )}
          </Fragment>
        ))}
      </TransitionSeries>
    </AbsoluteFill>
  );
};