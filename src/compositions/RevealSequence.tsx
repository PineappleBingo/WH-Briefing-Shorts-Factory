import React from "react";
import {
  AbsoluteFill,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { colors, fonts, safeZone } from "../styles/theme";
import { ProgressBar } from "../components/ProgressBar";
import type { Clip } from "../data";

interface RevealSequenceProps {
  clip: Clip;
  index: number;
  total: number;
}

/**
 * Pass 3: Full reveal — keyword highlighted with definition + Korean explanation.
 */
export const RevealSequence: React.FC<RevealSequenceProps> = ({
  clip,
  index,
  total,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const fadeIn = interpolate(frame, [0, 10], [0, 1], {
    extrapolateRight: "clamp",
  });
  const keywordScale = spring({ frame, fps, config: { damping: 200 } });

  const keyword = clip.keyword ?? clip.overlay.en;
  const highlightColor = clip.highlightColor ?? colors.keyword;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      {/* Keyword large and highlighted in center */}
      <AbsoluteFill
        style={{
          justifyContent: "center",
          alignItems: "center",
          paddingBottom: 100,
        }}
      >
        <div
          style={{
            fontFamily: fonts.primary,
            fontSize: 64,
            fontWeight: 800,
            color: highlightColor,
            transform: `scale(${keywordScale})`,
            textAlign: "center",
          }}
        >
          {keyword}
        </div>
      </AbsoluteFill>

      {/* Definition + Korean explanation card */}
      <AbsoluteFill
        style={{
          justifyContent: "flex-end",
          alignItems: "center",
          paddingBottom: safeZone.bottom,
          paddingLeft: safeZone.horizontal,
          paddingRight: safeZone.horizontal,
          opacity: fadeIn,
        }}
      >
        <div
          style={{
            backgroundColor: colors.overlay,
            padding: "24px 32px",
            borderRadius: 16,
            textAlign: "center",
          }}
        >
          <div
            style={{
              fontFamily: fonts.primary,
              fontSize: 36,
              color: colors.primary,
              marginBottom: 12,
              fontWeight: 600,
            }}
          >
            {clip.overlay.en}
          </div>
          <div
            style={{
              fontFamily: fonts.korean,
              fontSize: 32,
              color: colors.krText,
              lineHeight: 1.6,
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
