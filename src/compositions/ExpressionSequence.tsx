import React from "react";
import { AbsoluteFill, Video, useVideoConfig } from "remotion";
import { colors } from "../styles/theme";
import { Subtitle } from "../components/Subtitle";
import { ProgressBar } from "../components/ProgressBar";
import type { Clip } from "../data";

interface ExpressionSequenceProps {
  clip: Clip;
  index: number;
  total: number;
}

/**
 * Pass 1: Raw — play the original clip as-is.
 * Learner hears the expression naturally. No keyword banner — don't reveal yet.
 */
export const ExpressionSequence: React.FC<ExpressionSequenceProps> = ({
  clip,
  index,
  total,
}) => {
  const { fps } = useVideoConfig();

  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      {clip.videoSrc && (
        <Video
          src={clip.videoSrc}
          startFrom={Math.round((clip.clipStartSec ?? 0) * fps)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      )}
      {/* Plain subtitle — no keyword highlight on raw pass */}
      <Subtitle en={clip.overlay.en} kr={clip.overlay.kr} />
      <ProgressBar current={index} total={total} />
    </AbsoluteFill>
  );
};
