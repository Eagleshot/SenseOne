import React from 'react';

import { Battery, Signal } from 'lucide-react';

import { useApp } from '@/contexts/useApp';
import { cn } from '@/lib/utils';

export const QuickInfoCards: React.FC = () => {
  const { activeWebcam, historicalData } = useApp();

  const getBatteryStatus = (battery: number): 'success' | 'warning' | 'error' => {
    if (battery >= 60) return 'success';
    if (battery >= 30) return 'warning';
    return 'error';
  };

  const latestReading = historicalData[historicalData.length - 1];
  const batteryLevel = latestReading?.battery ?? 78;
  const batteryStatus = getBatteryStatus(batteryLevel);

  const signalStrength =
    typeof activeWebcam.isOnline !== 'boolean' ? 'Loading' : activeWebcam.isOnline ? 'Strong' : 'No signal';
  const signalStatus =
    typeof activeWebcam.isOnline !== 'boolean' ? 'neutral' : activeWebcam.isOnline ? 'success' : 'error';

  const batteryClass = cn(
    'font-semibold',
    batteryStatus === 'success' && 'text-success',
    batteryStatus === 'warning' && 'text-warning',
    batteryStatus === 'error' && 'text-destructive'
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
            batteryStatus === 'error' && 'text-destructive'
          )}
        />
        <span className="text-muted-foreground">Battery</span>
        <span className={batteryClass}>{batteryLevel}%</span>
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
