import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts, safeZone } from "../styles/theme";
import type { Clip } from "../data";

interface HookSequenceProps {
  clip: Clip;
}

export const HookSequence: React.FC<HookSequenceProps> = ({ clip }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame, fps, config: { damping: 200 } });
  const bgOpacity = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        backgroundColor: colors.background,
        justifyContent: "center",
        alignItems: "center",
        padding: safeZone.horizontal,
      }}
    >
      <div
        style={{
          backgroundColor: colors.accent,
          padding: "32px 48px",
          borderRadius: 20,
          transform: `scale(${scale})`,
          opacity: bgOpacity,
          textAlign: "center",
        }}
      >
        <div
          style={{
            fontFamily: fonts.primary,
            fontSize: 52,
            fontWeight: 800,
            color: colors.background,
            marginBottom: 16,
          }}
        >
          {clip.overlay.en}
        </div>
        <div
          style={{
            fontFamily: fonts.korean,
            fontSize: 36,
            color: "rgba(0,0,0,0.7)",
          }}
        >
          {clip.overlay.kr}
        </div>
      </div>
    </AbsoluteFill>
  );
};
