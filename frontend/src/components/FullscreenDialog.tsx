import type { FC, ReactElement, ReactNode } from "react";

import { Dialog, DialogContent, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

type FullscreenDialogProps = {
  title: string;
  children: ReactNode;
  trigger?: ReactElement;
  open?: boolean;
  onOpenChange?: (open: boolean) => void;
  contentClassName?: string;
  edgeToEdge?: boolean;
};

export const FullscreenDialog: FC<FullscreenDialogProps> = ({
  title,
  children,
  trigger,
  open,
  onOpenChange,
  contentClassName,
  edgeToEdge = false,
}) => (
  <Dialog open={open} onOpenChange={onOpenChange}>
    {trigger ? <DialogTrigger asChild>{trigger}</DialogTrigger> : null}
    <DialogContent
      hideCloseButton
      className={cn(
        edgeToEdge
          ? "h-screen max-h-screen w-screen max-w-screen overflow-hidden border-0 bg-background p-0 rounded-none"
          : "h-[calc(100vh-1rem)] max-h-none w-[calc(100vw-1rem)] max-w-none overflow-hidden border border-border/40 bg-background/95 p-0 sm:h-[calc(100vh-2rem)] sm:w-[calc(100vw-2rem)]",
        contentClassName
      )}
    >
      <DialogTitle className="sr-only">{title}</DialogTitle>
      <div className="h-full w-full">{children}</div>
    </DialogContent>
  </Dialog>
);

