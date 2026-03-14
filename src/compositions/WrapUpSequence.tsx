import React from "react";
import { AbsoluteFill } from "remotion";
import { colors } from "../styles/theme";
import { CTABanner } from "../components/CTABanner";
import { Subtitle } from "../components/Subtitle";
import type { Clip } from "../data";

interface WrapUpSequenceProps {
  clip: Clip;
}

export const WrapUpSequence: React.FC<WrapUpSequenceProps> = ({ clip }) => {
  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      <Subtitle en={clip.overlay.en} kr={clip.overlay.kr} />
      <CTABanner text="Follow for more!" />
    </AbsoluteFill>
  );
};
