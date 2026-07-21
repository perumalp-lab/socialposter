import { useEffect, useRef, useState } from "react";
import { Bell, CreditCard, LogOut, Menu, Search, Settings } from "lucide-react";
import { Link } from "react-router-dom";
import { useAuth } from "@/auth/AuthContext";
import { cn } from "@/lib/utils";

type Props = {
  onMenuClick?: () => void;
  showMenuButton?: boolean;
};

export function Header({ onMenuClick, showMenuButton }: Props) {
  const { user, logout } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!menuOpen) return;
    const onDoc = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    };
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [menuOpen]);

  const initials = user?.display_name
    ? user.display_name
        .split(/\s+/)
        .map((s) => s[0])
        .filter(Boolean)
        .slice(0, 2)
        .join("")
        .toUpperCase()
    : "?";

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur md:px-6">
      {showMenuButton && (
        <button
          type="button"
          onClick={onMenuClick}
          aria-label="Open menu"
          className="grid h-9 w-9 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <Menu className="h-5 w-5" />
        </button>
      )}

      <div className="relative hidden flex-1 sm:block">
        <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
        <input
          type="search"
          placeholder="Search posts, people, settings…"
          className={cn(
            "h-9 w-full max-w-md rounded-md border border-input bg-background pl-9 pr-3 text-sm",
            "placeholder:text-muted-foreground/70",
            "focus:outline-none focus:ring-2 focus:ring-ring",
          )}
        />
      </div>

      <div className="ml-auto flex items-center gap-2">
        <button
          type="button"
          aria-label="Notifications"
          className="relative grid h-9 w-9 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <Bell className="h-4 w-4" />
          <span className="absolute right-1.5 top-1.5 h-2 w-2 rounded-full bg-primary ring-2 ring-background" />
        </button>

        <div ref={menuRef} className="relative">
          <button
            type="button"
            onClick={() => setMenuOpen((o) => !o)}
            className="flex h-9 items-center gap-2 rounded-md pl-1 pr-2 hover:bg-accent"
            aria-label="Account menu"
            aria-expanded={menuOpen}
          >
            <span className="grid h-7 w-7 place-items-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
              {initials}
            </span>
            <span className="hidden text-sm font-medium md:inline">
              {user?.display_name || "Account"}
            </span>
          </button>

          {menuOpen && (
            <div className="absolute right-0 top-full z-40 mt-1 w-48 animate-fade-in overflow-hidden rounded-md border border-border bg-background shadow-md">
              <div className="border-b border-border px-3 py-2 text-xs">
                <div className="truncate font-medium">{user?.display_name}</div>
                <div className="truncate text-muted-foreground">{user?.email}</div>
              </div>
              <Link
                to="/settings"
                onClick={() => setMenuOpen(false)}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
              >
                <Settings className="h-4 w-4" />
                Settings
              </Link>
              <Link
                to="/settings/billing"
                onClick={() => setMenuOpen(false)}
                className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-accent"
              >
                <CreditCard className="h-4 w-4" />
                Billing
              </Link>
              <button
                type="button"
                onClick={() => void logout()}
                className="flex w-full items-center gap-2 border-t border-border px-3 py-2 text-left text-sm hover:bg-accent"
              >
                <LogOut className="h-4 w-4" />
                Sign out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
