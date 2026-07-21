import { NavLink } from "react-router-dom";
import type { NavItem } from "@/config/navigation";
import { cn } from "@/lib/utils";

type Props = {
  item: NavItem;
  collapsed: boolean;
};

export function SidebarItem({ item, collapsed }: Props) {
  const Icon = item.icon;

  return (
    <NavLink
      to={item.to}
      title={collapsed ? item.label : undefined}
      className={({ isActive }) =>
        cn(
          "group relative flex h-9 items-center gap-3 rounded-md px-2 text-sm font-medium",
          "transition-colors duration-150",
          "text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-foreground",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          isActive && "bg-sidebar-accent text-foreground",
          collapsed && "justify-center px-0",
        )
      }
    >
      {({ isActive }) => (
        <>
          <span
            aria-hidden
            className={cn(
              "absolute left-0 top-1/2 h-5 w-[3px] -translate-y-1/2 rounded-r-full bg-primary",
              "transition-opacity duration-150",
              isActive ? "opacity-100" : "opacity-0",
            )}
          />
          <Icon
            className={cn(
              "h-4 w-4 shrink-0 transition-transform duration-150",
              "group-hover:scale-105",
              isActive ? "text-primary" : "text-muted-foreground",
            )}
          />
          <span
            className={cn(
              "min-w-0 flex-1 truncate transition-opacity duration-150",
              collapsed && "pointer-events-none w-0 opacity-0",
            )}
          >
            {item.label}
          </span>
          {item.badge != null && !collapsed && (
            <span className="ml-auto inline-flex h-5 min-w-[20px] items-center justify-center rounded-full bg-primary/10 px-1.5 text-[10px] font-semibold text-primary">
              {item.badge}
            </span>
          )}
        </>
      )}
    </NavLink>
  );
}
