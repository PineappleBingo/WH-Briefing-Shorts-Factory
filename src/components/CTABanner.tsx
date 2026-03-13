import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { colors, fonts, safeZone } from "../styles/theme";

interface CTABannerProps {
  text: string;
}

export const CTABanner: React.FC<CTABannerProps> = ({ text }) => {
  const frame = useCurrentFrame();
  const slideUp = interpolate(frame, [0, 15], [100, 0], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: safeZone.bottom + 40,
      }}
    >
      <div
        style={{
          backgroundColor: colors.ctaBanner,
          padding: "16px 48px",
          borderRadius: 30,
          transform: `translateY(${slideUp}px)`,
          fontFamily: fonts.primary,
          fontSize: 40,
          fontWeight: 700,
          color: colors.primary,
        }}
      >
        {text}
      </div>
    </AbsoluteFill>
  );
};
