"use client";

import { BellRing, Check, Clock, Hourglass, RefreshCw, Send, Trash2, Zap } from "lucide-react";
import { useState } from "react";
import { Avatar, Badge, Button, Card, CardHeader, Empty, ErrorNote, PageHeader, Skeleton } from "@/components/ui";
import { api, useApi, type ClientRow, type OutboxRow, type RefillOffer, type Status, type WaitlistRow } from "@/lib/api";
import { ago } from "@/lib/format";

interface Due {
  client: ClientRow;
  last_service: string;
  days_since: number;
  interval: number;
}

const OFFER_TONE = { open: "sky", filled: "sage", expired: "neutral" } as const;
const PURPOSE: Record<string, string> = { refill: "Refill offer", nudge: "Nudge", reply: "Reply", handoff: "Staff alert" };

export default function WaitlistPage() {
  const { data: status } = useApi<Status>("/api/status");
  const { data: waitlist, error, reload: reloadWaitlist } = useApi<WaitlistRow[]>("/api/waitlist", 15000);
  const { data: offers, reload: reloadOffers } = useApi<RefillOffer[]>("/api/refill-offers", 10000);
  const { data: due, reload: reloadDue } = useApi<Due[]>("/api/nudges/due");
  const { data: outbox, reload: reloadOutbox } = useApi<OutboxRow[]>("/api/outbox?limit=12", 10000);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  if (error) return <ErrorNote message={error} />;
  const nudgesOn = status?.features.includes("nudges");

  const runNudges = async () => {
    setBusy(true);
    try {
      const r = await api<{ sent: number; skipped: number }>("/api/nudges/run", { method: "POST" });
      setNote(r.sent ? `Sent ${r.sent} personal nudge${r.sent === 1 ? "" : "s"}.` : "No one new to nudge right now (recently nudged, opted out, or quiet hours).");
      reloadDue();
      reloadOutbox();
    } catch (e) {
      setNote(e instanceof Error ? e.message : "Couldn't send nudges");
    } finally {
      setBusy(false);
    }
  };
  const remove = async (id: number) => {
    await api(`/api/waitlist/${id}`, { method: "DELETE" });
    reloadWaitlist();
  };

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Refill & nudges"
        subtitle="Empty slots get refilled from the waitlist; regulars get a nudge when they're due."
        action={
          <Button variant="secondary" onClick={() => { reloadOffers(); reloadWaitlist(); reloadDue(); reloadOutbox(); }}>
            <RefreshCw size={15} /> Refresh
          </Button>
        }
      />

      {/* How it works */}
      <div className="mb-6 grid gap-3 sm:grid-cols-3">
        {[
          { icon: <Zap size={16} />, title: "A slot opens", body: "A cancellation or unpaid deposit frees up time." },
          { icon: <Send size={16} />, title: "Best matches get a text", body: "Ranked by service fit, stylist and flexibility — 3 at a time." },
          { icon: <Check size={16} />, title: "First yes wins", body: "It's booked instantly; everyone else hears it's taken." },
        ].map((s, i) => (
          <div key={s.title} className="flex gap-3 rounded-2xl border border-line bg-surface/60 p-4">
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl bg-sky-soft text-sky">{s.icon}</span>
            <div>
              <p className="text-sm font-semibold text-ink">
                <span className="text-muted">{i + 1}. </span>
                {s.title}
              </p>
              <p className="mt-0.5 text-[13px] text-muted">{s.body}</p>
            </div>
          </div>
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Recent refills" subtitle="Freed-up slots and who grabbed them" />
          <div className="px-3 pb-3">
            {!offers && <Skeleton className="m-2 h-24" />}
            {offers?.length === 0 && <Empty icon={<RefreshCw size={20} />} title="No refills yet" body="Cancel an appointment from the calendar to watch FullChair refill it." />}
            <ul className="divide-y divide-line">
              {offers?.map((o) => (
                <li key={o.id} className="flex items-center gap-3 px-2 py-3">
                  <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-canvas text-muted">
                    {o.status === "filled" ? <Check size={16} className="text-sage" /> : o.status === "open" ? <Hourglass size={16} className="text-sky" /> : <Clock size={16} />}
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-medium text-ink">
                      {o.when} · {o.stylist.split(" ")[0]}
                    </p>
                    <p className="text-[13px] text-muted">
                      {o.status === "filled" ? `Filled by ${o.filled_by}` : `${o.contacted} client${o.contacted === 1 ? "" : "s"} texted`} · {ago(o.created_at)}
                    </p>
                  </div>
                  <Badge tone={OFFER_TONE[o.status]}>{o.status}</Badge>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card>
          <CardHeader title="Waitlist" subtitle={`${waitlist?.length ?? "…"} clients waiting for an opening`} />
          <div className="px-3 pb-3">
            {waitlist?.length === 0 && <Empty title="Waitlist is empty" body="FullChair adds clients here when nothing suitable is open." />}
            <ul className="divide-y divide-line">
              {waitlist?.map((w) => (
                <li key={w.id} className="group flex items-center gap-3 px-2 py-3">
                  <Avatar name={w.client.name} size={32} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">
                      {w.client.name} <span className="font-normal text-muted">· {w.service}</span>
                    </p>
                    <p className="truncate text-[13px] text-muted">
                      {[w.stylist && `with ${w.stylist.split(" ")[0]}`, w.preferred_times].filter(Boolean).join(" · ") || "Any time"}
                    </p>
                  </div>
                  {w.flexible && <Badge tone="sky">Short notice OK</Badge>}
                  <button onClick={() => remove(w.id)} className="rounded-lg p-1.5 text-muted opacity-0 transition-opacity group-hover:opacity-100 hover:bg-danger-soft hover:text-danger" aria-label="Remove from waitlist">
                    <Trash2 size={15} />
                  </button>
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Due for a rebook"
            subtitle="Regulars past their usual interval with nothing booked"
            action={
              <Button variant="primary" size="sm" onClick={runNudges} disabled={busy || !nudgesOn} title={nudgesOn ? "" : "Growth plan feature"}>
                <BellRing size={14} /> {busy ? "Sending…" : "Send nudges now"}
              </Button>
            }
          />
          {note && <p className="mx-5 mb-2 rounded-xl bg-sage-soft px-3 py-2 text-[13px] text-sage">{note}</p>}
          {!nudgesOn && status && <p className="mx-5 mb-2 rounded-xl bg-amber-soft px-3 py-2 text-[13px] text-amber">Rebooking nudges are part of the Growth plan.</p>}
          <div className="px-3 pb-3">
            {due?.length === 0 && <Empty icon={<BellRing size={20} />} title="Everyone's on track" body="No regulars are overdue right now." />}
            <ul className="divide-y divide-line">
              {due?.slice(0, 8).map((d) => (
                <li key={d.client.id} className="flex items-center gap-3 px-2 py-3">
                  <Avatar name={d.client.name} size={32} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-ink">{d.client.name}</p>
                    <p className="truncate text-[13px] text-muted">
                      {d.last_service} · {Math.round(d.days_since / 7)} weeks ago (usually every {Math.round(d.interval / 7)})
                    </p>
                  </div>
                  {d.client.last_nudged_at ? <Badge tone="neutral">Nudged {ago(d.client.last_nudged_at)}</Badge> : <Badge tone="amber">Due</Badge>}
                </li>
              ))}
            </ul>
          </div>
        </Card>

        <Card>
          <CardHeader title="Texts sent" subtitle={status?.integrations.sms ? "Delivered via Twilio" : "Demo mode — texts are simulated, not delivered"} />
          <div className="px-3 pb-3">
            {outbox?.length === 0 && <Empty title="No texts yet" />}
            <ul className="divide-y divide-line">
              {outbox?.map((m) => (
                <li key={m.id} className="px-2 py-3">
                  <div className="mb-1 flex items-center gap-2">
                    <Badge tone={m.purpose === "refill" ? "sky" : m.purpose === "nudge" ? "amber" : "neutral"}>{PURPOSE[m.purpose] || m.purpose}</Badge>
                    <span className="text-xs text-muted">to {m.to || "salon"}</span>
                    {m.status === "blocked" && <Badge tone="danger">held · quiet hours / opt-out</Badge>}
                    <span className="ml-auto text-xs text-muted">{ago(m.at)}</span>
                  </div>
                  <p className="line-clamp-2 text-[13px] leading-relaxed text-ink-2">{m.text}</p>
                </li>
              ))}
            </ul>
          </div>
        </Card>
      </div>
    </div>
  );
}
