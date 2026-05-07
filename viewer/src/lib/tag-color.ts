/**
 * Stable pseudo-HSL tint per tag slug (readable on dark rails).
 */

function tagHue(tag: string): number {
  let h = 0
  for (let i = 0; i < tag.length; i++) {
    h = (h + tag.charCodeAt(i) * (i + 7)) % 360
  }
  return h
}

/** Solid accent (e.g. legends). */
export function tagAccentColor(tag: string): string {
  return `hsl(${tagHue(tag)} 55% 45%)`
}

export function shotLabelColor(tag: string): { bg: string; fg: string } {
  return {
    bg: `hsl(${tagHue(tag)} 54% 42% / 0.58)`,
    fg: "#fafafa",
  }
}
