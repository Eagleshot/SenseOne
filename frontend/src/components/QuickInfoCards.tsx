import { useStationData } from '@/contexts/AppContext';
import { cn } from '@/lib/utils';
import {
  STATUS_METRIC_KEYS,
  formatMetricValue,
  metricIcon,
  metricLabel,
  statusLevelForValue,
  type StatusLevel,
} from '@/lib/metricCatalog';

const levelTextClass = (level: StatusLevel) =>
  level === 'success' ? 'text-success' : level === 'warning' ? 'text-warning' : 'text-destructive';

export const QuickInfoCards: React.FC = () => {
  const { activeWebcam, historicalData } = useStationData();

  const latestReading = historicalData[historicalData.length - 1];
  const readingValue = (key: string): number | null => {
    const value = latestReading?.[key];
    return typeof value === 'number' ? value : null;
  };

  // Battery may also arrive on the station summary, so fall back to that.
  const cards = STATUS_METRIC_KEYS.map((key) => {
    const value =
      key === 'battery'
        ? readingValue('battery') ??
          (typeof activeWebcam.battery === 'number' ? activeWebcam.battery : null)
        : readingValue(key);
    return { key, value };
  }).filter((card): card is { key: string; value: number } => card.value !== null);

  if (cards.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-6">
      {cards.map(({ key, value }) => {
        const Icon = metricIcon(key);
        const level = statusLevelForValue(value);
        return (
          <div key={key} className="flex items-center gap-2 text-sm text-foreground">
            <Icon className={cn('w-4 h-4', levelTextClass(level))} />
            <span className="text-muted-foreground">{metricLabel(key)}</span>
            <span className={cn('font-semibold', levelTextClass(level))}>
              {formatMetricValue(key, value)}
            </span>
          </div>
        );
      })}
    </div>
  );
};
