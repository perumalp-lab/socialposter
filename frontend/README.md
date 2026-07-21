# SocialPoster Frontend

Standalone Vite + React + TypeScript + Tailwind dashboard, kept separate from the
root Capacitor `package.json`.

## Run

```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
```

## Architecture

```
src/
├── App.tsx                       routes, mounted under <DashboardLayout/>
├── config/navigation.ts          single source of truth for nav sections + items
├── hooks/useMediaQuery.ts        breakpoint detection
├── lib/utils.ts                  cn() helper (clsx + tailwind-merge)
├── components/layout/
│   ├── DashboardLayout.tsx       shell: sidebar + header + <Outlet/>
│   ├── Sidebar.tsx               desktop + drawer variant
│   ├── SidebarSection.tsx        renders one group (Content, Insights, …)
│   ├── SidebarItem.tsx           NavLink with active rail + hover scale
│   ├── Header.tsx                search, notifications, profile
│   └── MobileDrawer.tsx          off-canvas slide-in for < lg
└── pages/index.tsx               placeholder pages for all 8 routes
```

### Adding a nav item

Edit `src/config/navigation.ts` — append to the right `NavSection.items`. Add
the matching `<Route>` in `App.tsx`. Nothing else changes.

### Active state

`<NavLink>` from react-router exposes `isActive`. We render a 3px rounded rail
on the left edge and tint the icon with `text-primary`.

### Collapsing

`DashboardLayout` owns the `collapsed` state and persists it to
`localStorage`. The `Sidebar` animates `width` (220ms ease-out); labels and
section headings fade with `opacity` so the icons stay centered as the column
shrinks to 68px.

### Mobile

Below `lg` (1024px), the desktop sidebar unmounts and a `MobileDrawer` takes
its place. It traps `Escape`, locks body scroll, and closes on route change.

### shadcn/ui

The components follow shadcn conventions (CSS variables for theme tokens,
`cn()` helper, Tailwind-first) but don't pull in the full Radix dependency
graph. To swap in the real primitives later:

```bash
npx shadcn@latest init
npx shadcn@latest add button sheet dropdown-menu avatar input
```

…then replace `MobileDrawer` with shadcn's `Sheet`, the avatar/profile button
with `DropdownMenu`, etc.

### Dark mode

CSS variables for `.dark` are already wired in `src/index.css`. Toggle by
adding/removing `class="dark"` on `<html>`.
