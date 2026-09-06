import React, { useEffect, useState } from "react";
import { AbsoluteFill, continueRender, delayRender, staticFile } from "remotion";
import { loadFont } from "@remotion/fonts";

let extroFontsLoaded = false;

export const ExtroInviteSlide: React.FC<{ textClipPath?: string }> = ({
  textClipPath,
}) => {
  const [handle] = useState(() =>
    extroFontsLoaded ? null : delayRender("Loading extro fonts")
  );

  useEffect(() => {
    if (extroFontsLoaded) return;
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
      extroFontsLoaded = true;
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
      <div
        style={{
          display: "inline-block",
          width: "fit-content",
          maxWidth: "85%",
          clipPath: textClipPath,
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 700,
            lineHeight: 1.4,
            textShadow: textShadowStyle,
          }}
        >
          প্রতি বুধবার এশার নামাযের পর বুয়েট সেন্ট্রাল মসজিদে এই তাফসীর হালাকাহ হয়।
        </div>
        <div
          style={{
            fontSize: 88,
            fontWeight: 700,
            marginTop: 40,
            lineHeight: 1.3,
            textShadow: textShadowStyle,
          }}
        >
          আমন্ত্রণ রইলো!
        </div>
      </div>
    </AbsoluteFill>
  );
};

export const ExtroVerseSlide: React.FC<{ textClipPath?: string }> = ({
  textClipPath,
}) => {
  const [handle] = useState(() =>
    extroFontsLoaded ? null : delayRender("Loading extro fonts")
  );

  useEffect(() => {
    if (extroFontsLoaded) return;
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
      extroFontsLoaded = true;
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
      <div
        style={{
          display: "inline-block",
          width: "fit-content",
          maxWidth: "85%",
          clipPath: textClipPath,
        }}
      >
        <div
          style={{
            fontSize: 120,
            fontWeight: 700,
            lineHeight: 1.3,
            textShadow: textShadowStyle,
          }}
        >
          জাযাকাল্লাহু খাইরান
        </div>
      </div>
    </AbsoluteFill>
  );
};
