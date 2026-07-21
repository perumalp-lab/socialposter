import { Link } from "react-router-dom";
import { Sparkles } from "lucide-react";
import type { PlanLimitBody } from "@/lib/billing";

/**
 * Inline banner shown when an action is blocked by the user's plan.
 * Renders the server-supplied message and a link to the billing page.
 */
export function PlanLimitAlert({ limit }: { limit: PlanLimitBody }) {
  return (
    <div className="flex flex-wrap items-start gap-3 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800">
      <Sparkles className="mt-0.5 h-4 w-4 shrink-0" />
      <div className="flex-1">
        <div className="font-medium">{limit.message}</div>
        <div className="text-xs text-amber-700">
          You're using {limit.current} of {limit.limit} on the {limit.plan} plan.
        </div>
      </div>
      <Link
        to="/settings/billing"
        className="inline-flex h-8 items-center rounded-md bg-amber-600 px-3 text-xs font-medium text-white hover:bg-amber-700"
      >
        View plans →
      </Link>
    </div>
  );
}
