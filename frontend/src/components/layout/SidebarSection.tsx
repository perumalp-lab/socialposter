import type { NavSection } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { SidebarItem } from "./SidebarItem";

type Props = {
  section: NavSection;
  collapsed: boolean;
};

export function SidebarSection({ section, collapsed }: Props) {
  return (
    <div className="mb-4 last:mb-1">
      <div
        className={cn(
          "px-2 pb-1 text-[11px] font-medium uppercase tracking-wider text-muted-foreground",
          "transition-opacity duration-150",
          collapsed && "pointer-events-none h-0 select-none overflow-hidden opacity-0",
        )}
        aria-hidden={collapsed || undefined}
      >
        {section.label}
      </div>
      <ul className="space-y-0.5">
        {section.items.map((item) => (
          <li key={item.to}>
            <SidebarItem item={item} collapsed={collapsed} />
          </li>
        ))}
      </ul>
    </div>
  );
}
