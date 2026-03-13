import React from "react";
import { Composition } from "remotion";
import { MainComposition } from "./compositions/MainComposition";
import { data } from "./data";
import { CANVAS } from "./styles/theme";
import { secondsToFrames } from "./utils/timing";

const getPartDuration = (partIndex: number): number => {
  const part = data.parts[partIndex];
  if (!part) return CANVAS.fps * 60;
  const lastClip = part.clips[part.clips.length - 1];
  return secondsToFrames(lastClip.end);
};

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const Comp = MainComposition as React.FC<any>;

export const RemotionRoot: React.FC = () => {
  return (
    <>
      {data.parts.map((part, i) => (
        <Composition
          key={part.id}
          id={part.id}
          component={Comp}
          durationInFrames={getPartDuration(i)}
          fps={CANVAS.fps}
          width={CANVAS.width}
          height={CANVAS.height}
          defaultProps={{ part }}
        />
      ))}
    </>
  );
};
