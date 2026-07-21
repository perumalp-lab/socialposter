import {
  Award,
  BarChart3,
  Calendar,
  CalendarClock,
  FileText,
  GitBranch,
  Image,
  Inbox,
  LayoutDashboard,
  Mail,
  MessageCircle,
  PenSquare,
  Plug,
  Shield,
  Users,
  Video,
  Wand2,
  type LucideIcon,
} from "lucide-react";

export type NavItem = {
  label: string;
  to: string;
  icon: LucideIcon;
  badge?: string | number;
};

export type NavSection = {
  id: string;
  label: string;
  items: NavItem[];
};

export const NAV_SECTIONS: NavSection[] = [
  {
    id: "overview",
    label: "Overview",
    items: [{ label: "Dashboard", to: "/dashboard", icon: LayoutDashboard }],
  },
  {
    id: "content",
    label: "Content",
    items: [
      { label: "Compose", to: "/compose", icon: PenSquare },
      { label: "Drafts", to: "/drafts", icon: FileText },
      { label: "Calendar", to: "/calendar", icon: Calendar },
      { label: "Schedules", to: "/schedules", icon: CalendarClock },
      { label: "Media", to: "/media", icon: Image },
      { label: "Webinars", to: "/webinars", icon: Video },
    ],
  },
  {
    id: "insights",
    label: "Insights",
    items: [{ label: "Analytics", to: "/analytics", icon: BarChart3 }],
  },
  {
    id: "communication",
    label: "Communication",
    items: [{ label: "Inbox", to: "/inbox", icon: Inbox }],
  },
  {
    id: "automation",
    label: "Automation",
    items: [
      { label: "Path", to: "/automation/path", icon: GitBranch },
      { label: "New", to: "/automation/new", icon: Wand2 },
      { label: "Email Automation", to: "/automation/email", icon: Mail },
      { label: "WhatsApp Automation", to: "/automation/whatsapp", icon: MessageCircle },
      { label: "Certificates", to: "/automation/certificates", icon: Award },
      { label: "Platform Integrations", to: "/automation/integrations", icon: Plug },
    ],
  },
  {
    id: "system",
    label: "System",
    items: [
      { label: "Connections", to: "/connections", icon: Plug },
      { label: "Team", to: "/team", icon: Users },
      { label: "Admin", to: "/admin", icon: Shield },
    ],
  },
];
