import React from "react";
import { AbsoluteFill, Sequence } from "remotion";
import { colors } from "../styles/theme";
import { secondsToFrames, durationFrames } from "../utils/timing";
import { HookSequence } from "./HookSequence";
import { ExpressionSequence } from "./ExpressionSequence";
import { FreezeFrameSequence } from "./FreezeFrameSequence";
import { WrapUpSequence } from "./WrapUpSequence";
import type { Part } from "../data";

interface MainCompositionProps {
  part: Part;
}

export const MainComposition: React.FC<MainCompositionProps> = ({ part }) => {
  const expressionClips = part.clips.filter((c) => c.type === "expression");
  const totalExpressions = expressionClips.length;
  let expressionIndex = 0;

  return (
    <AbsoluteFill style={{ backgroundColor: colors.background }}>
      {part.clips.map((clip, i) => {
        const from = secondsToFrames(clip.start);
        const duration = durationFrames(clip.start, clip.end);

        let content: React.ReactNode;
        switch (clip.type) {
          case "hook":
            content = <HookSequence clip={clip} />;
            break;
          case "expression":
            expressionIndex++;
            content = (
              <ExpressionSequence
                clip={clip}
                index={expressionIndex}
                total={totalExpressions}
              />
            );
            break;
          case "freeze_frame":
            content = <FreezeFrameSequence clip={clip} />;
            break;
          case "wrapup":
            content = <WrapUpSequence clip={clip} />;
            break;
        }

        return (
          <Sequence key={i} from={from} durationInFrames={duration}>
            {content}
          </Sequence>
        );
      })}
    </AbsoluteFill>
  );
};
