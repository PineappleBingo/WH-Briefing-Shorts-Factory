import { CANVAS } from "../styles/theme";

/** Convert seconds to frame number */
export const secondsToFrames = (seconds: number): number =>
  Math.round(seconds * CANVAS.fps);

/** Convert frame number to seconds */
export const framesToSeconds = (frames: number): number =>
  frames / CANVAS.fps;

/** Calculate duration in frames from start/end seconds */
export const durationFrames = (startSec: number, endSec: number): number =>
  secondsToFrames(endSec - startSec);
