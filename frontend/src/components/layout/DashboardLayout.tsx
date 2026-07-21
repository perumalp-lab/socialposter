import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { useMediaQuery } from "@/hooks/useMediaQuery";
import { cn } from "@/lib/utils";
import { Header } from "./Header";
import { MobileDrawer } from "./MobileDrawer";
import { Sidebar } from "./Sidebar";

const SIDEBAR_STATE_KEY = "sp.sidebar.collapsed";

export function DashboardLayout() {
  const isDesktop = useMediaQuery("(min-width: 1024px)");
  const location = useLocation();

  const [collapsed, setCollapsed] = useState<boolean>(() => {
    if (typeof window === "undefined") return false;
    return window.localStorage.getItem(SIDEBAR_STATE_KEY) === "1";
  });
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    window.localStorage.setItem(SIDEBAR_STATE_KEY, collapsed ? "1" : "0");
  }, [collapsed]);

  // Close mobile drawer on route change.
  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  return (
    <div className="flex h-full w-full">
      {isDesktop && (
        <Sidebar
          collapsed={collapsed}
          onToggleCollapsed={() => setCollapsed((c) => !c)}
        />
      )}

      {!isDesktop && (
        <MobileDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)}>
          <Sidebar collapsed={false} variant="drawer" />
        </MobileDrawer>
      )}

      <div
        className={cn(
          "flex min-w-0 flex-1 flex-col transition-[margin] duration-200 ease-out",
        )}
      >
        <Header
          onMenuClick={() => setDrawerOpen(true)}
          showMenuButton={!isDesktop}
        />
        <main className="flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-6xl px-4 py-6 md:px-8 md:py-8">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
}
