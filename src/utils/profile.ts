export type PerformanceMode = "LOW" | "HIGH";

export const getPerformanceMode = (): PerformanceMode => {
  const mode = process.env.PERFORMANCE_MODE?.toUpperCase();
  return mode === "HIGH" ? "HIGH" : "LOW";
};

export const getConcurrency = (): number => {
  const mode = getPerformanceMode();
  if (mode === "LOW") return 1;
  const cores = process.env.REMOTION_CPU_CORES;
  return cores ? parseInt(cores, 10) : 0; // 0 = auto (all cores)
};
