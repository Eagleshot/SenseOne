import * as React from "react";

import * as DropdownMenuPrimitive from "@radix-ui/react-dropdown-menu";
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
import { menuShortcutDimClass, menuSubTriggerSoftActiveClass } from "@/components/ui/shared-classes";

import { cn } from "@/lib/utils";

const DropdownMenu = DropdownMenuPrimitive.Root;

const DropdownMenuTrigger = DropdownMenuPrimitive.Trigger;

const DropdownMenuGroup = DropdownMenuPrimitive.Group;

const DropdownMenuPortal = DropdownMenuPrimitive.Portal;

const DropdownMenuSub = DropdownMenuPrimitive.Sub;

const DropdownMenuRadioGroup = DropdownMenuPrimitive.RadioGroup;

const DropdownMenuSubTrigger = createMenuSubTrigger(
  DropdownMenuPrimitive.SubTrigger,
  DropdownMenuPrimitive.SubTrigger.displayName || "DropdownMenuSubTrigger",
  {
    activeClassName: menuSubTriggerSoftActiveClass,
    ChevronIcon: ChevronRight,
  },
);

const DropdownMenuSubContent = createMenuSubContent(
  DropdownMenuPrimitive.SubContent,
  DropdownMenuPrimitive.SubContent.displayName || "DropdownMenuSubContent",
  "shadow-lg",
);

const DropdownMenuContent = React.forwardRef<
  React.ElementRef<typeof DropdownMenuPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DropdownMenuPrimitive.Content>
>(({ className, sideOffset = 4, ...props }, ref) => (
  <DropdownMenuPrimitive.Portal>
    <DropdownMenuPrimitive.Content
      ref={ref}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className,
      )}
      {...props}
    />
  </DropdownMenuPrimitive.Portal>
));
DropdownMenuContent.displayName = DropdownMenuPrimitive.Content.displayName;

const DropdownMenuItem = createMenuItem(
  DropdownMenuPrimitive.Item,
  DropdownMenuPrimitive.Item.displayName || "DropdownMenuItem",
  "transition-colors",
);

const DropdownMenuCheckboxItem = createMenuCheckboxItem(
  DropdownMenuPrimitive.CheckboxItem,
  DropdownMenuPrimitive.ItemIndicator,
  DropdownMenuPrimitive.CheckboxItem.displayName || "DropdownMenuCheckboxItem",
  {
    Icon: Check,
    iconClassName: "h-4 w-4",
    extraClassName: "transition-colors",
  },
);

const DropdownMenuRadioItem = createMenuRadioItem(
  DropdownMenuPrimitive.RadioItem,
  DropdownMenuPrimitive.ItemIndicator,
  DropdownMenuPrimitive.RadioItem.displayName || "DropdownMenuRadioItem",
  {
    Icon: Circle,
    iconClassName: "h-2 w-2 fill-current",
    extraClassName: "transition-colors",
  },
);

const DropdownMenuLabel = createMenuLabel(
  DropdownMenuPrimitive.Label,
  DropdownMenuPrimitive.Label.displayName || "DropdownMenuLabel",
);

const DropdownMenuSeparator = createMenuSeparator(
  DropdownMenuPrimitive.Separator,
  DropdownMenuPrimitive.Separator.displayName || "DropdownMenuSeparator",
  "bg-muted",
);

const DropdownMenuShortcut = createMenuShortcut("DropdownMenuShortcut", menuShortcutDimClass);

export {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuCheckboxItem,
  DropdownMenuRadioItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuGroup,
  DropdownMenuPortal,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuRadioGroup,
};
