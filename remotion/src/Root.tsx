import React from "react";
import { Composition, Still } from "remotion";
import { VerseSequence, VerseSequenceProps, FPS } from "./VerseSequence";
import { SpeechWatermark } from "./SpeechWatermark";
import { ExtroScene, EXTRO_TOTAL_FRAMES } from "./ExtroScene";

const WIDTH = 1920;
const HEIGHT = 1080;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {/* 1. Intro + Verses Scene */}
      <Composition
        id="VerseSequence"
        component={VerseSequence}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          intro: {
            title: "তাফসীরুল কুরআন",
            surah_name: "সূরা আলে-ইমরান",
            verse_range: "৪৫-৪৬",
            date: "২ সেপ্টেম্বর, ২০২৬",
            speaker: "মুফতি রাশেদুর রহমান",
          },
          firstVerseStartSec: 15.057,
          verses: [
            {
              verseKey: "1:1",
              arabic: "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
              bengali: "পরম করুণাময়, অসীম দয়ালু আল্লাহর নামে",
              durationInFrames: 150,
            },
          ],
        } as VerseSequenceProps}
        calculateMetadata={({ props }) => {
          const typedProps = props as VerseSequenceProps;
          const verses = typedProps.verses || [];
          const firstVerseStartSec = typedProps.firstVerseStartSec ?? 15.057;
          const firstVerseFrame = Math.max(
            Math.round(firstVerseStartSec * FPS),
            150
          );
          const totalVersesFrames = verses.reduce(
            (sum, v) => sum + (v.durationInFrames || 0),
            0
          );
          // Scene 1 ends after: 1s scroll hold (30) + 1.25s scroll close (38) + 1s mosque hold (30)
          const durationInFrames = Math.max(
            firstVerseFrame + totalVersesFrames + 30 + 38 + 30,
            FPS
          );
          return { durationInFrames };
        }}
      />

      {/* 2. Speech Watermark (Single transparent still for top-left overlay) */}
      <Still
        id="SpeechWatermark"
        component={SpeechWatermark}
        width={WIDTH}
        height={HEIGHT}
        defaultProps={{
          surah_name: "সূরা আলে-ইমরান",
          verse_range: "৪৫-৪৬",
        }}
      />

      {/* 3. Extro Scene (Invitation + Closing audio tracks) */}
      <Composition
        id="ExtroScene"
        component={ExtroScene}
        fps={FPS}
        width={WIDTH}
        height={HEIGHT}
        durationInFrames={EXTRO_TOTAL_FRAMES}
      />
    </>
  );
};
