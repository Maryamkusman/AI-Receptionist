"use client";

import { useMemo, useState } from "react";
import { money } from "@/lib/format";

function niceMax(v: number) {
  if (v <= 4) return 4;
  const pow = Math.pow(10, Math.floor(Math.log10(v)));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * pow).find((s) => (v / s) <= 4) || pow * 10;
  return Math.ceil(v / step) * step;
}

/** Single-series column chart with per-column hover tooltip. */
export function ColumnChart({
  data,
  color = "var(--color-series-1)",
  label,
}: {
  data: { date: string; value: number; sub?: string }[];
  color?: string;
  label: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const max = useMemo(() => niceMax(Math.max(1, ...data.map((d) => d.value))), [data]);
  const ticks = [0, max / 2, max];
  const labelEvery = Math.ceil(data.length / 7);

  return (
    <div className="relative select-none" role="img" aria-label={label}>
      <div className="relative h-64">
        {/* gridlines + y ticks */}
        {ticks.map((t) => (
          <div key={t} className="absolute right-0 left-8 border-t border-line" style={{ bottom: `${(t / max) * 100}%` }}>
            <span className="absolute -top-2 -left-8 w-6 text-right text-[11px] text-muted tabular-nums">{t}</span>
          </div>
        ))}
        <div className="absolute inset-y-0 right-0 left-8 flex items-end gap-[2px]">
          {data.map((d, i) => {
            const h = (d.value / max) * 100;
            return (
              <div
                key={d.date}
                className="relative flex h-full min-w-0 flex-1 cursor-default items-end justify-center"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              >
                {hover === i && <div className="absolute inset-y-0 w-full rounded-md bg-ink/[0.04]" />}
                <div
                  className="relative w-full max-w-6 rounded-t-[4px] transition-opacity"
                  style={{ height: `${h}%`, background: color, opacity: hover === null || hover === i ? 1 : 0.45, minHeight: d.value ? 3 : 0 }}
                />
                {hover === i && (
                  <div
                    className="pointer-events-none absolute z-10 w-max -translate-x-1/2 rounded-xl bg-ink px-3 py-2 text-xs text-white shadow-[var(--shadow-pop)]"
                    style={{ bottom: `calc(${Math.max(h, 8)}% + 10px)`, left: "50%" }}
                  >
                    <p className="text-white/60">
                      {new Date(d.date + "T12:00").toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" })}
                    </p>
                    <p className="mt-0.5 font-semibold">
                      {d.value} booking{d.value === 1 ? "" : "s"}
                      {d.sub && <span className="font-normal text-white/70"> · {d.sub}</span>}
                    </p>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
      {/* x labels */}
      <div className="mt-2 ml-8 flex gap-[2px]">
        {data.map((d, i) => (
          <div key={d.date} className="min-w-0 flex-1 overflow-visible text-center text-[11px] whitespace-nowrap text-muted">
            {i % labelEvery === 0 ? new Date(d.date + "T12:00").toLocaleDateString("en-US", { month: "short", day: "numeric" }) : ""}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Part-to-whole bar with a legend row per segment. */
export function SplitBar({
  parts,
}: {
  parts: { key: string; label: string; color: string; value: number; count: number }[];
}) {
  const [hover, setHover] = useState<string | null>(null);
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  return (
    <div>
      <div className="flex h-3 w-full gap-[2px] overflow-hidden rounded-full">
        {parts.map((p) =>
          p.value > 0 ? (
            <div
              key={p.key}
              title={`${p.label}: ${money(p.value)}`}
              onMouseEnter={() => setHover(p.key)}
              onMouseLeave={() => setHover(null)}
              className="h-full transition-opacity"
              style={{ width: `${(p.value / total) * 100}%`, background: p.color, opacity: hover && hover !== p.key ? 0.4 : 1 }}
            />
          ) : null,
        )}
      </div>
      <ul className="mt-4 space-y-2.5">
        {parts.map((p) => (
          <li
            key={p.key}
            onMouseEnter={() => setHover(p.key)}
            onMouseLeave={() => setHover(null)}
            className="flex items-center gap-3 text-sm"
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: p.color }} />
            <span className="min-w-0 flex-1 truncate text-ink-2">{p.label}</span>
            <span className="text-muted tabular-nums" title={`${p.count} appointments`}>
              {p.count}
            </span>
            <span className="w-20 text-right font-medium text-ink tabular-nums">{money(p.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
