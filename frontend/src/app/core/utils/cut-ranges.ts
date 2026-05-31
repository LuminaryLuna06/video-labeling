// frontend/src/app/core/utils/cut-ranges.ts

export interface CutRange {
  id?: string;
  start: number;
  end: number;
}

/**
 * Clamp each range to [0, duration], swap inverted starts/ends, drop
 * sub-millisecond ranges, sort by start, and merge any overlaps.
 * Used both client-side (button disable logic) and as a reference for
 * the server-side equivalent in dam_server.py.
 */
export function normalizeCuts(cuts: CutRange[], duration: number): CutRange[] {
  const cleaned = cuts
    .map((c) => {
      const lo = Math.min(c.start, c.end);
      const hi = Math.max(c.start, c.end);
      return { ...c, start: Math.max(0, lo), end: Math.min(duration, hi) };
    })
    .filter((c) => c.end - c.start > 0.001)
    .sort((a, b) => a.start - b.start);

  const merged: CutRange[] = [];
  for (const c of cleaned) {
    const last = merged[merged.length - 1];
    if (last && c.start <= last.end) {
      last.end = Math.max(last.end, c.end);
    } else {
      merged.push({ ...c });
    }
  }
  return merged;
}

/**
 * Complement of `cuts` within [0, duration] — the ranges that survive.
 * Returns [] when cuts cover the whole video; returns [{0,duration}] for no cuts.
 */
export function keepRanges(cuts: CutRange[], duration: number): CutRange[] {
  const normalized = normalizeCuts(cuts, duration);
  const keep: CutRange[] = [];
  let cursor = 0;
  for (const c of normalized) {
    if (c.start > cursor) keep.push({ start: cursor, end: c.start });
    cursor = c.end;
  }
  if (cursor < duration) keep.push({ start: cursor, end: duration });
  return keep.filter(r => r.end - r.start > 0.001);
}
