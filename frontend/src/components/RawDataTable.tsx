import React, { useEffect, useMemo, useState } from "react";

import { ChevronDown, Download, Search, ArrowUpDown } from "lucide-react";
import { format } from "date-fns";

import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

import { cn } from "@/lib/utils";
import { formatCsvTimestamp, formatDateTimeLabel } from "@/lib/datetime";
import { useApp } from "@/contexts/AppContext";
import type { SensorData } from "@/data/types";

type SortField = "timestamp" | "temperature" | "humidity" | "battery" | "windSpeed" | "pressure";
type SortDirection = "asc" | "desc";

interface RawDataTableProps {
  data: SensorData[];
}

export const RawDataTable: React.FC<RawDataTableProps> = ({ data }) => {
  const { timezone } = useApp();
  const [isOpen, setIsOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [sortField, setSortField] = useState<SortField>("timestamp");
  const [sortDirection, setSortDirection] = useState<SortDirection>("desc");
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const filteredAndSortedData = useMemo(() => {
    let working = [...data];

    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase();
      working = working.filter((d) => {
        const dateStr = formatDateTimeLabel(d.timestamp, timezone).toLowerCase();
        const values = [d.temperature, d.humidity, d.battery, d.windSpeed, d.pressure]
          .map(String)
          .join(" ");
        return dateStr.includes(query) || values.includes(query);
      });
    }

    working.sort((a, b) => {
      let aVal: number | Date = a[sortField];
      let bVal: number | Date = b[sortField];

      if (sortField === "timestamp") {
        aVal = a.timestamp.getTime();
        bVal = b.timestamp.getTime();
      }

      if (sortDirection === "asc") {
        return (aVal as number) - (bVal as number);
      }
      return (bVal as number) - (aVal as number);
    });

    return working;
  }, [data, searchQuery, sortField, sortDirection, timezone]);

  const totalPages = Math.max(1, Math.ceil(filteredAndSortedData.length / itemsPerPage));
  const page = Math.min(currentPage, totalPages);
  const paginatedData = filteredAndSortedData.slice(
    (page - 1) * itemsPerPage,
    page * itemsPerPage
  );

  useEffect(() => {
    if (currentPage > totalPages) {
      setCurrentPage(totalPages);
    }
  }, [currentPage, totalPages]);

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(sortDirection === "asc" ? "desc" : "asc");
    } else {
      setSortField(field);
      setSortDirection("desc");
    }
  };

  const handleDownloadCSV = () => {
    const headers = [
      "Timestamp",
      "Temperature (°C)",
      "Humidity (%)",
      "Battery (%)",
      "Wind (km/h)",
      "Pressure (hPa)",
    ];
    const rows = filteredAndSortedData.map((d) => [
      formatCsvTimestamp(d.timestamp, timezone),
      d.temperature,
      d.humidity,
      d.battery,
      d.windSpeed,
      d.pressure,
    ]);

    const csv = [headers, ...rows].map((row) => row.join(",")).join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `sensor-data-${format(new Date(), "yyyy-MM-dd")}.csv`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  const SortableHeader: React.FC<{ field: SortField; children: React.ReactNode }> = ({
    field,
    children,
  }) => (
    <TableHead>
      <button onClick={() => handleSort(field)} className="flex items-center gap-1 hover:text-foreground transition-colors">
        {children}
        <ArrowUpDown
          className={cn("w-3 h-3", sortField === field ? "text-primary" : "text-muted-foreground")}
        />
      </button>
    </TableHead>
  );

  const startIndex = filteredAndSortedData.length === 0 ? 0 : (page - 1) * itemsPerPage + 1;
  const endIndex = Math.min(page * itemsPerPage, filteredAndSortedData.length);

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen}>
      <CollapsibleTrigger asChild>
        <button
          type="button"
          aria-label={isOpen ? "Collapse raw data" : "Expand raw data"}
          className="w-full flex items-center justify-between pt-4 pb-2 border-t border-foreground/40 dark:border-foreground/30 text-left"
        >
          <span className="text-base font-semibold text-foreground">Raw Data</span>
          <ChevronDown
            className={cn(
              "w-4 h-4 text-muted-foreground transition-transform duration-200",
              isOpen && "rotate-180"
            )}
          />
        </button>
      </CollapsibleTrigger>

      <CollapsibleContent>
        <div className="pt-4 space-y-4">
          <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search data..."
                value={searchQuery}
                onChange={(e) => {
                  setSearchQuery(e.target.value);
                  setCurrentPage(1);
                }}
                className="pl-10 bg-[hsl(var(--sidebar-background))]"
              />
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDownloadCSV}
              className="btn-panel"
            >
              <Download className="w-4 h-4" />
              Download CSV
            </Button>
          </div>
          <div className="border border-foreground/40 dark:border-foreground/30 rounded-lg overflow-hidden bg-[hsl(var(--sidebar-background))]">
            <Table className="[&_th+th]:border-l [&_td+td]:border-l [&_th+th]:border-foreground/40 dark:[&_th+th]:border-foreground/30 [&_td+td]:border-foreground/40 dark:[&_td+td]:border-foreground/30">
              <TableHeader>
                <TableRow className="bg-[hsl(var(--sidebar-background))] dark:bg-muted">
                  <SortableHeader field="timestamp">Timestamp</SortableHeader>
                  <SortableHeader field="temperature">Temp</SortableHeader>
                  <SortableHeader field="humidity">Humidity</SortableHeader>
                  <SortableHeader field="battery">Battery</SortableHeader>
                  <SortableHeader field="windSpeed">Wind</SortableHeader>
                  <SortableHeader field="pressure">Pressure</SortableHeader>
                </TableRow>
              </TableHeader>
              <TableBody className="bg-muted/70 dark:bg-transparent">
                {paginatedData.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center text-sm text-muted-foreground py-8">
                      No data available for the selected range.
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedData.map((row, index) => (
                    <TableRow key={index} className="hover:bg-[hsl(var(--sidebar-background))]">
                      <TableCell className="font-medium">{formatDateTimeLabel(row.timestamp, timezone)}</TableCell>
                      <TableCell>{row.temperature} °C</TableCell>
                      <TableCell>{row.humidity}%</TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            "px-2 py-0.5 rounded-full text-xs font-medium",
                            row.battery >= 60 && "badge-success",
                            row.battery >= 30 && row.battery < 60 && "badge-warning",
                            row.battery < 30 && "badge-error"
                          )}
                        >
                          {row.battery}%
                        </span>
                      </TableCell>
                      <TableCell>{row.windSpeed} km/h</TableCell>
                      <TableCell>{row.pressure} hPa</TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </div>
          <div className="grid items-center gap-3 md:grid-cols-[1fr_auto_1fr]">
            <p className="text-sm text-muted-foreground text-center md:text-left">
              Showing {startIndex} to {endIndex} of {filteredAndSortedData.length} entries
            </p>
            <p className="text-xs text-muted-foreground text-center">
              Raw data reflects the date and time range selected above.
            </p>
            <div className="flex items-center justify-center gap-2 md:justify-end">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                disabled={page === 1}
                className="border-border/70 bg-[hsl(var(--sidebar-background))] text-foreground hover:bg-[hsl(var(--sidebar-accent))]"
              >
                Previous
              </Button>
              <span className="text-sm text-muted-foreground px-2">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                disabled={page === totalPages}
                className="border-border/70 bg-[hsl(var(--sidebar-background))] text-foreground hover:bg-[hsl(var(--sidebar-accent))]"
              >
                Next
              </Button>
            </div>
          </div>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
};

