import React from "react";
import { AbsoluteFill, Img } from "remotion";
import { IntroSlide, IntroData } from "./IntroSlide";
import introBg from "./intro_bg.png";
import { ChannelWatermark } from "./ChannelWatermark";

export const Thumbnail: React.FC<IntroData> = (props) => {
  return (
    <AbsoluteFill style={{ backgroundColor: "#000" }}>
      {/* 1. Base Layer: Mosque Twilight Background */}
      <Img
        src={introBg}
        style={{
          position: "absolute",
          width: "100%",
          height: "100%",
          objectFit: "cover",
        }}
      />

      {/* 2. Dark Overlay for high contrast & readable typography */}
      <AbsoluteFill
        style={{
          backgroundColor: "#000000",
          opacity: 0.65,
        }}
      />

      {/* 3. Intro Title & Bengali Typography */}
      <IntroSlide {...props} />

      {/* 4. Channel Watermark Logo */}
      <ChannelWatermark opacity={0.6} />
    </AbsoluteFill>
  );
};
