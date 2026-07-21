import { ChevronsLeft, ChevronsRight, Sparkles } from "lucide-react";
import { NAV_SECTIONS } from "@/config/navigation";
import { cn } from "@/lib/utils";
import { SidebarSection } from "./SidebarSection";

type SidebarProps = {
  collapsed?: boolean;
  onToggleCollapsed?: () => void;
  variant?: "default" | "drawer";
};

export function Sidebar({
  collapsed = false,
  onToggleCollapsed,
  variant = "default",
}: SidebarProps) {
  const isDrawer = variant === "drawer";

  return (
    <aside
      data-collapsed={collapsed}
      className={cn(
        "group/sidebar flex h-full shrink-0 flex-col border-r border-sidebar-border bg-sidebar text-sidebar-foreground",
        "transition-[width] duration-200 ease-out",
        isDrawer ? "w-72" : collapsed ? "w-[68px]" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex h-14 items-center gap-2 border-b border-sidebar-border px-3",
          collapsed && !isDrawer && "justify-center px-0",
        )}
      >
        <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary text-primary-foreground">
          <Sparkles className="h-4 w-4" />
        </div>
        {(!collapsed || isDrawer) && (
          <span className="truncate text-sm font-semibold tracking-tight">
            Kryptams
          </span>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto px-2 py-3">
        {NAV_SECTIONS.map((section) => (
          <SidebarSection
            key={section.id}
            section={section}
            collapsed={collapsed && !isDrawer}
          />
        ))}
      </nav>

      {!isDrawer && onToggleCollapsed && (
        <button
          type="button"
          onClick={onToggleCollapsed}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          className={cn(
            "flex h-10 items-center gap-2 border-t border-sidebar-border px-3 text-xs font-medium text-muted-foreground",
            "transition-colors hover:bg-sidebar-accent hover:text-foreground",
            collapsed && "justify-center px-0",
          )}
        >
          {collapsed ? (
            <ChevronsRight className="h-4 w-4" />
          ) : (
            <>
              <ChevronsLeft className="h-4 w-4" />
              <span>Collapse</span>
            </>
          )}
        </button>
      )}
    </aside>
  );
}
