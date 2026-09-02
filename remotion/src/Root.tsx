import React from "react";
import { Composition } from "remotion";
import { VerseSequence, VerseInput } from "./VerseSequence";

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
      defaultProps={{
        verses: [
          {
            verseKey: "1:1",
            arabic: "بِسْمِ اللَّهِ الرَّحْمَٰنِ الرَّحِيمِ",
            bengali: "পরম করুণাময়, অসীম দয়ালু আল্লাহর নামে",
            durationInFrames: 150,
          },
          {
            verseKey: "1:2",
            arabic: "الْحَمْدُ لِلَّهِ رَبِّ الْعَالَمِينَ",
            bengali: "যাবতীয় প্রশংসা জগতসমূহের রব আল্লাহরই জন্য",
            durationInFrames: 150,
          }
        ] as VerseInput[]
      }}
      calculateMetadata={({ props }) => {
        const verses = props.verses as VerseInput[];
        const durationInFrames = Math.max(verses.reduce((sum, v) => sum + v.durationInFrames, 0), FPS);
        return { durationInFrames };
      }}
    />
  );
};
