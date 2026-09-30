"use client";

import clsx from "clsx";
import { Search, Users, X } from "lucide-react";
import { useState } from "react";
import { Avatar, Badge, Button, Card, Empty, ErrorNote, Field, Input, PageHeader, Segmented, Skeleton, Textarea, Toggle } from "@/components/ui";
import { api, useApi, type ClientRow } from "@/lib/api";
import { dayOf, money } from "@/lib/format";

export default function ClientsPage() {
  const [q, setQ] = useState("");
  const [view, setView] = useState<"all" | "due" | "upcoming">("all");
  const { data, error, reload } = useApi<ClientRow[]>(`/api/clients?q=${encodeURIComponent(q)}`);
  const [open, setOpen] = useState<ClientRow | null>(null);

  if (error) return <ErrorNote message={error} />;

  const rows = (data || []).filter((c) => (view === "due" ? c.due_for_rebook : view === "upcoming" ? !!c.next_visit : true));
  const dueCount = (data || []).filter((c) => c.due_for_rebook).length;

  return (
    <div className="animate-fade-up">
      <PageHeader title="Clients" subtitle="One profile per client across calls, texts and Instagram." />
      <Card>
        <div className="flex flex-wrap items-center gap-3 border-b border-line p-4">
          <div className="relative w-full max-w-xs">
            <Search size={15} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, phone or @handle" className="pl-9" />
          </div>
          <Segmented
            value={view}
            onChange={setView}
            options={[
              { value: "all", label: "Everyone" },
              { value: "due", label: <>Due to rebook {dueCount > 0 && <Badge tone="amber">{dueCount}</Badge>}</> },
              { value: "upcoming", label: "Booked" },
            ]}
          />
          <span className="ml-auto text-sm text-muted">{rows.length} clients</span>
        </div>
        <div className="scroll-thin overflow-x-auto">
          <table className="w-full min-w-[760px] text-sm">
            <thead>
              <tr className="text-left text-xs text-muted">
                <th className="px-5 py-3 font-medium">Client</th>
                <th className="px-3 py-3 font-medium">Usually sees</th>
                <th className="px-3 py-3 text-right font-medium">Visits</th>
                <th className="px-3 py-3 text-right font-medium">Lifetime</th>
                <th className="px-3 py-3 font-medium">Last visit</th>
                <th className="px-3 py-3 font-medium">Next visit</th>
                <th className="px-5 py-3 font-medium" />
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {!data &&
                [0, 1, 2, 3, 4].map((i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-5 py-3">
                      <Skeleton className="h-8" />
                    </td>
                  </tr>
                ))}
              {rows.map((c) => (
                <tr key={c.id} onClick={() => setOpen(c)} className="cursor-pointer transition-colors hover:bg-canvas/70">
                  <td className="px-5 py-3">
                    <div className="flex items-center gap-3">
                      <Avatar name={c.name || c.phone} size={32} />
                      <div className="min-w-0">
                        <p className="truncate font-medium text-ink">{c.name || "Unknown"}</p>
                        <p className="truncate text-xs text-muted">{c.phone || c.ig}</p>
                      </div>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-ink-2">{c.preferred_stylist?.split(" ")[0] || "—"}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{c.visits}</td>
                  <td className="px-3 py-3 text-right tabular-nums">{money(c.lifetime_value)}</td>
                  <td className="px-3 py-3 text-ink-2">
                    {c.last_visit ? (
                      <>
                        {new Date(c.last_visit + "T12:00").toLocaleDateString("en-US", { month: "short", day: "numeric" })}
                        <span className="block text-xs text-muted">{c.last_service}</span>
                      </>
                    ) : (
                      "—"
                    )}
                  </td>
                  <td className="px-3 py-3 text-ink-2">{c.next_visit ? dayOf(c.next_visit) : "—"}</td>
                  <td className="px-5 py-3 text-right">
                    <div className="flex justify-end gap-1.5">
                      {c.due_for_rebook && <Badge tone="amber">Due to rebook</Badge>}
                      {!c.opt_in && <Badge tone="neutral">Opted out</Badge>}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {data && rows.length === 0 && <Empty icon={<Users size={20} />} title="No clients here" body="Try a different search or filter." />}
        </div>
      </Card>

      {open && <ClientDrawer client={open} onClose={() => setOpen(null)} onSaved={() => { reload(); setOpen(null); }} />}
    </div>
  );
}

function ClientDrawer({ client, onClose, onSaved }: { client: ClientRow; onClose: () => void; onSaved: () => void }) {
  const [notes, setNotes] = useState(client.notes);
  const [optIn, setOptIn] = useState(client.opt_in);
  const [intervalDays, setIntervalDays] = useState(client.visit_interval_days?.toString() || "");
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    await api(`/api/clients/${client.id}`, {
      method: "PATCH",
      json: { notes, opt_in: optIn, visit_interval_days: intervalDays ? Number(intervalDays) : null },
    });
    setSaving(false);
    onSaved();
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      <div className="absolute inset-0 bg-ink/20 backdrop-blur-[2px]" onClick={onClose} />
      <div className="animate-fade-up relative flex h-full w-full max-w-md flex-col bg-surface shadow-[var(--shadow-pop)]">
        <div className="flex items-center justify-between border-b border-line px-6 py-4">
          <h2 className="font-serif text-xl">Client</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 space-y-5 overflow-y-auto p-6">
          <div className="flex items-center gap-3">
            <Avatar name={client.name || client.phone} size={48} />
            <div>
              <p className="text-lg font-semibold">{client.name || "Unknown"}</p>
              <p className="text-sm text-muted">{[client.phone, client.ig].filter(Boolean).join(" · ")}</p>
            </div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            {[
              ["Visits", String(client.visits)],
              ["Lifetime", money(client.lifetime_value)],
              ["Every", client.visit_interval_days ? `${client.visit_interval_days}d` : "—"],
            ].map(([k, v]) => (
              <div key={k} className="rounded-2xl bg-canvas p-3 text-center">
                <p className="text-xs text-muted">{k}</p>
                <p className="mt-0.5 text-lg font-semibold tabular-nums">{v}</p>
              </div>
            ))}
          </div>
          <Field label="Notes for the team and the AI" hint="e.g. 'Prefers quiet appointments', 'Sensitive scalp'">
            <Textarea rows={4} value={notes} onChange={(e) => setNotes(e.target.value)} />
          </Field>
          <Field label="Usual visit interval (days)" hint="FullChair nudges them when this passes with nothing booked.">
            <Input type="number" min={7} value={intervalDays} onChange={(e) => setIntervalDays(e.target.value)} />
          </Field>
          <div className={clsx("flex items-center justify-between rounded-2xl p-4 ring-1 ring-line")}>
            <div>
              <p className="text-sm font-medium">Texts from FullChair</p>
              <p className="text-xs text-muted">Refill offers and rebooking reminders</p>
            </div>
            <Toggle checked={optIn} onChange={setOptIn} label="Opt in to texts" />
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-line p-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button variant="primary" onClick={save} disabled={saving}>
            {saving ? "Saving…" : "Save changes"}
          </Button>
        </div>
      </div>
    </div>
  );
}
