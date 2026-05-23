import { formatDistanceToNow } from "date-fns";

import { useApp } from "@/contexts/AppContext";
import { LOADING_LABEL, UNAVAILABLE_LABEL } from "@/lib/placeholders";
import { cn } from "@/lib/utils";

export const StatusSummary: React.FC = () => {
  const { activeWebcam } = useApp();

  const isOnline = activeWebcam.isOnline;
  const hasStatus = typeof isOnline === "boolean";
  const pendingLabel = activeWebcam.id ? LOADING_LABEL : UNAVAILABLE_LABEL;
  const lastUpdateAgo = activeWebcam.lastUpdate
    ? formatDistanceToNow(activeWebcam.lastUpdate, { addSuffix: true }).replace("about ", "").replace(/minutes?/g, "min.")
    : pendingLabel;

  const now = new Date();
  const nextUpdateIn =
    activeWebcam.nextUpdate && activeWebcam.nextUpdate > now
      ? `in ${Math.round((activeWebcam.nextUpdate.getTime() - now.getTime()) / (60 * 1000))} min.`
      : UNAVAILABLE_LABEL;

  return (
    <div
      className={cn(
        "px-4 py-2 flex items-center gap-3 rounded-lg border backdrop-blur-sm",
        !hasStatus
          ? "bg-muted/40 border-border/60"
          : isOnline
            ? "bg-success/10 border-success/20"
            : "bg-destructive/10 border-destructive/20"
      )}
    >
      <span
        className={cn(
          "h-2.5 w-2.5 rounded-full",
          !hasStatus ? "bg-muted-foreground/60" : "animate-pulse",
          hasStatus && isOnline ? "bg-success" : hasStatus ? "bg-destructive" : ""
        )}
      />
      <div className="text-xs text-muted-foreground">
        <span className="text-foreground">Last Online: {lastUpdateAgo}</span>
        <span className="mx-1 text-muted-foreground">-</span>
        <span className="text-foreground">
          Next Online: {!hasStatus ? pendingLabel : isOnline ? nextUpdateIn : "Offline"}
        </span>
      </div>
    </div>
  );
};

