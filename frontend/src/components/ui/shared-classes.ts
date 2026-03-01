export const modalOverlayClass =
  "fixed inset-0 z-50 bg-black/80 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0";

export const menuSubTriggerBaseClass =
  "flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none";

export const menuSubTriggerActiveClass =
  "data-[state=open]:bg-accent data-[state=open]:text-accent-foreground focus:bg-accent focus:text-accent-foreground";

export const menuSubTriggerSoftActiveClass = "data-[state=open]:bg-accent focus:bg-accent";

export const menuItemClass =
  "relative flex cursor-default select-none items-center rounded-sm px-2 py-1.5 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 focus:bg-accent focus:text-accent-foreground";

export const menuCheckboxItemClass =
  "relative flex cursor-default select-none items-center rounded-sm py-1.5 pl-8 pr-2 text-sm outline-none data-[disabled]:pointer-events-none data-[disabled]:opacity-50 focus:bg-accent focus:text-accent-foreground";

export const menuRadioItemClass = menuCheckboxItemClass;

export const menuLabelBaseClass = "px-2 py-1.5 text-sm font-semibold";

export const menuSubContentBaseClass =
  "z-50 min-w-[8rem] overflow-hidden rounded-md border bg-popover p-1 text-popover-foreground data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[side=bottom]:slide-in-from-top-2 data-[side=left]:slide-in-from-right-2 data-[side=right]:slide-in-from-left-2 data-[side=top]:slide-in-from-bottom-2";

export const menuShortcutClass = "ml-auto text-xs tracking-widest text-muted-foreground";
export const menuShortcutDimClass = "ml-auto text-xs tracking-widest opacity-60";

export const menuItemIndicatorClass = "absolute left-2 flex h-3.5 w-3.5 items-center justify-center";

export const menuChevronClass = "ml-auto h-4 w-4";

export const menuSeparatorBaseClass = "-mx-1 my-1 h-px";

export const defaultVariantOptions = {
  variant: "default",
  size: "default",
} as const;

export const defaultVariantOnlyOptions = {
  variant: "default",
} as const;

export const modalContentClass =
  "fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95 data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%] data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%] sm:rounded-lg";

export const modalHeaderClass = "flex flex-col space-y-2 text-center sm:text-left";

export const modalFooterClass = "flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2";

export const modalDescriptionClass = "text-sm text-muted-foreground";
