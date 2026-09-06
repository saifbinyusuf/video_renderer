import React, { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";

let watermarkFontsLoaded = false;

export const SpeechWatermark: React.FC<{
  surah_name?: string;
  verse_range?: string;
}> = ({ surah_name = "সূরা আলে-ইমরান", verse_range = "৪৫-৪৬" }) => {
  const [handle] = useState(() =>
    watermarkFontsLoaded ? null : delayRender("Loading watermark fonts")
  );

  useEffect(() => {
    if (watermarkFontsLoaded) return;
    Promise.all([
      loadFont({
        family: "bengali",
        url: staticFile("fonts/bengali.ttf"),
      }),
      loadFont({
        family: "shokuntola",
        url: staticFile("fonts/shokuntola.ttf"),
      }),
    ]).then(() => {
      watermarkFontsLoaded = true;
      if (handle !== null) continueRender(handle);
    });
  }, [handle]);

  const textShadowStyle =
    "0 0 16px rgba(0, 0, 0, 0.95), 0 0 35px rgba(0, 0, 0, 0.8), 2px 2px 5px rgba(0, 0, 0, 0.95)";

  return (
    <AbsoluteFill style={{ backgroundColor: "transparent" }}>
      <div
        style={{
          position: "absolute",
          top: 60,
          left: 80,
          fontFamily: "bengali, shokuntola, sans-serif",
          color: "#fae588",
          textAlign: "left",
        }}
      >
        {/* Line 1: তাফসীর */}
        <div
          style={{
            fontSize: 60,
            fontWeight: 700,
            lineHeight: 1.25,
            textShadow: textShadowStyle,
          }}
        >
          তাফসীর
        </div>
        {/* Line 2: <surah name> */}
        <div
          style={{
            fontSize: 60,
            fontWeight: 500,
            marginTop: 8,
            lineHeight: 1.25,
            textShadow: textShadowStyle,
          }}
        >
          {surah_name}
        </div>
        {/* Line 3: আয়াত <verse range> */}
        <div
          style={{
            fontSize: 60,
            fontWeight: 500,
            marginTop: 8,
            lineHeight: 1.25,
            textShadow: textShadowStyle,
          }}
        >
          আয়াত {verse_range}
        </div>
      </div>
    </AbsoluteFill>
  );
};
