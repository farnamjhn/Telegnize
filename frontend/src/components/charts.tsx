/** The chart layer.
 *
 * Every chart here plots a single series, so each one is one hue (no legend —
 * the card title names what is plotted) with the value carried by length.
 * The only categorical chart is the language split, which caps at three hues
 * plus "Other". Marks follow the house specs: bars ≤24px with a 4px rounded
 * data-end square at the baseline, 2px lines, ≥8px end markers ringed in the
 * surface color, solid hairline grid. Every chart has a table-view twin in
 * its card, so no value is reachable only through a tooltip.
 */

import { useState } from "react";

import { int } from "../lib/format";
import { useMeasure } from "../lib/useMeasure";

const SURFACE = "var(--surface-1)";

export interface Point {
  key: string;
  label: string;
  value: number;
}

/** Axis ticks rounded to clean numbers (0 / 500 / 1,000). */
function niceTicks(max: number, count = 4): number[] {
  if (max <= 0) return [0];
  const raw = max / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const step =
    [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw) ??
    magnitude * 10;
  const ticks: number[] = [];
  for (let value = 0; ; value += step) {
    ticks.push(value);
    if (value >= max) return ticks;
  }
}

/** A bar whose data-end is rounded and whose baseline end stays square. */
function capPath(
  x: number,
  y: number,
  width: number,
  height: number,
  radius = 4,
): string {
  const r = Math.min(radius, width / 2, height);
  return [
    `M${x} ${y + height}`,
    `V${y + r}`,
    `a${r} ${r} 0 0 1 ${r} ${-r}`,
    `h${width - 2 * r}`,
    `a${r} ${r} 0 0 1 ${r} ${r}`,
    `V${y + height}`,
    "Z",
  ].join(" ");
}

function Tooltip({
  x,
  y,
  title,
  value,
  unit,
}: {
  x: number;
  y: number;
  title: string;
  value: string;
  unit?: string;
}) {
  return (
    <div className="tooltip" style={{ left: x, top: y }}>
      <div className="tooltip-title">{title}</div>
      <div className="tooltip-row">
        <span className="swatch" style={{ background: "var(--series-1)" }} />
        <span className="muted">{unit ?? "Messages"}</span>
        <span className="tooltip-value">{value}</span>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- column chart */

export function ColumnChart({
  data,
  height = 190,
  unit,
  labelEvery = 1,
}: {
  data: Point[];
  height?: number;
  unit?: string;
  labelEvery?: number;
}) {
  const { ref, width } = useMeasure<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  const pad = { top: 18, right: 4, bottom: 22, left: 36 };
  const plotWidth = Math.max(0, width - pad.left - pad.right);
  const plotHeight = height - pad.top - pad.bottom;
  const max = Math.max(1, ...data.map((d) => d.value));
  const ticks = niceTicks(max);
  const scaleMax = ticks[ticks.length - 1] || 1;
  const band = data.length ? plotWidth / data.length : 0;
  const barWidth = Math.max(2, Math.min(24, band * 0.62));
  const peak = data.reduce(
    (best, d, i) => (d.value > data[best].value ? i : best),
    0,
  );

  const yOf = (value: number) =>
    pad.top + plotHeight - (value / scaleMax) * plotHeight;

  return (
    <div className="chart-figure" ref={ref}>
      {width > 0 && (
        <svg
          className="chart"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`${unit ?? "Messages"} by ${data.length} buckets`}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                className="chart-grid"
                x1={pad.left}
                x2={width - pad.right}
                y1={yOf(tick) + 0.5}
                y2={yOf(tick) + 0.5}
              />
              <text
                className="chart-tick"
                x={pad.left - 8}
                y={yOf(tick) + 3.5}
                textAnchor="end"
              >
                {int(tick)}
              </text>
            </g>
          ))}

          {data.map((point, i) => {
            const barHeight = (point.value / scaleMax) * plotHeight;
            const x = pad.left + i * band + (band - barWidth) / 2;
            const isActive = active === i;
            return (
              <path
                key={point.key}
                d={capPath(
                  x,
                  pad.top + plotHeight - barHeight,
                  barWidth,
                  Math.max(barHeight, point.value > 0 ? 2 : 0),
                )}
                fill="var(--series-1)"
                opacity={active === null || isActive ? 1 : 0.42}
                style={{ transition: "opacity 120ms" }}
              />
            );
          })}

          {/* Selective direct label: the peak only. */}
          {data.length > 0 && data[peak].value > 0 && active === null && (
            <text
              className="chart-label"
              x={pad.left + peak * band + band / 2}
              y={yOf(data[peak].value) - 7}
              textAnchor="middle"
            >
              {int(data[peak].value)}
            </text>
          )}

          <line
            className="chart-axis"
            x1={pad.left}
            x2={width - pad.right}
            y1={pad.top + plotHeight + 0.5}
            y2={pad.top + plotHeight + 0.5}
          />

          {data.map((point, i) =>
            i % labelEvery === 0 ? (
              <text
                key={point.key}
                className="chart-tick"
                x={pad.left + i * band + band / 2}
                y={height - 6}
                textAnchor="middle"
              >
                {point.label}
              </text>
            ) : null,
          )}

          {/* Hit areas span the whole band, so they are far bigger than the mark. */}
          {data.map((point, i) => (
            <rect
              key={point.key}
              className="chart-hit"
              x={pad.left + i * band}
              y={pad.top}
              width={band}
              height={plotHeight}
              onMouseEnter={() => setActive(i)}
              onMouseLeave={() => setActive(null)}
            />
          ))}
        </svg>
      )}

      {active !== null && data[active] && (
        <Tooltip
          x={pad.left + active * band + band / 2}
          y={yOf(data[active].value)}
          title={data[active].label}
          value={int(data[active].value)}
          unit={unit}
        />
      )}
    </div>
  );
}

/* ------------------------------------------------------------ trend chart */

export interface TrendSeries {
  key: string;
  label: string;
  color: string;
  points: { period: string; value: number; count: number }[];
}

/** A multi-series line chart over shared periods. Used for latency trends,
 *  where the shape of the series is the point and the single drift figure
 *  only says which direction to look in. */
export function TrendChart({
  series,
  height = 210,
  formatValue,
  formatPeriod,
}: {
  series: TrendSeries[];
  height?: number;
  formatValue: (value: number) => string;
  formatPeriod: (period: string) => string;
}) {
  const { ref, width } = useMeasure<HTMLDivElement>();
  const [active, setActive] = useState<number | null>(null);

  // One axis built from every period any series covers, oldest first.
  const periods = [
    ...new Set(series.flatMap((s) => s.points.map((p) => p.period))),
  ].sort();
  const pad = { top: 18, right: 16, bottom: 22, left: 46 };
  const plotWidth = Math.max(0, width - pad.left - pad.right);
  const plotHeight = height - pad.top - pad.bottom;
  const max = Math.max(
    1,
    ...series.flatMap((s) => s.points.map((p) => p.value)),
  );
  const ticks = niceTicks(max);
  const scaleMax = ticks[ticks.length - 1] || 1;
  const last = periods.length - 1;

  const xOf = (i: number) =>
    pad.left + (periods.length < 2 ? plotWidth / 2 : (i / last) * plotWidth);
  const yOf = (value: number) =>
    pad.top + plotHeight - (value / scaleMax) * plotHeight;

  const byPeriod = (s: TrendSeries) =>
    new Map(s.points.map((p) => [p.period, p]));
  const stride = Math.max(1, Math.ceil(periods.length / 6));

  return (
    <div className="chart-figure" ref={ref}>
      {width > 0 && periods.length > 0 && (
        <svg
          className="chart"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          role="img"
          aria-label={`Trend over ${periods.length} periods`}
        >
          {ticks.map((tick) => (
            <g key={tick}>
              <line
                className="chart-grid"
                x1={pad.left}
                x2={width - pad.right}
                y1={yOf(tick) + 0.5}
                y2={yOf(tick) + 0.5}
              />
              <text
                className="chart-tick"
                x={pad.left - 8}
                y={yOf(tick) + 3.5}
                textAnchor="end"
              >
                {formatValue(tick)}
              </text>
            </g>
          ))}

          {series.map((line) => {
            const lookup = byPeriod(line);
            const path = periods
              .map((period, i) => {
                const point = lookup.get(period);
                return point
                  ? `${i === 0 ? "M" : "L"}${xOf(i)} ${yOf(point.value)}`
                  : "";
              })
              .filter(Boolean)
              .join(" ")
              .replace(/^L/, "M");
            const endIndex = periods.findLastIndex((period) =>
              lookup.has(period),
            );
            const endPoint =
              endIndex >= 0 ? lookup.get(periods[endIndex]) : undefined;
            return (
              <g key={line.key}>
                <path
                  d={path}
                  fill="none"
                  stroke={line.color}
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
                {endPoint && (
                  <circle
                    cx={xOf(endIndex)}
                    cy={yOf(endPoint.value)}
                    r="4"
                    fill={line.color}
                    stroke={SURFACE}
                    strokeWidth="2"
                  />
                )}
              </g>
            );
          })}

          <line
            className="chart-axis"
            x1={pad.left}
            x2={width - pad.right}
            y1={pad.top + plotHeight + 0.5}
            y2={pad.top + plotHeight + 0.5}
          />

          {periods.map((period, i) =>
            i % stride === 0 || i === last ? (
              <text
                key={period}
                className="chart-tick"
                x={xOf(i)}
                y={height - 6}
                textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"}
              >
                {formatPeriod(period)}
              </text>
            ) : null,
          )}

          {active !== null && (
            <>
              <line
                className="chart-axis"
                x1={xOf(active)}
                x2={xOf(active)}
                y1={pad.top}
                y2={pad.top + plotHeight}
              />
              {series.map((line) => {
                const point = byPeriod(line).get(periods[active]);
                return point ? (
                  <circle
                    key={line.key}
                    cx={xOf(active)}
                    cy={yOf(point.value)}
                    r="4.5"
                    fill={line.color}
                    stroke={SURFACE}
                    strokeWidth="2"
                  />
                ) : null;
              })}
            </>
          )}

          <rect
            className="chart-hit"
            x={pad.left}
            y={pad.top}
            width={plotWidth}
            height={plotHeight}
            onMouseLeave={() => setActive(null)}
            onMouseMove={(event) => {
              const box = event.currentTarget.getBoundingClientRect();
              const ratio = (event.clientX - box.left) / (box.width || 1);
              setActive(Math.max(0, Math.min(last, Math.round(ratio * last))));
            }}
          />
        </svg>
      )}

      {active !== null && periods[active] && (
        <div className="tooltip" style={{ left: xOf(active), top: pad.top }}>
          <div className="tooltip-title">{formatPeriod(periods[active])}</div>
          {series.map((line) => {
            const point = byPeriod(line).get(periods[active]);
            if (!point) return null;
            return (
              <div key={line.key} className="tooltip-row">
                <span className="swatch" style={{ background: line.color }} />
                <span className="muted">{line.label}</span>
                <span className="tooltip-value">
                  {formatValue(point.value)}
                </span>
              </div>
            );
          })}
          <div className="tooltip-title" style={{ marginTop: 5 }}>
            {series
              .map((line) => byPeriod(line).get(periods[active])?.count ?? 0)
              .reduce((a, b) => a + b, 0)}{" "}
            replies behind these
          </div>
        </div>
      )}

      {/* Two or more series always carry a legend. */}
      <div className="legend">
        {series.map((line) => (
          <span key={line.key} className="legend-item">
            <span className="swatch" style={{ background: line.color }} />
            {line.label}
          </span>
        ))}
      </div>
    </div>
  );
}

/* ---------------------------------------------------- part-to-whole strip */

const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

export interface Slice {
  key: string;
  label: string;
  value: number;
  color: string;
}

/** Keeps the three fixed hues and folds everything past them into "Other" —
 *  a generated fourth hue would be indistinguishable under CVD. */
export function foldToSlices(
  entries: [string, number][],
  name: (key: string) => string,
): Slice[] {
  const sorted = [...entries].sort((a, b) => b[1] - a[1]);
  const head = sorted.slice(0, SERIES.length).map(([key, value], i) => ({
    key,
    label: name(key),
    value,
    color: SERIES[i],
  }));
  const tail = sorted.slice(SERIES.length);
  if (tail.length) {
    head.push({
      key: "__rest",
      // Not "Other": that is a real language tag, and two legend entries
      // reading "Other" tell the reader nothing.
      label: `+${tail.length} more`,
      value: tail.reduce((sum, [, value]) => sum + value, 0),
      color: "var(--series-other)",
    });
  }
  return head;
}

export function ShareStrip({ slices }: { slices: Slice[] }) {
  const total = slices.reduce((sum, slice) => sum + slice.value, 0) || 1;
  const [active, setActive] = useState<string | null>(null);

  return (
    <div>
      <div className="stack">
        {/* A zero-value slice draws nothing — the 3px floor keeps a tiny real
         * value visible, but it would otherwise invent a sliver where there
         * is no data at all. The legend still lists it. */}
        {slices
          .filter((slice) => slice.value > 0)
          .map((slice) => (
            <div
              key={slice.key}
              className="stack-seg"
              style={{
                width: `${(slice.value / total) * 100}%`,
                background: slice.color,
                opacity: active === null || active === slice.key ? 1 : 0.42,
              }}
              onMouseEnter={() => setActive(slice.key)}
              onMouseLeave={() => setActive(null)}
              title={`${slice.label}: ${int(slice.value)}`}
            />
          ))}
      </div>
      {/* Two or more series always carry a legend — identity is never color alone. */}
      <div className="legend">
        {slices.map((slice) => (
          <span key={slice.key} className="legend-item">
            <span className="swatch" style={{ background: slice.color }} />
            {slice.label}
            <span className="legend-value">
              {int(slice.value)} · {((slice.value / total) * 100).toFixed(1)}%
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

/* ------------------------------------------------------- probability bars */

/** Ordered magnitude, one hue, value at the tip of each bar. */
export function ProbabilityBars({
  probabilities,
  winner,
  format,
}: {
  probabilities: Record<string, number>;
  winner?: string;
  format: (key: string) => string;
}) {
  const rows = Object.entries(probabilities).sort((a, b) => b[1] - a[1]);
  if (!rows.length) return null;

  return (
    <div style={{ display: "grid", gap: 8 }}>
      {rows.map(([key, probability]) => {
        const isWinner = key === winner;
        return (
          <div key={key} className="share">
            <span
              style={{
                width: 132,
                fontSize: 12.5,
                color: isWinner
                  ? "var(--text-primary)"
                  : "var(--text-secondary)",
              }}
            >
              {format(key)}
            </span>
            <span className="share-track">
              <span
                className="share-fill"
                style={{
                  width: `${Math.max(probability * 100, 0.8)}%`,
                  background: isWinner ? "var(--series-1)" : "var(--seq-600)",
                }}
              />
            </span>
            <span className="share-value">
              {(probability * 100).toFixed(1)}%
            </span>
          </div>
        );
      })}
    </div>
  );
}
