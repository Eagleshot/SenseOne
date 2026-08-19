import { useMemo, useState } from "react";

import { Check, ChevronDown } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { TimezoneOption } from "@/data/types";
import { cn } from "@/lib/utils";

type TimezonePickerProps = {
  value: string;
  options: TimezoneOption[];
  onChange: (timezone: string) => void;
  triggerClassName?: string;
};

/** Searchable timezone selector — a plain dropdown is unusable with the full
 * ~400-entry IANA list. */
export const TimezonePicker: React.FC<TimezonePickerProps> = ({
  value,
  options,
  onChange,
  triggerClassName,
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return options;
    return options.filter(
      (option) =>
        option.label.toLowerCase().includes(normalized) ||
        option.value.toLowerCase().includes(normalized),
    );
  }, [options, query]);

  const selectedLabel = options.find((option) => option.value === value)?.label ?? value;

  const handleOpenChange = (nextOpen: boolean) => {
    setOpen(nextOpen);
    if (!nextOpen) setQuery("");
  };

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="outline"
          role="combobox"
          aria-expanded={open}
          aria-label="Timezone"
          className={cn("w-full justify-between font-normal", triggerClassName)}
        >
          <span className="truncate">{selectedLabel}</span>
          <ChevronDown className="h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[260px] p-0" align="start">
        <div className="border-b border-border p-2">
          <Input
            autoFocus
            placeholder="Search timezones..."
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            className="h-8 text-sm"
          />
        </div>
        <ScrollArea className="h-64">
          <div className="p-1">
            {filtered.length === 0 ? (
              <p className="p-3 text-center text-xs text-muted-foreground">No timezones found.</p>
            ) : (
              filtered.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  onClick={() => {
                    onChange(option.value);
                    handleOpenChange(false);
                  }}
                  className={cn(
                    "flex w-full items-center justify-between gap-2 rounded-md px-2 py-1.5 text-left text-sm text-popover-foreground transition-colors hover:bg-primary/10 hover:text-popover-foreground",
                    option.value === value && "bg-primary/15 hover:bg-primary/20",
                  )}
                >
                  <span className="truncate">{option.label}</span>
                  {option.value === value && <Check className="h-4 w-4 shrink-0 text-primary" />}
                </button>
              ))
            )}
          </div>
        </ScrollArea>
      </PopoverContent>
    </Popover>
  );
};
