import { Navigate, Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "@/auth/ProtectedRoute";
import { DashboardLayout } from "@/components/layout/DashboardLayout";
import { LoginPage } from "@/pages/LoginPage";
import { DashboardPage } from "@/pages/DashboardPage";
import { CalendarPage } from "@/pages/CalendarPage";
import { DraftsPage } from "@/pages/DraftsPage";
import { ComposePage } from "@/pages/ComposePage";
import { ConnectionsPage } from "@/pages/ConnectionsPage";
import { AdminPage } from "@/pages/AdminPage";
import { SettingsPage } from "@/pages/SettingsPage";
import { MediaPage } from "@/pages/MediaPage";
import { SchedulesPage } from "@/pages/SchedulesPage";
import { InboxPage } from "@/pages/InboxPage";
import { AnalyticsPage } from "@/pages/AnalyticsPage";
import { AutomationPage } from "@/pages/AutomationPage";
import { AutomationPathPage } from "@/pages/automation/AutomationPathPage";
import { AutomationNewPage } from "@/pages/automation/AutomationNewPage";
import { AutomationEmailPage } from "@/pages/automation/AutomationEmailPage";
import { AutomationWhatsAppPage } from "@/pages/automation/AutomationWhatsAppPage";
import { AutomationCertificatesPage } from "@/pages/automation/AutomationCertificatesPage";
import { AutomationIntegrationsPage } from "@/pages/automation/AutomationIntegrationsPage";
import { TeamPage } from "@/pages/TeamPage";
import { BillingPage } from "@/pages/BillingPage";
import { PricingPage } from "@/pages/PricingPage";
import { WebinarsPage } from "@/pages/WebinarsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/pricing" element={<PricingPage />} />
      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="compose" element={<ComposePage />} />
        <Route path="drafts" element={<DraftsPage />} />
        <Route path="calendar" element={<CalendarPage />} />
        <Route path="schedules" element={<SchedulesPage />} />
        <Route path="media" element={<MediaPage />} />
        <Route path="analytics" element={<AnalyticsPage />} />
        <Route path="inbox" element={<InboxPage />} />
        <Route path="connections" element={<ConnectionsPage />} />
        <Route path="automation" element={<AutomationPage />} />
        <Route path="automation/path" element={<AutomationPathPage />} />
        <Route path="automation/new" element={<AutomationNewPage />} />
        <Route path="automation/email" element={<AutomationEmailPage />} />
        <Route path="automation/whatsapp" element={<AutomationWhatsAppPage />} />
        <Route path="automation/certificates" element={<AutomationCertificatesPage />} />
        <Route path="automation/integrations" element={<AutomationIntegrationsPage />} />
        <Route path="team" element={<TeamPage />} />
        <Route path="webinars" element={<WebinarsPage />} />
        <Route path="admin" element={<AdminPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="settings/billing" element={<BillingPage />} />
      </Route>
    </Routes>
  );
}
