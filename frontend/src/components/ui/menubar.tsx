import * as React from "react";

import * as MenubarPrimitive from "@radix-ui/react-menubar";
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

const MenubarMenu = MenubarPrimitive.Menu;

const MenubarGroup = MenubarPrimitive.Group;

const MenubarPortal = MenubarPrimitive.Portal;

const MenubarSub = MenubarPrimitive.Sub;

const MenubarRadioGroup = MenubarPrimitive.RadioGroup;

const Menubar = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Root>
>(({ className, ...props }, ref) => (
  <MenubarPrimitive.Root
    ref={ref}
    className={cn("flex h-10 items-center space-x-1 rounded-md border bg-background p-1", className)}
    {...props}
  />
));
Menubar.displayName = MenubarPrimitive.Root.displayName;

const MenubarTrigger = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Trigger>,
  React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Trigger>
>(({ className, ...props }, ref) => (
  <MenubarPrimitive.Trigger
    ref={ref}
    className={cn(
      "flex cursor-default select-none items-center rounded-sm px-3 py-1.5 text-sm font-medium outline-none data-[state=open]:bg-accent data-[state=open]:text-accent-foreground focus:bg-accent focus:text-accent-foreground",
      className,
    )}
    {...props}
  />
));
MenubarTrigger.displayName = MenubarPrimitive.Trigger.displayName;

const MenubarSubTrigger = createMenuSubTrigger(
  MenubarPrimitive.SubTrigger,
  MenubarPrimitive.SubTrigger.displayName || "MenubarSubTrigger",
  {
    activeClassName: menuSubTriggerActiveClass,
    ChevronIcon: ChevronRight,
  },
);

const MenubarSubContent = createMenuSubContent(
  MenubarPrimitive.SubContent,
  MenubarPrimitive.SubContent.displayName || "MenubarSubContent",
);

const MenubarContent = React.forwardRef<
  React.ElementRef<typeof MenubarPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof MenubarPrimitive.Content>
>(({ className, align = "start", alignOffset = -4, sideOffset = 8, ...props }, ref) => (
  <MenubarPrimitive.Portal>
    <MenubarPrimitive.Content
      ref={ref}
      align={align}
      alignOffset={alignOffset}
      sideOffset={sideOffset}
      className={cn(
        "z-50 min-w-[12rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground shadow-md data-[state=open]:animate-in data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2",
        className,
      )}
      {...props}
    />
  </MenubarPrimitive.Portal>
));
MenubarContent.displayName = MenubarPrimitive.Content.displayName;

const MenubarItem = createMenuItem(MenubarPrimitive.Item, MenubarPrimitive.Item.displayName || "MenubarItem");

const MenubarCheckboxItem = createMenuCheckboxItem(
  MenubarPrimitive.CheckboxItem,
  MenubarPrimitive.ItemIndicator,
  MenubarPrimitive.CheckboxItem.displayName || "MenubarCheckboxItem",
  {
    Icon: Check,
    iconClassName: "h-4 w-4",
  },
);

const MenubarRadioItem = createMenuRadioItem(
  MenubarPrimitive.RadioItem,
  MenubarPrimitive.ItemIndicator,
  MenubarPrimitive.RadioItem.displayName || "MenubarRadioItem",
  {
    Icon: Circle,
    iconClassName: "h-2 w-2 fill-current",
  },
);

const MenubarLabel = createMenuLabel(
  MenubarPrimitive.Label,
  MenubarPrimitive.Label.displayName || "MenubarLabel",
);

const MenubarSeparator = createMenuSeparator(
  MenubarPrimitive.Separator,
  MenubarPrimitive.Separator.displayName || "MenubarSeparator",
  "bg-muted",
);

const MenubarShortcut = createMenuShortcut("MenubarShortcut", menuShortcutClass);

export {
  Menubar,
  MenubarMenu,
  MenubarTrigger,
  MenubarContent,
  MenubarItem,
  MenubarSeparator,
  MenubarLabel,
  MenubarCheckboxItem,
  MenubarRadioGroup,
  MenubarRadioItem,
  MenubarPortal,
  MenubarSubContent,
  MenubarSubTrigger,
  MenubarGroup,
  MenubarSub,
  MenubarShortcut,
};
