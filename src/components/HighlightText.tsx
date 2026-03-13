import React from "react";
import { spring, useCurrentFrame, useVideoConfig } from "remotion";
import { colors, fonts } from "../styles/theme";

interface HighlightTextProps {
  text: string;
  color?: string;
}

export const HighlightText: React.FC<HighlightTextProps> = ({
  text,
  color = colors.keyword,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const scale = spring({ frame, fps, config: { damping: 200 } });

  return (
    <div
      style={{
        fontFamily: fonts.primary,
        fontSize: 64,
        fontWeight: 800,
        color,
        transform: `scale(${scale})`,
        textAlign: "center",
      }}
    >
      {text}
    </div>
  );
};
