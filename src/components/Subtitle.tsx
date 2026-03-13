import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { caption, colors, fonts, safeZone } from "../styles/theme";

interface SubtitleProps {
  en: string;
  kr: string;
  highlightColor?: string;
}

export const Subtitle: React.FC<SubtitleProps> = ({
  en,
  kr,
  highlightColor,
}) => {
  const frame = useCurrentFrame();
  const opacity = interpolate(frame, [0, 8], [0, 1], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-end",
        alignItems: "center",
        paddingBottom: safeZone.bottom,
        paddingLeft: safeZone.horizontal,
        paddingRight: safeZone.horizontal,
        opacity,
      }}
    >
      <div
        style={{
          textAlign: "center",
          backgroundColor: colors.overlay,
          padding: "16px 24px",
          borderRadius: 12,
        }}
      >
        <div
          style={{
            fontFamily: fonts.primary,
            fontSize: caption.enFontSize,
            lineHeight: caption.lineHeight,
            color: highlightColor ?? colors.primary,
            fontWeight: 700,
            marginBottom: 8,
          }}
        >
          {en}
        </div>
        <div
          style={{
            fontFamily: fonts.korean,
            fontSize: caption.krFontSize,
            lineHeight: caption.lineHeight,
            color: colors.krText,
          }}
        >
          {kr}
        </div>
      </div>
    </AbsoluteFill>
  );
};
