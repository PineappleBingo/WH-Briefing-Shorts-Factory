import React from "react";
import {
  AbsoluteFill,
  Video,
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
 * Pass 2: Blank out — replay the clip with the keyword hidden in the subtitle.
 * Audio plays normally so the learner must listen and recall the missing word (cloze deletion).
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

  const blankedSentence = keyword
    ? clip.overlay.en.replace(
        new RegExp(keyword.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), "gi"),
        blank,
      )
    : clip.overlay.en;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      {clip.videoSrc && (
        <Video
          src={clip.videoSrc}
          startFrom={Math.round((clip.clipStartSec ?? 0) * fps)}
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
        />
      )}

      {/* "?" prompt — cues learner to listen for the missing word */}
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
            opacity: 0.5,
          }}
        >
          ?
        </div>
      </AbsoluteFill>

      {/* Blanked subtitle */}
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
