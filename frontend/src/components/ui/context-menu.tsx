import * as React from "react";

import * as ContextMenuPrimitive from "@radix-ui/react-context-menu";
import { Check, ChevronRight, Circle } from "lucide-react";

import {
  createMenuCheckboxItem,
  createMenuItem,
  createMenuLabel,
  createMenuRadioItem,
  createMenuSeparator,
  createMenuShortcut,
  createMenuSubContent,
  createMenuSubTrigger,
} from "@/components/ui/menu-factory";
import { menuShortcutClass, menuSubTriggerActiveClass } from "@/components/ui/shared-classes";

import { cn } from "@/lib/utils";

const ContextMenu = ContextMenuPrimitive.Root;

const ContextMenuTrigger = ContextMenuPrimitive.Trigger;

const ContextMenuGroup = ContextMenuPrimitive.Group;

const ContextMenuPortal = ContextMenuPrimitive.Portal;

const ContextMenuSub = ContextMenuPrimitive.Sub;

const ContextMenuRadioGroup = ContextMenuPrimitive.RadioGroup;

const ContextMenuSubTrigger = createMenuSubTrigger(
  ContextMenuPrimitive.SubTrigger,
  ContextMenuPrimitive.SubTrigger.displayName || "ContextMenuSubTrigger",
  {
    activeClassName: menuSubTriggerActiveClass,
    ChevronIcon: ChevronRight,
  },
);

const ContextMenuSubContent = createMenuSubContent(
  ContextMenuPrimitive.SubContent,
  ContextMenuPrimitive.SubContent.displayName || "ContextMenuSubContent",
  "shadow-md",
);

const ContextMenuContent = React.forwardRef<
  React.ElementRef<typeof ContextMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof ContextMenuPrimitive.Content>
>(({ className, ...props }, ref) => (
  <ContextMenuPrimitive.Portal>
    <ContextMenuPrimitive.Content
      ref={ref}
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md animate-in fade-in-80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className,
      )}
      {...props}
    />
  </ContextMenuPrimitive.Portal>
));
ContextMenuContent.displayName = ContextMenuPrimitive.Content.displayName;

const ContextMenuItem = createMenuItem(
  ContextMenuPrimitive.Item,
  ContextMenuPrimitive.Item.displayName || "ContextMenuItem",
);

const ContextMenuCheckboxItem = createMenuCheckboxItem(
  ContextMenuPrimitive.CheckboxItem,
  ContextMenuPrimitive.ItemIndicator,
  ContextMenuPrimitive.CheckboxItem.displayName || "ContextMenuCheckboxItem",
  {
    Icon: Check,
    iconClassName: "h-4 w-4",
  },
);

const ContextMenuRadioItem = createMenuRadioItem(
  ContextMenuPrimitive.RadioItem,
  ContextMenuPrimitive.ItemIndicator,
  ContextMenuPrimitive.RadioItem.displayName || "ContextMenuRadioItem",
  {
    Icon: Circle,
    iconClassName: "h-2 w-2 fill-current",
  },
);

const ContextMenuLabel = createMenuLabel(
  ContextMenuPrimitive.Label,
  ContextMenuPrimitive.Label.displayName || "ContextMenuLabel",
  "text-foreground",
);

const ContextMenuSeparator = createMenuSeparator(
  ContextMenuPrimitive.Separator,
  ContextMenuPrimitive.Separator.displayName || "ContextMenuSeparator",
  "bg-border",
);

const ContextMenuShortcut = createMenuShortcut("ContextMenuShortcut", menuShortcutClass);

export {
  ContextMenu,
  ContextMenuTrigger,
  ContextMenuContent,
  ContextMenuItem,
  ContextMenuCheckboxItem,
  ContextMenuRadioItem,
  ContextMenuLabel,
  ContextMenuSeparator,
  ContextMenuShortcut,
  ContextMenuGroup,
  ContextMenuPortal,
  ContextMenuSub,
  ContextMenuSubContent,
  ContextMenuSubTrigger,
  ContextMenuRadioGroup,
};
