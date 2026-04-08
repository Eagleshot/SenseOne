import { Battery, Signal } from 'lucide-react';

import { useApp } from '@/contexts/useApp';
import { LOADING_LABEL, UNAVAILABLE_LABEL } from '@/lib/placeholders';
import { cn } from '@/lib/utils';

export const QuickInfoCards: React.FC = () => {
  const { activeWebcam, historicalData } = useApp();

  const getBatteryStatus = (battery: number | null): 'success' | 'warning' | 'error' | 'neutral' => {
    if (battery === null) return 'neutral';
    if (battery >= 60) return 'success';
    if (battery >= 30) return 'warning';
    return 'error';
  };

  const latestReading = historicalData[historicalData.length - 1];
  const historyBattery = latestReading?.battery;
  const batteryLevel =
    typeof activeWebcam.battery === 'number'
      ? activeWebcam.battery
      : typeof historyBattery === 'number'
        ? historyBattery
        : null;
  const batteryStatus = getBatteryStatus(batteryLevel);
  const isStationKnown = Boolean(activeWebcam.id);
  const pendingLabel = isStationKnown ? LOADING_LABEL : UNAVAILABLE_LABEL;

  const signalStrength =
    typeof activeWebcam.isOnline !== 'boolean' ? pendingLabel : activeWebcam.isOnline ? 'Strong' : 'No signal';
  const signalStatus =
    typeof activeWebcam.isOnline !== 'boolean' ? 'neutral' : activeWebcam.isOnline ? 'success' : 'error';
  const batteryLabel =
    typeof batteryLevel === 'number'
      ? `${batteryLevel}%`
      : !isStationKnown
        ? UNAVAILABLE_LABEL
        : activeWebcam.battery === null
          ? UNAVAILABLE_LABEL
          : pendingLabel;

  const batteryClass = cn(
    'font-semibold',
    batteryStatus === 'success' && 'text-success',
    batteryStatus === 'warning' && 'text-warning',
    batteryStatus === 'error' && 'text-destructive',
    batteryStatus === 'neutral' && 'text-muted-foreground'
  );

  const signalClass = cn(
    'font-semibold',
    signalStatus === 'success' ? 'text-success' : signalStatus === 'error' ? 'text-destructive' : 'text-muted-foreground'
  );

  return (
    <div className="flex flex-wrap items-center gap-6">
      <div className="flex items-center gap-2 text-sm text-foreground">
        <Battery
          className={cn(
            'w-4 h-4',
            batteryStatus === 'success' && 'text-success',
            batteryStatus === 'warning' && 'text-warning',
            batteryStatus === 'error' && 'text-destructive',
            batteryStatus === 'neutral' && 'text-muted-foreground'
          )}
        />
        <span className="text-muted-foreground">Battery</span>
        <span className={batteryClass}>{batteryLabel}</span>
      </div>
      <div className="flex items-center gap-2 text-sm text-foreground">
        <Signal
          className={cn(
            'w-4 h-4',
            signalStatus === 'success'
              ? 'text-success'
              : signalStatus === 'error'
                ? 'text-destructive'
                : 'text-muted-foreground'
          )}
        />
        <span className="text-muted-foreground">Signal</span>
        <span className={signalClass}>{signalStrength}</span>
      </div>
    </div>
  );
};
