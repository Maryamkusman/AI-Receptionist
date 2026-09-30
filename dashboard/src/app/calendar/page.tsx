"use client";

import clsx from "clsx";
import { ChevronLeft, ChevronRight, CircleDollarSign, RefreshCw, Sparkles, X } from "lucide-react";
import { useMemo, useState } from "react";
import { Avatar, Badge, Button, Card, ErrorNote, PageHeader, Skeleton, Toggle } from "@/components/ui";
import { api, useApi, type Appointment, type Status, type Stylist } from "@/lib/api";
import { money, parseLocal, timeOf } from "@/lib/format";

const START_H = 8;
const END_H = 21;
const HOUR_PX = 64;

const iso = (d: Date) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
const addDays = (d: Date, n: number) => new Date(d.getFullYear(), d.getMonth(), d.getDate() + n);

const SOURCE_LABEL: Record<string, string> = { ai: "Booked by FullChair", refill: "Refilled a cancellation", nudge: "Rebooking nudge", staff: "Booked by staff" };

export default function CalendarPage() {
  const { data: status } = useApi<Status>("/api/status");
  const salonToday = status ? parseLocal(status.now) : new Date();
  const [day, setDay] = useState<Date | null>(null);
  const current = day || new Date(salonToday.getFullYear(), salonToday.getMonth(), salonToday.getDate());
  const weekStart = addDays(current, -((current.getDay() + 6) % 7));

  const { data: stylists } = useApi<Stylist[]>("/api/stylists");
  const { data: week, error, reload } = useApi<Appointment[]>(`/api/appointments?start=${iso(weekStart)}&end=${iso(addDays(weekStart, 6))}`, 15000);
  const [aiOnly, setAiOnly] = useState(false);
  const [open, setOpen] = useState<Appointment | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const dayAppts = useMemo(
    () => (week || []).filter((a) => a.start.startsWith(iso(current)) && a.status !== "cancelled" && (!aiOnly || a.booked_by_ai)),
    [week, current, aiOnly],
  );
  const counts = useMemo(() => {
    const m: Record<string, number> = {};
    (week || []).forEach((a) => a.status !== "cancelled" && (m[a.start.slice(0, 10)] = (m[a.start.slice(0, 10)] || 0) + 1));
    return m;
  }, [week]);

  if (error) return <ErrorNote message={error} />;

  const cancel = async (a: Appointment) => {
    const r = await api<{ refill: { contacted: number } | null }>(`/api/appointments/${a.id}/cancel`, { method: "POST" });
    setOpen(null);
    setToast(
      r.refill && r.refill.contacted
        ? `Cancelled. FullChair texted ${r.refill.contacted} waitlist client${r.refill.contacted === 1 ? "" : "s"} to refill the slot.`
        : "Cancelled. No matching waitlist clients to text right now.",
    );
    setTimeout(() => setToast(null), 6000);
    reload();
  };
  const markPaid = async (a: Appointment) => {
    const updated = await api<Appointment>(`/api/appointments/${a.id}/mark-paid`, { method: "POST" });
    setOpen(updated);
    reload();
  };

  const nowLine = status && iso(current) === iso(salonToday) ? (salonToday.getHours() + salonToday.getMinutes() / 60 - START_H) * HOUR_PX : null;

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Calendar"
        subtitle="Mirrored live from your booking system."
        action={
          <label className="flex items-center gap-2.5 text-sm text-ink-2">
            <Toggle checked={aiOnly} onChange={setAiOnly} label="Only AI bookings" /> Only FullChair bookings
          </label>
        }
      />

      {/* Week strip */}
      <Card className="mb-4 p-2">
        <div className="flex items-center gap-1">
          <button onClick={() => setDay(addDays(current, -7))} className="rounded-xl p-2 text-muted hover:bg-canvas hover:text-ink" aria-label="Previous week">
            <ChevronLeft size={18} />
          </button>
          <div className="grid flex-1 grid-cols-7 gap-1">
            {Array.from({ length: 7 }, (_, i) => addDays(weekStart, i)).map((d) => {
              const active = iso(d) === iso(current);
              const isToday = iso(d) === iso(salonToday);
              return (
                <button
                  key={iso(d)}
                  onClick={() => setDay(d)}
                  className={clsx("flex flex-col items-center rounded-xl py-2 transition-colors", active ? "bg-ink text-white" : "hover:bg-canvas")}
                >
                  <span className={clsx("text-[11px] font-medium uppercase", active ? "text-white/70" : "text-muted")}>
                    {d.toLocaleDateString("en-US", { weekday: "short" })}
                  </span>
                  <span className="text-lg font-semibold tabular-nums">{d.getDate()}</span>
                  <span className={clsx("text-[11px]", active ? "text-white/70" : isToday ? "font-medium text-rose" : "text-muted")}>
                    {isToday ? "Today" : counts[iso(d)] ? `${counts[iso(d)]} appts` : "—"}
                  </span>
                </button>
              );
            })}
          </div>
          <button onClick={() => setDay(addDays(current, 7))} className="rounded-xl p-2 text-muted hover:bg-canvas hover:text-ink" aria-label="Next week">
            <ChevronRight size={18} />
          </button>
        </div>
      </Card>

      {/* Day grid */}
      <Card className="overflow-hidden">
        {!stylists || !week ? (
          <Skeleton className="m-4 h-96" />
        ) : (
          <div className="scroll-thin overflow-x-auto">
            <div className="min-w-[720px]">
              <div className="sticky top-0 z-10 grid border-b border-line bg-surface" style={{ gridTemplateColumns: `56px repeat(${stylists.length}, 1fr)` }}>
                <div />
                {stylists.map((s) => (
                  <div key={s.id} className="flex items-center gap-2 border-l border-line px-3 py-3">
                    <Avatar name={s.name} color={s.color} size={28} />
                    <div className="min-w-0">
                      <p className="truncate text-sm font-semibold text-ink">{s.name.split(" ")[0]}</p>
                      <p className="truncate text-[11px] text-muted">
                        {(() => {
                          const n = dayAppts.filter((a) => a.stylist.id === s.id).length;
                          return `${n} appointment${n === 1 ? "" : "s"}`;
                        })()}
                      </p>
                    </div>
                  </div>
                ))}
              </div>
              <div className="relative grid" style={{ gridTemplateColumns: `56px repeat(${stylists.length}, 1fr)`, height: (END_H - START_H) * HOUR_PX }}>
                <div className="relative">
                  {Array.from({ length: END_H - START_H }, (_, i) => (
                    <span key={i} className="absolute right-2 -translate-y-1/2 text-[11px] text-muted tabular-nums" style={{ top: i * HOUR_PX }}>
                      {i === 0 ? "" : `${((START_H + i - 1) % 12) + 1}${START_H + i < 12 ? "a" : "p"}`}
                    </span>
                  ))}
                </div>
                {stylists.map((s) => (
                  <div key={s.id} className="relative border-l border-line">
                    {Array.from({ length: END_H - START_H }, (_, i) => (
                      <div key={i} className="absolute inset-x-0 border-t border-line/70" style={{ top: i * HOUR_PX }} />
                    ))}
                    {dayAppts
                      .filter((a) => a.stylist.id === s.id)
                      .map((a) => {
                        const st = parseLocal(a.start);
                        const en = parseLocal(a.end);
                        const top = (st.getHours() + st.getMinutes() / 60 - START_H) * HOUR_PX;
                        const h = Math.max(((en.getTime() - st.getTime()) / 3600000) * HOUR_PX - 3, 22);
                        return (
                          <button
                            key={a.id}
                            onClick={() => setOpen(a)}
                            className="absolute inset-x-1.5 overflow-hidden rounded-lg border-l-[3px] px-2 py-1 text-left transition-shadow hover:shadow-[var(--shadow-pop)]"
                            style={{ top: top + 1, height: h, borderColor: a.stylist.color, background: `color-mix(in srgb, ${a.stylist.color} 12%, white)` }}
                          >
                            <div className="flex items-center gap-1">
                              <p className="truncate text-[12px] font-semibold text-ink">{a.client.name}</p>
                              {a.booked_by_ai && <Sparkles size={11} className="shrink-0 text-rose" aria-label="Booked by FullChair" />}
                            </div>
                            {h > 34 && (
                              <p className="truncate text-[11px] text-ink-2">
                                {timeOf(a.start)} · {a.service.name}
                              </p>
                            )}
                            {a.status === "pending_deposit" && h > 50 && <p className="text-[10px] font-medium text-amber">Awaiting deposit</p>}
                          </button>
                        );
                      })}
                  </div>
                ))}
                {nowLine !== null && nowLine > 0 && nowLine < (END_H - START_H) * HOUR_PX && (
                  <div className="pointer-events-none absolute right-0 left-14 z-[5] border-t-2 border-rose" style={{ top: nowLine }}>
                    <span className="absolute -top-[5px] -left-1 h-2 w-2 rounded-full bg-rose" />
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </Card>

      {/* Drawer */}
      {open && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]" onClick={() => setOpen(null)} />
          <div className="animate-fade-up relative flex h-full w-full max-w-md flex-col bg-surface shadow-[var(--shadow-pop)]">
            <div className="flex items-center justify-between border-b border-line px-6 py-4">
              <h2 className="font-serif text-xl">Appointment</h2>
              <button onClick={() => setOpen(null)} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Close">
                <X size={18} />
              </button>
            </div>
            <div className="flex-1 space-y-5 overflow-y-auto p-6">
              <div className="flex items-center gap-3">
                <Avatar name={open.client.name} size={44} />
                <div>
                  <p className="text-lg font-semibold text-ink">{open.client.name}</p>
                  <p className="text-sm text-muted">{open.client.phone}</p>
                </div>
              </div>
              <dl className="grid grid-cols-2 gap-4 rounded-2xl bg-canvas p-4 text-sm">
                <div>
                  <dt className="text-xs text-muted">Service</dt>
                  <dd className="font-medium">{open.service.name}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">With</dt>
                  <dd className="font-medium">{open.stylist.name}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">When</dt>
                  <dd className="font-medium">{open.when}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">Price</dt>
                  <dd className="font-medium">{money(open.price)}</dd>
                </div>
              </dl>
              <div className="flex flex-wrap gap-2">
                <Badge tone={open.booked_by_ai ? "rose" : "neutral"}>
                  {open.booked_by_ai && <Sparkles size={11} />} {SOURCE_LABEL[open.source] || open.source}
                </Badge>
                <Badge tone={open.status === "pending_deposit" ? "amber" : open.status === "cancelled" ? "danger" : "sage"}>{open.status.replace("_", " ")}</Badge>
                {open.deposit_status !== "none" && <Badge tone={open.deposit_status === "paid" ? "sage" : "amber"}>Deposit {open.deposit_status}</Badge>}
              </div>
            </div>
            {open.status !== "cancelled" && open.status !== "completed" && (
              <div className="flex gap-2 border-t border-line p-4">
                {open.deposit_status === "pending" && (
                  <Button variant="secondary" onClick={() => markPaid(open)}>
                    <CircleDollarSign size={15} /> Mark deposit paid
                  </Button>
                )}
                <Button variant="danger" className="ml-auto" onClick={() => cancel(open)}>
                  <RefreshCw size={15} /> Cancel & refill slot
                </Button>
              </div>
            )}
          </div>
        </div>
      )}

      {toast && (
        <div className="animate-fade-up fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 items-center gap-2 rounded-2xl bg-ink px-4 py-3 text-sm text-white shadow-[var(--shadow-pop)]">
          <RefreshCw size={15} /> {toast}
        </div>
      )}
    </div>
  );
}
