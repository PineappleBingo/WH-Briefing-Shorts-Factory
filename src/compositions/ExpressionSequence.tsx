import React from "react";
import { AbsoluteFill } from "remotion";
import { colors } from "../styles/theme";
import { Subtitle } from "../components/Subtitle";
import { HighlightText } from "../components/HighlightText";
import { ProgressBar } from "../components/ProgressBar";
import type { Clip } from "../data";

interface ExpressionSequenceProps {
  clip: Clip;
  index: number;
  total: number;
}

export const ExpressionSequence: React.FC<ExpressionSequenceProps> = ({
  clip,
  index,
  total,
}) => {
  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      <AbsoluteFill
        style={{ justifyContent: "center", alignItems: "center" }}
      >
        <HighlightText
          text={clip.overlay.en}
          color={clip.highlightColor ?? colors.keyword}
        />
      </AbsoluteFill>
      <Subtitle
        en={clip.overlay.en}
        kr={clip.overlay.kr}
        highlightColor={clip.highlightColor}
      />
      <ProgressBar current={index} total={total} />
    </AbsoluteFill>
  );
};
