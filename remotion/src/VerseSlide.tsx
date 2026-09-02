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
      <div style={{ textAlign: "center", maxWidth: "70%" }}>
        <div
          style={{
            fontFamily: "ArabicFont",
            fontSize: 70,
            color: "#FFD700",
            direction: "rtl",
            lineHeight: 1.6,
            textShadow: "2px 2px 6px rgba(0,0,0,0.75)",
          }}
        >
          {arabic}
        </div>
        <div
          style={{
            fontFamily: "BengaliFont",
            fontSize: 55,
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
