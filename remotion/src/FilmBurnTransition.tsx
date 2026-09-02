import React from "react";
import { interpolate } from "remotion";
import type {
  TransitionPresentation,
  TransitionPresentationComponentProps,
} from "@remotion/transitions";

type FilmBurnProps = {
  intensity?: number;
};

const FilmBurnPresentation: React.FC<
  TransitionPresentationComponentProps<FilmBurnProps>
> = ({ children, presentationDirection, presentationProgress, passedProps }) => {
  const intensity = passedProps.intensity ?? 1;

  // Flash peaks in the middle of the transition, fades at both ends
  const flash =
    interpolate(presentationProgress, [0, 0.5, 1], [0, 1, 0]) * intensity;

  const opacity =
    presentationDirection === "entering"
      ? interpolate(presentationProgress, [0, 0.4, 1], [0, 0.2, 1])
      : interpolate(presentationProgress, [0, 0.6, 1], [1, 0.8, 0]);

  return (
    <div style={{ position: "absolute", width: "100%", height: "100%", opacity }}>
      {children}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background:
            "radial-gradient(circle at 50% 50%, rgba(255,205,120,0.95) 0%, rgba(255,120,0,0.65) 40%, rgba(0,0,0,0) 72%)",
          mixBlendMode: "screen",
          opacity: flash,
        }}
      />
    </div>
  );
};

export const filmBurn = (
  props: FilmBurnProps = {}
): TransitionPresentation<FilmBurnProps> => ({
  component: FilmBurnPresentation,
  props,
});
