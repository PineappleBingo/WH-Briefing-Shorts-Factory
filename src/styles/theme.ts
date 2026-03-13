/**
 * Isolated theme configuration.
 * Engineer agent patches this file on font-missing errors.
 * Edit freely without touching render logic.
 */

export const CANVAS = {
  width: 1080,
  height: 1920,
  fps: 30,
} as const;

export const colors = {
  background: "#0D0D0D",
  primary: "#FFFFFF",
  accent: "#FFD700", // Hook highlight
  keyword: "#00BFFF", // Expression highlight
  krText: "#CCCCCC", // Korean explanation
  ctaBanner: "#FF4444", // CTA background
  progressBar: "#FFD700",
  overlay: "rgba(0, 0, 0, 0.6)",
} as const;

export const fonts = {
  primary: "Arial, Helvetica, sans-serif",
  mono: "'Courier New', monospace",
  // Korean-friendly fallback chain
  korean: "'Noto Sans KR', 'Malgun Gothic', sans-serif",
} as const;

export const caption = {
  maxLines: 2,
  maxCharsPerLine: 42,
  enFontSize: 48,
  krFontSize: 36,
  lineHeight: 1.4,
} as const;

export const safeZone = {
  top: 120, // pixels from top
  bottom: 200, // pixels from bottom (avoid YouTube UI)
  horizontal: 60,
} as const;
