import React from "react";
import { Img } from "remotion";
import icbLogo from "./icb_logo.png";

export const CHANNEL_WATERMARK_OPACITY = 0.5;
export const CHANNEL_WATERMARK_WIDTH = 180;
export const CHANNEL_WATERMARK_BOTTOM = 40;
export const CHANNEL_WATERMARK_RIGHT = 50;

export const ChannelWatermark: React.FC<{
  opacity?: number;
  width?: number;
  bottom?: number;
  right?: number;
}> = ({
  opacity = CHANNEL_WATERMARK_OPACITY,
  width = CHANNEL_WATERMARK_WIDTH,
  bottom = CHANNEL_WATERMARK_BOTTOM,
  right = CHANNEL_WATERMARK_RIGHT,
}) => {
  return (
    <div
      style={{
        position: "absolute",
        bottom,
        right,
        zIndex: 9999,
        pointerEvents: "none",
        opacity,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        filter: "drop-shadow(0 2px 8px rgba(0, 0, 0, 0.85))",
      }}
    >
      <Img
        src={icbLogo}
        style={{
          width,
          height: "auto",
          objectFit: "contain",
        }}
      />
    </div>
  );
};
