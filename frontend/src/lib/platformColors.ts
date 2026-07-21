/** Per-platform brand colors. Used for chips, badges, and accent dots. */

export type PlatformBrand = {
  /** Display label override (defaults to capitalized name). */
  label?: string;
  /** Solid brand background (used when chip is "on"). */
  bg: string;
  /** Foreground when on top of `bg`. */
  fg: string;
  /** Tinted background for badges/hover (lighter or alpha'd brand color). */
  softBg: string;
  /** Foreground when on top of `softBg`. */
  softFg: string;
  /** Border color for "off" chip variant. */
  border: string;
};

/** Hex / rgb-comma values keep tooltips and snippets simple to read.
 *  They're plain strings so we can use them in inline `style={}` props
 *  without depending on Tailwind being able to lex dynamic class names. */
const BRANDS: Record<string, PlatformBrand> = {
  linkedin: {
    label: "LinkedIn",
    bg: "#0A66C2",
    fg: "#ffffff",
    softBg: "rgba(10, 102, 194, 0.10)",
    softFg: "#0A66C2",
    border: "rgba(10, 102, 194, 0.45)",
  },
  twitter: {
    label: "X",
    bg: "#0F1419",
    fg: "#ffffff",
    softBg: "rgba(15, 20, 25, 0.08)",
    softFg: "#0F1419",
    border: "rgba(15, 20, 25, 0.30)",
  },
  facebook: {
    label: "Facebook",
    bg: "#1877F2",
    fg: "#ffffff",
    softBg: "rgba(24, 119, 242, 0.10)",
    softFg: "#1877F2",
    border: "rgba(24, 119, 242, 0.45)",
  },
  instagram: {
    label: "Instagram",
    /* Instagram is a gradient — bg uses it; soft variants use the warm pink. */
    bg: "linear-gradient(45deg, #f09433, #e6683c, #dc2743, #cc2366, #bc1888)",
    fg: "#ffffff",
    softBg: "rgba(220, 39, 67, 0.10)",
    softFg: "#dc2743",
    border: "rgba(220, 39, 67, 0.45)",
  },
  youtube: {
    label: "YouTube",
    bg: "#FF0000",
    fg: "#ffffff",
    softBg: "rgba(255, 0, 0, 0.10)",
    softFg: "#cc0000",
    border: "rgba(255, 0, 0, 0.45)",
  },
  whatsapp: {
    label: "WhatsApp",
    bg: "#25D366",
    fg: "#ffffff",
    softBg: "rgba(37, 211, 102, 0.10)",
    softFg: "#1fa756",
    border: "rgba(37, 211, 102, 0.45)",
  },
};

/** Fallback for unknown platforms — uses the theme's primary. */
const FALLBACK: PlatformBrand = {
  bg: "hsl(var(--primary))",
  fg: "hsl(var(--primary-foreground))",
  softBg: "hsl(var(--accent))",
  softFg: "hsl(var(--accent-foreground))",
  border: "hsl(var(--border))",
};

export function platformBrand(name: string): PlatformBrand {
  return BRANDS[name?.toLowerCase()] ?? FALLBACK;
}

export function platformLabel(name: string): string {
  return BRANDS[name?.toLowerCase()]?.label ?? name;
}
