// A metric key is whatever a device reports (e.g. "temperature", "battery",
// "reception"). It is no longer a fixed union — available metrics are derived
// from the data at runtime and labelled via the metric catalog.
export type MetricType = string;

