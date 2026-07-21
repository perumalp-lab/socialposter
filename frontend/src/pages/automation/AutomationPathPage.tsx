import { GitBranch } from "lucide-react";

export function AutomationPathPage() {
  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Path</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Design multi-step automation workflows.
          </p>
        </div>
      </div>
      <div className="flex flex-col items-center justify-center rounded-lg border border-dashed border-border bg-background py-16 text-center">
        <GitBranch className="h-8 w-8 text-muted-foreground" />
        <p className="mt-3 text-sm font-medium">No paths yet</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Create visual automation paths to chain triggers and actions.
        </p>
      </div>
    </div>
  );
}
