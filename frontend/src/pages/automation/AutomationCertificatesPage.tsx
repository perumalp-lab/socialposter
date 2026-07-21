import { Award } from "lucide-react";

export function AutomationCertificatesPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Certificates</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Generate and manage automated certificates.
          </p>
        </div>
      </div>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background py-16 text-center">
        <Award className="h-8 w-8 text-muted-foreground" />
        <p className="mt-3 text-sm font-medium">No certificates yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Create automated certificate templates for events and courses.
        </p>
      </div>
    </div>
  );
}
