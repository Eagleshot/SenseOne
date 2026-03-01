import React from "react";

import { formatDistanceToNow } from "date-fns";

import { useApp } from "@/contexts/AppContext";
import { cn } from "@/lib/utils";

export const StatusSummary: React.FC = () => {
  const { activeWebcam } = useApp();

  const lastUpdateAgo = formatDistanceToNow(activeWebcam.lastUpdate, { addSuffix: true })
    .replace("about ", "")
    .replace(/minutes?/g, "min.");

  const now = new Date();
  const nextUpdateIn =
    activeWebcam.nextUpdate > now
      ? `in ${Math.round((activeWebcam.nextUpdate.getTime() - now.getTime()) / (60 * 1000))} min.`
      : "Soon";

  return (
    <div
      className={cn(
        "px-4 py-2 flex items-center gap-3 rounded-lg border backdrop-blur-sm",
        activeWebcam.isOnline ? "bg-success/10 border-success/20" : "bg-destructive/10 border-destructive/20"
      )}
    >
      <span
        className={cn(
          "h-2.5 w-2.5 rounded-full animate-pulse",
          activeWebcam.isOnline ? "bg-success" : "bg-destructive"
        )}
      />
      <div className="text-xs text-muted-foreground">
        <span className="text-foreground">Last Online: {lastUpdateAgo}</span>
        <span className="mx-1 text-muted-foreground">-</span>
        <span className="text-foreground">
          Next Online: {activeWebcam.isOnline ? nextUpdateIn : "Offline"}
        </span>
      </div>
    </div>
  );
};
