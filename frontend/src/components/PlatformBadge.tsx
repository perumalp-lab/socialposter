import { platformBrand, platformLabel } from "@/lib/platformColors";
import { cn } from "@/lib/utils";

type Props = {
  platform: string;
  /** "soft" (default) is a tinted pill; "solid" fills with the brand color. */
  variant?: "soft" | "solid" | "dot";
  className?: string;
};

/** Small uppercase pill labeling a platform with its brand color. */
export function PlatformBadge({ platform, variant = "soft", className }: Props) {
  const brand = platformBrand(platform);
  const label = platformLabel(platform);

  if (variant === "dot") {
    return (
      <span className={cn("inline-flex items-center gap-1.5", className)}>
        <span
          aria-hidden
          className="inline-block h-2 w-2 rounded-full"
          style={{ background: brand.bg }}
        />
        <span className="text-xs font-medium">{label}</span>
      </span>
    );
  }

  if (variant === "solid") {
    return (
      <span
        className={cn(
          "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
          className,
        )}
        style={{ background: brand.bg, color: brand.fg }}
      >
        {label}
      </span>
    );
  }

  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide",
        className,
      )}
      style={{ background: brand.softBg, color: brand.softFg }}
    >
      {label}
    </span>
  );
}
