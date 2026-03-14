import React from "react";
import {
  AbsoluteFill,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts, safeZone } from "../styles/theme";
import { ProgressBar } from "../components/ProgressBar";
import type { Clip } from "../data";

interface BlankSequenceProps {
  clip: Clip;
  index: number;
  total: number;
}

/**
 * Pass 2: Replay with the keyword blanked out.
 * The learner tries to recall the expression (cloze deletion).
 */
export const BlankSequence: React.FC<BlankSequenceProps> = ({
  clip,
  index,
  total,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const blankScale = spring({ frame, fps, config: { damping: 200 } });
  const keyword = clip.keyword ?? "";
  const blank = "_".repeat(Math.max(5, keyword.length));

  // Replace keyword in the sentence with blanks
  const sentence = clip.overlay.en;
  const blankedSentence = keyword
    ? sentence.replace(new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"), blank)
    : sentence;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      {/* Question mark prompt */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          paddingBottom: 200,
        }}
      >
        <div
          style={{
            fontFamily: fonts.primary,
            fontSize: 120,
            fontWeight: 800,
            color: colors.accent,
            transform: `scale(${blankScale})`,
            opacity: 0.3,
          }}
        >
          ?
        </div>
      </AbsoluteFill>

      {/* Blanked sentence at bottom */}
      <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          paddingBottom: safeZone.bottom,
          paddingLeft: safeZone.horizontal,
          paddingRight: safeZone.horizontal,
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
              fontSize: 40,
              lineHeight: 1.4,
              color: colors.primary,
              fontWeight: 600,
            }}
          >
            {blankedSentence}
          </div>
          <div
            style={{
              fontFamily: fonts.korean,
              fontSize: 32,
              lineHeight: 1.4,
              color: colors.krText,
              marginTop: 8,
            }}
          >
            {clip.overlay.kr}
          </div>
        </div>
      </AbsoluteFill>
      <ProgressBar current={index} total={total} />
    </AbsoluteFill>
  );
};
