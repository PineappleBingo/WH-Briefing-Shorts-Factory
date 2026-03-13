import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors, fonts, safeZone } from "../styles/theme";
import type { Clip } from "../data";

interface FreezeFrameSequenceProps {
  clip: Clip;
}

export const FreezeFrameSequence: React.FC<FreezeFrameSequenceProps> = ({
  clip,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          padding: safeZone.horizontal,
          opacity,
        }}
      >
        <div
          style={{
            backgroundColor: colors.overlay,
            padding: "40px 48px",
            borderRadius: 16,
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontFamily: fonts.primary,
              fontSize: 40,
              color: colors.primary,
              marginBottom: 20,
              fontWeight: 600,
            }}
          >
            {clip.overlay.en}
          </div>
          <div
            style={{
              fontFamily: fonts.korean,
              fontSize: 34,
              color: colors.krText,
              lineHeight: 1.6,
            }}
          >
            {clip.overlay.kr}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
