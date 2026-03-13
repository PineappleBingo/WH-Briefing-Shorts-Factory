import React from "react";
import { AbsoluteFill } from "remotion";
import { colors, fonts, safeZone } from "../styles/theme";

interface ProgressBarProps {
  current: number;
  total: number;
}

export const ProgressBar: React.FC<ProgressBarProps> = ({
  current,
  total,
}) => {
  const progress = current / total;

  return (
    <AbsoluteFill
      style={{
        justifyContent: "flex-start",
        alignItems: "center",
        paddingTop: safeZone.top,
      }}
    >
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 12,
        }}
      >
        <div
          style={{
            width: 200,
            height: 6,
            backgroundColor: "rgba(255,255,255,0.2)",
            borderRadius: 3,
            overflow: "hidden",
          }}
        >
          <div
            style={{
              width: `${progress * 100}%`,
              height: "100%",
              backgroundColor: colors.progressBar,
              borderRadius: 3,
            }}
          />
        </div>
        <span
          style={{
            fontFamily: fonts.primary,
            fontSize: 24,
            color: colors.primary,
          }}
        >
          {current}/{total}
        </span>
      </div>
    </AbsoluteFill>
  );
};
