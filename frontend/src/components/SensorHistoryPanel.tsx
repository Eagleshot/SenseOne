import React, { useMemo, useState } from "react";

import { motion } from "framer-motion";
import { Calendar, LineChart, Plus } from "lucide-react";
import { endOfDay, format, startOfDay } from "date-fns";
import type { DateRange } from "react-day-picker";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Calendar as CalendarComponent } from "@/components/ui/calendar";

import { useApp } from "@/contexts/AppContext";
import { HistoricalCharts } from "./HistoricalCharts";
import { RawDataTable } from "./RawDataTable";

export const SensorHistoryPanel: React.FC = () => {
  const { historicalData } = useApp();
  const [dateRange, setDateRange] = useState<DateRange | undefined>({
    from: new Date(Date.now() - 24 * 60 * 60 * 1000),
    to: new Date(),
  });
  const [timeFrom, setTimeFrom] = useState("00:00");
  const [timeTo, setTimeTo] = useState("23:59");
  const [addChartSignal, setAddChartSignal] = useState(0);

  const parseTime = (value: string) => {
    const [hours, minutes] = value.split(":").map(Number);
    if (Number.isNaN(hours) || Number.isNaN(minutes)) return undefined;
    return hours * 60 + minutes;
  };

  const filteredData = useMemo(() => {
    const from = dateRange?.from ? startOfDay(dateRange.from) : undefined;
    const to = dateRange?.to ? endOfDay(dateRange.to) : undefined;
    const fromMinutes = parseTime(timeFrom);
    const toMinutes = parseTime(timeTo);

    return historicalData.filter((row) => {
      const timestamp = row.timestamp;
      if (from && timestamp < from) return false;
      if (to && timestamp > to) return false;

      if (fromMinutes !== undefined || toMinutes !== undefined) {
        const currentMinutes = timestamp.getHours() * 60 + timestamp.getMinutes();

        if (fromMinutes !== undefined && toMinutes !== undefined) {
          if (fromMinutes <= toMinutes) {
            if (currentMinutes < fromMinutes || currentMinutes > toMinutes) return false;
          } else if (currentMinutes < fromMinutes && currentMinutes > toMinutes) {
            return false;
          }
        } else if (fromMinutes !== undefined && currentMinutes < fromMinutes) {
          return false;
        } else if (toMinutes !== undefined && currentMinutes > toMinutes) {
          return false;
        }
      }

      return true;
    });
  }, [historicalData, dateRange, timeFrom, timeTo]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25 }}
      className="panel-shell"
    >
      <div className="p-4 sm:p-6">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-2">
            <LineChart className="h-5 w-5 text-muted-foreground" />
            <h2 className="text-2xl font-bold text-foreground">Sensor Data</h2>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setAddChartSignal((value) => value + 1)}
              className="btn-panel"
            >
              <Plus className="w-4 h-4" />
              Add Chart
            </Button>
            <Popover>
              <PopoverTrigger asChild>
                <Button
                  variant="outline"
                  size="sm"
                  className="btn-panel"
                >
                  <Calendar className="w-4 h-4" />
                  {dateRange?.from && dateRange?.to
                    ? `${format(dateRange.from, "MMM d")} - ${format(dateRange.to, "MMM d")}`
                    : "Select range"}
                </Button>
              </PopoverTrigger>
              <PopoverContent className="w-auto p-0" align="end">
                <div className="space-y-3 p-3 pointer-events-auto">
                  <CalendarComponent
                    initialFocus
                    mode="range"
                    defaultMonth={dateRange?.from}
                    selected={dateRange}
                    onSelect={setDateRange}
                    numberOfMonths={1}
                  />
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="text-xs text-muted-foreground">Time</span>
                    <Input
                      type="time"
                      value={timeFrom}
                      onChange={(event) => setTimeFrom(event.target.value)}
                      className="h-9 w-full sm:w-[120px]"
                    />
                    <span className="text-xs text-muted-foreground">to</span>
                    <Input
                      type="time"
                      value={timeTo}
                      onChange={(event) => setTimeTo(event.target.value)}
                      className="h-9 w-full sm:w-[120px]"
                    />
                  </div>
                </div>
              </PopoverContent>
            </Popover>
          </div>
        </div>
      </div>

      <div className="space-y-6 p-4 sm:p-6">
        <HistoricalCharts data={filteredData} addChartSignal={addChartSignal} />
        <RawDataTable data={filteredData} />
      </div>
    </motion.div>
  );
};

