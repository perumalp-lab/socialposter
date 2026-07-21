import type { CSSProperties, ReactNode } from "react";
import { platformBrand, platformLabel } from "@/lib/platformColors";
import { cn } from "@/lib/utils";

type Props = {
  platform: string;
  selected: boolean;
  disabled?: boolean;
  onClick?: () => void;
  title?: string;
  /** Extra content rendered to the right of the label (e.g. "·offline"). */
  children?: ReactNode;
  className?: string;
};

/** Interactive platform pill — filled with brand color when selected,
 *  bordered with brand color when not. Uses inline styles since each
 *  brand has a unique color outside Tailwind's palette. */
export function PlatformChip({
  platform,
  selected,
  disabled,
  onClick,
  title,
  children,
  className,
}: Props) {
  const brand = platformBrand(platform);
  const label = platformLabel(platform);

  const style: CSSProperties = selected
    ? { background: brand.bg, color: brand.fg, borderColor: "transparent" }
    : disabled
      ? {}
      : { borderColor: brand.border, color: brand.softFg };

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      style={style}
      className={cn(
        "h-8 rounded-full border px-3 text-xs font-medium transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        !selected && !disabled && "bg-background hover:brightness-95",
        disabled && "cursor-not-allowed border-border bg-muted text-muted-foreground opacity-60",
        className,
      )}
    >
      {label}
      {children}
    </button>
  );
}
