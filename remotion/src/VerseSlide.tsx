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
        family: "shokuntola",
        url: staticFile("fonts/shokuntola.ttf"),
      }),
      loadFont({
        family: "bengali",
        url: staticFile("fonts/bengali.ttf"),
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
      <div style={{ textAlign: "center", maxWidth: "60%" }}>
        <div
          style={{
            fontFamily: "ArabicFont",
            fontSize: 80,
            color: "#00000",
            direction: "rtl",
            lineHeight: 1.5,
            textShadow: "2px 2px 6px rgba(0,0,0,0.5)",
          }}
        >
          {arabic}
        </div>
        <div
          style={{
            fontFamily: "bengali",
            fontSize: 60,
            color: "#000000",
            marginTop: 30,
            lineHeight: 1.5,
            textShadow: "2px 2px 6px rgba(0,0,0,0.5)",
          }}
        >
          {bengali}
        </div>
      </div>
    </AbsoluteFill>
  );
};
