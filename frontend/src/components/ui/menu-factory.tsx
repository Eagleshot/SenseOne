import * as React from "react";

import {
  menuCheckboxItemClass,
  menuChevronClass,
  menuItemClass,
  menuItemIndicatorClass,
  menuLabelBaseClass,
  menuRadioItemClass,
  menuSeparatorBaseClass,
  menuSubContentBaseClass,
  menuSubTriggerBaseClass,
} from "@/components/ui/shared-classes";

import { cn } from "@/lib/utils";

type IconComponent = React.ComponentType<{ className?: string }>;
type MenuPrimitiveProps = React.PropsWithChildren<{
  className?: string;
  inset?: boolean;
}> &
  Record<string, unknown>;
type MenuPrimitiveComponent = React.ComponentType<
  MenuPrimitiveProps & React.RefAttributes<HTMLElement>
>;
type MenuIndicatorComponent = React.ComponentType<React.PropsWithChildren>;

function createMenuIndicatorItem(
  Comp: MenuPrimitiveComponent,
  ItemIndicator: MenuIndicatorComponent,
  displayName: string,
  baseClassName: string,
  options: {
    Icon: IconComponent;
    iconClassName: string;
    extraClassName?: string;
  },
) {
  const { Icon, iconClassName, extraClassName } = options;
  const Component = React.forwardRef<HTMLElement, MenuPrimitiveProps>(
    ({ className, children, ...props }, ref) => (
      <Comp ref={ref} className={cn(baseClassName, extraClassName, className)} {...props}>
        <span className={menuItemIndicatorClass}>
          <ItemIndicator>
            <Icon className={iconClassName} />
          </ItemIndicator>
        </span>
        {children}
      </Comp>
    ),
  );
  Component.displayName = displayName;
  return Component;
}

export function createMenuSubTrigger(
  Comp: MenuPrimitiveComponent,
  displayName: string,
  options: {
    activeClassName: string;
    ChevronIcon: IconComponent;
    extraClassName?: string;
  },
) {
  const { activeClassName, ChevronIcon, extraClassName } = options;
  const Component = React.forwardRef<HTMLElement, MenuPrimitiveProps>(
    ({ className, inset, children, ...props }, ref) => (
      <Comp
        ref={ref}
        className={cn(menuSubTriggerBaseClass, activeClassName, extraClassName, inset && "pl-8", className)}
        {...props}
      >
        {children}
        <ChevronIcon className={menuChevronClass} />
      </Comp>
    ),
  );
  Component.displayName = displayName;
  return Component;
}

export function createMenuSubContent(
  Comp: MenuPrimitiveComponent,
  displayName: string,
  extraClassName?: string,
) {
  const Component = React.forwardRef<HTMLElement, MenuPrimitiveProps>(
    ({ className, ...props }, ref) => (
      <Comp ref={ref} className={cn(menuSubContentBaseClass, extraClassName, className)} {...props} />
    ),
  );
  Component.displayName = displayName;
  return Component;
}

export function createMenuItem(
  Comp: MenuPrimitiveComponent,
  displayName: string,
  extraClassName?: string,
) {
  const Component = React.forwardRef<HTMLElement, MenuPrimitiveProps>(
    ({ className, inset, ...props }, ref) => (
      <Comp
        ref={ref}
        className={cn(menuItemClass, extraClassName, inset && "pl-8", className)}
        {...props}
      />
    ),
  );
  Component.displayName = displayName;
  return Component;
}

export function createMenuCheckboxItem(
  Comp: MenuPrimitiveComponent,
  ItemIndicator: MenuIndicatorComponent,
  displayName: string,
  options: {
    Icon: IconComponent;
    iconClassName: string;
    extraClassName?: string;
  },
) {
  return createMenuIndicatorItem(Comp, ItemIndicator, displayName, menuCheckboxItemClass, options);
}

export function createMenuRadioItem(
  Comp: MenuPrimitiveComponent,
  ItemIndicator: MenuIndicatorComponent,
  displayName: string,
  options: {
    Icon: IconComponent;
    iconClassName: string;
    extraClassName?: string;
  },
) {
  return createMenuIndicatorItem(Comp, ItemIndicator, displayName, menuRadioItemClass, options);
}

export function createMenuLabel(
  Comp: MenuPrimitiveComponent,
  displayName: string,
  extraClassName?: string,
) {
  const Component = React.forwardRef<HTMLElement, MenuPrimitiveProps>(
    ({ className, inset, ...props }, ref) => (
      <Comp ref={ref} className={cn(menuLabelBaseClass, extraClassName, inset && "pl-8", className)} {...props} />
    ),
  );
  Component.displayName = displayName;
  return Component;
}

export function createMenuSeparator(
  Comp: MenuPrimitiveComponent,
  displayName: string,
  toneClassName: string,
) {
  const Component = React.forwardRef<HTMLElement, MenuPrimitiveProps>(
    ({ className, ...props }, ref) => (
      <Comp ref={ref} className={cn(menuSeparatorBaseClass, toneClassName, className)} {...props} />
    ),
  );
  Component.displayName = displayName;
  return Component;
}

export function createMenuShortcut(displayName: string, shortcutClassName: string) {
  const Component = ({ className, ...props }: React.HTMLAttributes<HTMLSpanElement>) => (
    <span className={cn(shortcutClassName, className)} {...props} />
  );
  Component.displayName = displayName;
  return Component;
}
