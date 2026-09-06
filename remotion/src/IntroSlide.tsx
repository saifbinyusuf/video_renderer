import React, { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";

export type IntroData = {
  title?: string;
  surah_name: string;
  verse_range: string;
  date: string;
  speaker: string;
  textClipPath?: string;
};

let introFontsLoaded = false;

export const IntroSlide: React.FC<IntroData> = ({
  title = "তাফসীরুল কুরআন",
  surah_name,
  verse_range,
  date,
  speaker,
  textClipPath,
}) => {
  const [handle] = useState(() =>
    introFontsLoaded ? null : delayRender("Loading intro fonts")
  );

  useEffect(() => {
    if (introFontsLoaded) return;
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
      introFontsLoaded = true;
      if (handle !== null) continueRender(handle);
    });
  }, [handle]);

  const textShadowStyle =
    "0 0 16px rgba(0, 0, 0, 0.95), 0 0 35px rgba(0, 0, 0, 0.8), 2px 2px 5px rgba(0, 0, 0, 0.95)";

  return (
    <AbsoluteFill
      style={{
        justifyContent: "center",
        alignItems: "center",
        fontFamily: "bengali, shokuntola, sans-serif",
        color: "#fae588",
        textAlign: "center",
      }}
    >
      {/* Constrained bounding box so clipPath animates strictly across the text itself */}
      <div
        style={{
          display: "inline-block",
          width: "fit-content",
          maxWidth: "85%",
          clipPath: textClipPath,
        }}
      >
        {/* 1. Largest text */}
        <div
          style={{
            fontSize: 130,
            fontWeight: 700,
            letterSpacing: 2,
            lineHeight: 1.3,
            textShadow: textShadowStyle,
          }}
        >
          {title}
        </div>

        {/* 2. Surah & Verses */}
        <div
          style={{
            fontSize: 95,
            fontWeight: 700,
            marginTop: 32,
            lineHeight: 1.3,
            textShadow: textShadowStyle,
          }}
        >
          {surah_name}ঃ আয়াত {verse_range}
        </div>

        {/* 3. Mosque and Date */}
        <div
          style={{
            fontSize: 80,
            fontWeight: 600,
            marginTop: 28,
            lineHeight: 1.3,
            textShadow: textShadowStyle,
          }}
        >
          বুয়েট সেন্ট্রাল মসজিদ, {date}
        </div>

        {/* 4. Speaker */}
        <div
          style={{
            fontSize: 60,
            fontWeight: 500,
            marginTop: 36,
            lineHeight: 1.3,
            textShadow: textShadowStyle,
          }}
        >
          আলোচকঃ {speaker}
        </div>
      </div>
    </AbsoluteFill>
  );
};
