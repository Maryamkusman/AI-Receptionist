"use client";

import clsx from "clsx";
import { ArrowDownRight, ArrowRight, ArrowUpRight, CalendarDays, Hand, MessageCircle, RefreshCw, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ColumnChart, SplitBar } from "@/components/charts";
import { Avatar, Badge, Card, CardHeader, ChannelIcon, CHANNEL_LABEL, Empty, ErrorNote, PageHeader, Segmented, Skeleton } from "@/components/ui";
import { useApi, type Channel, type Kpi, type Overview, type Status } from "@/lib/api";
import { ago, firstName, money, num, pctChange, timeOf } from "@/lib/format";

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function Delta({ kpi }: { kpi: Kpi }) {
  const pct = pctChange(kpi.value, kpi.prev);
  if (pct === null) return <span className="text-xs text-muted">new this period</span>;
  const up = pct >= 0;
  return (
    <span className={clsx("inline-flex items-center gap-0.5 text-xs font-medium", up ? "text-sage" : "text-danger")}>
      {up ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
      {Math.abs(pct)}% <span className="font-normal text-muted">vs previous</span>
    </span>
  );
}

function StatTile({ label, value, kpi, icon }: { label: string; value: string; kpi: Kpi; icon: React.ReactNode }) {
  return (
    <Card className="p-5">
      <div className="flex items-center justify-between">
        <p className="text-[13px] font-medium text-muted">{label}</p>
        <span className="text-muted">{icon}</span>
      </div>
      <p className="mt-3 font-serif text-[32px] leading-none font-medium tracking-tight text-ink tabular-nums">{value}</p>
      <div className="mt-2.5">
        <Delta kpi={kpi} />
      </div>
    </Card>
  );
}

export default function OverviewPage() {
  const [days, setDays] = useState<"7" | "30" | "90">("30");
  const { data, error } = useApi<Overview>(`/api/overview?days=${days}`, 30000);
  const { data: status } = useApi<Status>("/api/status");

  if (error) return <ErrorNote message={error} />;

  const k = data?.kpis;
  return (
    <div className="animate-fade-up">
      <PageHeader
        title={`${greeting()} ✨`}
        subtitle={status ? `Here's how ${status.salon.name}'s front desk is doing.` : " "}
        action={
          <Segmented
            value={days}
            onChange={setDays}
            options={[
              { value: "7", label: "7 days" },
              { value: "30", label: "30 days" },
              { value: "90", label: "90 days" },
            ]}
          />
        }
      />

      {/* Hero */}
      <Card className="relative mb-6 overflow-hidden p-6 sm:p-8">
        <div className="pointer-events-none absolute -top-24 -right-24 h-72 w-72 rounded-full bg-rose-soft blur-3xl" />
        <div className="pointer-events-none absolute -bottom-32 left-1/3 h-64 w-64 rounded-full bg-amber-soft/70 blur-3xl" />
        <div className="relative flex flex-wrap items-end justify-between gap-6">
          <div>
            <p className="text-sm font-medium text-ink-2">Revenue recovered by FullChair · last {days} days</p>
            {data ? (
              <p className="mt-2 font-serif text-[52px] leading-none font-medium tracking-[-0.02em] text-ink sm:text-[64px] tabular-nums">
                {money(data.kpis.revenue_recovered.value)}
              </p>
            ) : (
              <Skeleton className="mt-3 h-14 w-64" />
            )}
            <p className="mt-3 max-w-lg text-[15px] text-ink-2">
              {data && (
                <>
                  {num(data.kpis.ai_bookings.value)} appointments your team didn&apos;t have to book
                  {data.roi.multiple ? (
                    <>
                      {" "}— that&apos;s <span className="font-semibold text-ink">{data.roi.multiple}×</span> the cost of your {data.roi.plan} plan.
                    </>
                  ) : (
                    "."
                  )}
                </>
              )}
            </p>
          </div>
          {data && (
            <div className="flex gap-6 rounded-2xl bg-surface/80 px-5 py-4 ring-1 ring-line backdrop-blur">
              <div>
                <p className="text-xs text-muted">After-hours chats</p>
                <p className="mt-1 text-xl font-semibold text-ink tabular-nums">{Math.round(data.after_hours_share * 100)}%</p>
              </div>
              <div className="w-px bg-line" />
              <div>
                <p className="text-xs text-muted">Plan cost</p>
                <p className="mt-1 text-xl font-semibold text-ink tabular-nums">{money(data.roi.plan_cost)}</p>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* KPI tiles */}
      <div className="mb-6 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {k ? (
          <>
            <StatTile label="Conversations handled" value={num(k.conversations.value)} kpi={k.conversations} icon={<MessageCircle size={17} />} />
            <StatTile label="Booked by AI" value={num(k.ai_bookings.value)} kpi={k.ai_bookings} icon={<CalendarDays size={17} />} />
            <StatTile label="Cancellations refilled" value={num(k.slots_refilled.value)} kpi={k.slots_refilled} icon={<RefreshCw size={17} />} />
            <StatTile label="Revenue recovered" value={money(k.revenue_recovered.value)} kpi={k.revenue_recovered} icon={<Sparkles size={17} />} />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[134px]" />)
        )}
      </div>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Chart */}
        <Card className="xl:col-span-2">
          <CardHeader title="Appointments booked by FullChair" subtitle="Per day — hover a column for details" />
          <div className="px-5 pt-2 pb-5">
            {data ? (
              <ColumnChart
                label="Appointments booked by FullChair per day"
                data={data.daily.map((d) => ({ date: d.date, value: d.bookings, sub: money(d.revenue) }))}
              />
            ) : (
              <Skeleton className="h-56" />
            )}
          </div>
        </Card>

        {/* Where it came from */}
        <Card>
          <CardHeader title="Where it came from" subtitle="Revenue by what FullChair did" />
          <div className="px-5 pb-5">
            {data ? (
              <SplitBar
                parts={[
                  { key: "ai", label: "Answered & booked", color: "var(--color-series-1)", value: data.by_source.ai.revenue, count: data.by_source.ai.count },
                  { key: "refill", label: "Cancellation refills", color: "var(--color-series-2)", value: data.by_source.refill.revenue, count: data.by_source.refill.count },
                  { key: "nudge", label: "Rebooking nudges", color: "var(--color-series-3)", value: data.by_source.nudge.revenue, count: data.by_source.nudge.count },
                ]}
              />
            ) : (
              <Skeleton className="h-32" />
            )}
            {data && (
              <div className="mt-6 border-t border-line pt-4">
                <p className="mb-3 text-[13px] font-medium text-muted">Conversations by channel</p>
                <div className="grid grid-cols-2 gap-2">
                  {(["sms", "instagram", "voice", "web"] as Channel[]).map((c) => (
                    <div key={c} className="flex items-center gap-2 rounded-xl bg-canvas px-3 py-2">
                      <ChannelIcon channel={c} size={14} className="text-muted" />
                      <span className="flex-1 text-[13px] text-ink-2">{CHANNEL_LABEL[c]}</span>
                      <span className="text-sm font-semibold text-ink tabular-nums">{data.channels[c] || 0}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </Card>

        {/* Needs you */}
        <Card className="xl:col-span-1">
          <CardHeader
            title={
              <span className="flex items-center gap-2">
                Needs you {data && data.handoffs.length > 0 && <Badge tone="rose">{data.handoffs.length}</Badge>}
              </span>
            }
            subtitle="Conversations handed to your team"
          />
          <div className="px-3 pb-3">
            {data?.handoffs.length === 0 && <Empty icon={<Hand size={20} />} title="All clear" body="FullChair is handling everything right now." />}
            {data?.handoffs.map((h) => (
              <Link key={h.id} href={`/inbox?c=${h.id}`} className="group block rounded-xl p-3 transition-colors hover:bg-canvas">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-ink">{h.client}</span>
                  <ChannelIcon channel={h.channel} size={13} className="text-muted" />
                  <span className="ml-auto text-xs text-muted">{ago(h.at)}</span>
                </div>
                <p className="mt-1 line-clamp-2 text-[13px] leading-relaxed text-ink-2">{h.summary}</p>
              </Link>
            ))}
          </div>
        </Card>

        {/* Today */}
        <Card className="xl:col-span-2">
          <CardHeader
            title="Still to come today"
            subtitle="Upcoming appointments"
            action={
              <Link href="/calendar" className="inline-flex items-center gap-1 text-[13px] font-medium text-rose hover:underline">
                Calendar <ArrowRight size={14} />
              </Link>
            }
          />
          <div className="px-3 pb-3">
            {data?.today.length === 0 && <Empty icon={<CalendarDays size={20} />} title="Nothing else today" body="Enjoy the quiet — or check tomorrow in the calendar." />}
            <ul className="divide-y divide-line">
              {data?.today.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-2 py-3">
                  <span className="w-16 shrink-0 text-sm font-semibold text-ink tabular-nums">{timeOf(a.start)}</span>
                  <span className="h-8 w-1 shrink-0 rounded-full" style={{ background: a.color }} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{a.client}</p>
                    <p className="truncate text-[13px] text-muted">
                      {a.service} · {firstName(a.stylist)}
                    </p>
                  </div>
                  {a.booked_by_ai && (
                    <Badge tone="rose">
                      <Sparkles size={11} /> AI booked
                    </Badge>
                  )}
                  <Avatar name={a.stylist} color={a.color} size={28} />
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
