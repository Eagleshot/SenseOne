import * as React from "react";

import { ChevronLeft, ChevronRight } from "lucide-react";
import { DayPicker } from "react-day-picker";

import { cn } from "@/lib/utils";

export type CalendarProps = React.ComponentProps<typeof DayPicker>;

const navButtonClasses = cn(
  "inline-flex h-7 w-7 items-center justify-center rounded-md border border-input bg-transparent p-0 text-sm font-medium ring-offset-background transition-colors chrome-shell-stroke",
  "opacity-50 hover:bg-accent hover:text-accent-foreground hover:opacity-100",
);

function Calendar({ className, classNames, showOutsideDays = true, ...props }: CalendarProps) {
  return (
    <DayPicker
      showOutsideDays={showOutsideDays}
      className={cn("p-3", className)}
      classNames={{
        months: "relative flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0",
        month: "space-y-4",
        // The nav is positioned absolutely across the caption row, so pad the
        // caption (px-8) to keep the centered label clear of the arrows.
        month_caption: "flex h-7 items-center justify-center px-8",
        caption_label: "text-sm font-medium",
        nav: "absolute inset-x-0 top-0 flex items-center justify-between px-1",
        button_previous: navButtonClasses,
        button_next: navButtonClasses,
        month_grid: "w-full border-collapse space-y-1",
        weekdays: "flex",
        weekday: "text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]",
        week: "flex w-full mt-2",
        // In react-day-picker v10 the selection state (aria-selected) and the
        // range/selected/today modifier classes are applied to this <td> cell
        // itself, and the clickable element is its direct child <button>. So we
        // fill selected cells via the cell's own aria-selected and round the
        // outer ends of the range (and each row's edges) on the cell.
        day: "relative h-9 w-9 p-0 text-center text-sm focus-within:relative focus-within:z-20 aria-selected:bg-accent first:aria-selected:rounded-l-md last:aria-selected:rounded-r-md",
        day_button:
          "inline-flex h-9 w-9 items-center justify-center rounded-md p-0 text-sm font-normal transition-colors hover:bg-accent hover:text-accent-foreground",
        selected: "",
        range_start: "rounded-l-md [&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:hover:bg-primary",
        range_end: "rounded-r-md [&>button]:bg-primary [&>button]:text-primary-foreground [&>button]:hover:bg-primary",
        range_middle: "aria-selected:text-accent-foreground",
        today: "[&>button]:bg-accent [&>button]:text-accent-foreground",
        outside:
          "text-muted-foreground opacity-50 aria-selected:bg-accent/50 aria-selected:text-muted-foreground",
        disabled: "text-muted-foreground opacity-50",
        hidden: "invisible",
        ...classNames,
      }}
      components={{
        Chevron: ({ orientation }) =>
          orientation === "left" ? (
            <ChevronLeft className="h-4 w-4" />
          ) : (
            <ChevronRight className="h-4 w-4" />
          ),
      }}
      {...props}
    />
  );
}
Calendar.displayName = "Calendar";

export { Calendar };
