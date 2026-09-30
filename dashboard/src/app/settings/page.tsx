"use client";

import clsx from "clsx";
import { Check, CircleCheck, Pause, Pencil, Play, Plus, Save, Trash2, TriangleAlert, X } from "lucide-react";
import { useEffect, useState } from "react";
import { Avatar, Badge, Button, Card, CardHeader, ErrorNote, Field, Input, PageHeader, Segmented, Skeleton, Textarea, Toggle } from "@/components/ui";
import { api, useApi, type Salon, type Service, type Status, type Stylist } from "@/lib/api";
import { money } from "@/lib/format";

type Tab = "salon" | "voice" | "menu" | "team" | "plan";
const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"] as const;
const DAY_NAME: Record<string, string> = { mon: "Monday", tue: "Tuesday", wed: "Wednesday", thu: "Thursday", fri: "Friday", sat: "Saturday", sun: "Sunday" };
const hourLabel = (h: number) => `${((h + 11) % 12) + 1}:00 ${h < 12 ? "AM" : "PM"}`;

export default function SettingsPage() {
  const [tab, setTab] = useState<Tab>("salon");
  const { data: salon, error, setData } = useApi<Salon>("/api/salon");
  const [draft, setDraft] = useState<Salon | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (salon && !draft) setDraft(salon);
  }, [salon, draft]);

  if (error) return <ErrorNote message={error} />;

  const dirty = !!draft && !!salon && JSON.stringify(draft) !== JSON.stringify(salon);
  const set = <K extends keyof Salon>(k: K, v: Salon[K]) => setDraft((d) => (d ? { ...d, [k]: v } : d));
  const save = async () => {
    if (!draft) return;
    const { id: _id, ...body } = draft;
    const s = await api<Salon>("/api/salon", { method: "PATCH", json: body });
    setData(s);
    setDraft(s);
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  };

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Settings"
        subtitle="Everything your receptionist knows about the salon."
        action={
          (tab === "salon" || tab === "voice") && (
            <Button variant="primary" onClick={save} disabled={!dirty}>
              {saved ? <Check size={15} /> : <Save size={15} />} {saved ? "Saved" : "Save changes"}
            </Button>
          )
        }
      />
      <div className="scroll-thin mb-6 overflow-x-auto">
        <Segmented
          value={tab}
          onChange={setTab}
          options={[
            { value: "salon", label: "Salon" },
            { value: "voice", label: "Voice & knowledge" },
            { value: "menu", label: "Service menu" },
            { value: "team", label: "Team" },
            { value: "plan", label: "Plan & connections" },
          ]}
        />
      </div>

      {!draft && <Skeleton className="h-96" />}

      {draft && tab === "salon" && (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card>
            <CardHeader title="Salon details" subtitle="Shared with clients when they ask" />
            <div className="space-y-4 px-5 pb-5">
              <Field label="Salon name">
                <Input value={draft.name} onChange={(e) => set("name", e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Phone">
                  <Input value={draft.phone} onChange={(e) => set("phone", e.target.value)} />
                </Field>
                <Field label="Timezone">
                  <Input value={draft.timezone} onChange={(e) => set("timezone", e.target.value)} />
                </Field>
              </div>
              <Field label="Address">
                <Input value={draft.address} onChange={(e) => set("address", e.target.value)} />
              </Field>
              <div className="grid gap-4 sm:grid-cols-2">
                <Field label="Handoff phone" hint="Gets a text with a summary when a human is needed">
                  <Input value={draft.handoff_phone} onChange={(e) => set("handoff_phone", e.target.value)} />
                </Field>
                <Field label="Average ticket ($)" hint="Used for ROI estimates">
                  <Input type="number" value={draft.avg_ticket} onChange={(e) => set("avg_ticket", Number(e.target.value))} />
                </Field>
              </div>
            </div>
          </Card>
          <Card>
            <CardHeader title="Opening hours" subtitle="FullChair only offers times inside these hours" />
            <div className="space-y-1 px-5 pb-5">
              {DAYS.map((d) => {
                const span = draft.hours[d];
                return (
                  <div key={d} className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-canvas/60">
                    <Toggle
                      checked={!!span}
                      onChange={(on) => set("hours", { ...draft.hours, [d]: on ? [9, 18] : null })}
                      label={`Open ${DAY_NAME[d]}`}
                    />
                    <span className="w-24 text-sm font-medium text-ink">{DAY_NAME[d]}</span>
                    {span ? (
                      <div className="flex items-center gap-2 text-sm">
                        <HourSelect value={span[0]} onChange={(v) => set("hours", { ...draft.hours, [d]: [v, span[1]] })} />
                        <span className="text-muted">to</span>
                        <HourSelect value={span[1]} onChange={(v) => set("hours", { ...draft.hours, [d]: [span[0], v] })} />
                      </div>
                    ) : (
                      <span className="text-sm text-muted">Closed</span>
                    )}
                  </div>
                );
              })}
              <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-line pt-4 text-sm text-ink-2">
                <span>Quiet hours for automated texts:</span>
                <HourSelect value={draft.quiet_hours_start} onChange={(v) => set("quiet_hours_start", v)} />
                <span className="text-muted">to</span>
                <HourSelect value={draft.quiet_hours_end} onChange={(v) => set("quiet_hours_end", v)} />
              </div>
            </div>
          </Card>
        </div>
      )}

      {draft && tab === "voice" && (
        <div className="grid gap-6 xl:grid-cols-2">
          <Card className="xl:col-span-2">
            <CardHeader title="Voice & tone" subtitle="How your receptionist sounds — write it the way you'd brief a new front-desk hire" />
            <div className="px-5 pb-5">
              <Textarea rows={3} value={draft.voice_tone} onChange={(e) => set("voice_tone", e.target.value)} />
            </div>
          </Card>
          <Card>
            <CardHeader title="Policies" subtitle="Cancellations, deposits, late arrivals…" />
            <div className="px-5 pb-5">
              <Textarea rows={14} value={draft.policies} onChange={(e) => set("policies", e.target.value)} />
            </div>
          </Card>
          <Card>
            <CardHeader title="FAQ" subtitle="Parking, products, prep — anything clients ask" />
            <div className="px-5 pb-5">
              <Textarea rows={14} value={draft.faq} onChange={(e) => set("faq", e.target.value)} />
            </div>
          </Card>
        </div>
      )}

      {tab === "menu" && <MenuEditor />}
      {tab === "team" && <TeamEditor />}
      {draft && tab === "plan" && <PlanPanel salon={draft} onChange={async (patch) => {
        const s = await api<Salon>("/api/salon", { method: "PATCH", json: patch });
        setData(s);
        setDraft(s);
      }} />}
    </div>
  );
}

function HourSelect({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <select
      value={value}
      onChange={(e) => onChange(Number(e.target.value))}
      className="h-9 rounded-lg border border-line-strong bg-surface px-2 text-sm focus:border-rose/50 focus:outline-none"
    >
      {Array.from({ length: 24 }, (_, h) => (
        <option key={h} value={h}>
          {hourLabel(h)}
        </option>
      ))}
    </select>
  );
}

// ------------------------------------------------------------------ menu

const EMPTY_SERVICE: Omit<Service, "id"> = {
  name: "", category: "Cut", description: "", duration_min: 60, price: 0, deposit_required: false,
  deposit_amount: 0, stylist_ids: [], rebook_interval_days: null, active: true,
};

function MenuEditor() {
  const { data: services, reload } = useApi<Service[]>("/api/services");
  const { data: stylists } = useApi<Stylist[]>("/api/stylists");
  const [editing, setEditing] = useState<(Omit<Service, "id"> & { id?: number }) | null>(null);

  const groups = (services || []).reduce<Record<string, Service[]>>((acc, s) => {
    (acc[s.category] ||= []).push(s);
    return acc;
  }, {});

  const save = async () => {
    if (!editing) return;
    const { id, ...body } = editing;
    await api(id ? `/api/services/${id}` : "/api/services", { method: id ? "PUT" : "POST", json: body });
    setEditing(null);
    reload();
  };
  const remove = async (id: number) => {
    await api(`/api/services/${id}`, { method: "DELETE" });
    setEditing(null);
    reload();
  };
  const nameOf = (id: number) => stylists?.find((s) => s.id === id)?.name.split(" ")[0];

  return (
    <>
      <Card>
        <CardHeader
          title="Service menu"
          subtitle="What FullChair can quote and book"
          action={
            <Button variant="primary" size="sm" onClick={() => setEditing({ ...EMPTY_SERVICE })}>
              <Plus size={14} /> Add service
            </Button>
          }
        />
        {!services && <Skeleton className="m-5 h-64" />}
        <div className="px-5 pb-5">
          {Object.entries(groups).map(([cat, list]) => (
            <div key={cat} className="mb-5 last:mb-0">
              <p className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">{cat}</p>
              <div className="divide-y divide-line rounded-2xl ring-1 ring-line">
                {list.map((s) => (
                  <button key={s.id} onClick={() => setEditing(s)} className="flex w-full items-center gap-4 px-4 py-3 text-left transition-colors first:rounded-t-2xl last:rounded-b-2xl hover:bg-canvas/60">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-medium text-ink">{s.name}</p>
                      <p className="truncate text-[13px] text-muted">
                        {s.duration_min} min
                        {s.stylist_ids.length > 0 && ` · ${s.stylist_ids.map(nameOf).join(", ")}`}
                        {s.description && ` · ${s.description}`}
                      </p>
                    </div>
                    {s.deposit_required && <Badge tone="amber">{money(s.deposit_amount)} deposit</Badge>}
                    <span className="w-16 text-right font-semibold text-ink tabular-nums">{money(s.price)}</span>
                    <Pencil size={14} className="text-muted" />
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </Card>

      {editing && (
        <Modal title={editing.id ? "Edit service" : "New service"} onClose={() => setEditing(null)}>
          <div className="space-y-4">
            <div className="grid gap-4 sm:grid-cols-[1fr_140px]">
              <Field label="Name">
                <Input value={editing.name} onChange={(e) => setEditing({ ...editing, name: e.target.value })} autoFocus />
              </Field>
              <Field label="Category">
                <Input value={editing.category} onChange={(e) => setEditing({ ...editing, category: e.target.value })} />
              </Field>
            </div>
            <Field label="Description">
              <Input value={editing.description} onChange={(e) => setEditing({ ...editing, description: e.target.value })} />
            </Field>
            <div className="grid grid-cols-3 gap-4">
              <Field label="Price ($)">
                <Input type="number" value={editing.price} onChange={(e) => setEditing({ ...editing, price: Number(e.target.value) })} />
              </Field>
              <Field label="Minutes">
                <Input type="number" step={15} value={editing.duration_min} onChange={(e) => setEditing({ ...editing, duration_min: Number(e.target.value) })} />
              </Field>
              <Field label="Rebook (days)">
                <Input type="number" value={editing.rebook_interval_days ?? ""} onChange={(e) => setEditing({ ...editing, rebook_interval_days: e.target.value ? Number(e.target.value) : null })} />
              </Field>
            </div>
            <div className="flex items-center gap-3 rounded-2xl p-3 ring-1 ring-line">
              <Toggle checked={editing.deposit_required} onChange={(v) => setEditing({ ...editing, deposit_required: v })} label="Deposit required" />
              <span className="flex-1 text-sm">Require a deposit to hold the slot</span>
              {editing.deposit_required && (
                <Input type="number" className="w-24" value={editing.deposit_amount} onChange={(e) => setEditing({ ...editing, deposit_amount: Number(e.target.value) })} />
              )}
            </div>
            <Field label="Who can do it" hint="None selected = anyone on the team">
              <div className="flex flex-wrap gap-2">
                {stylists?.map((st) => {
                  const on = editing.stylist_ids.includes(st.id);
                  return (
                    <button
                      type="button"
                      key={st.id}
                      onClick={() =>
                        setEditing({ ...editing, stylist_ids: on ? editing.stylist_ids.filter((i) => i !== st.id) : [...editing.stylist_ids, st.id] })
                      }
                      className={clsx(
                        "flex items-center gap-2 rounded-full py-1 pr-3 pl-1 text-sm ring-1 transition-colors",
                        on ? "bg-rose-soft text-rose ring-rose/30" : "text-ink-2 ring-line hover:bg-canvas",
                      )}
                    >
                      <Avatar name={st.name} color={st.color} size={22} />
                      {st.name.split(" ")[0]}
                    </button>
                  );
                })}
              </div>
            </Field>
          </div>
          <div className="mt-6 flex items-center gap-2">
            {editing.id && (
              <Button variant="danger" onClick={() => remove(editing.id!)}>
                <Trash2 size={14} /> Remove
              </Button>
            )}
            <Button variant="ghost" className="ml-auto" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={save} disabled={!editing.name.trim()}>
              Save service
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

// ------------------------------------------------------------------ team

const SWATCHES = ["#b86b77", "#7b8f6a", "#c49a5a", "#5f7a94", "#9a7bb0", "#c08470", "#5f9a95"];

function TeamEditor() {
  const { data: stylists, reload } = useApi<Stylist[]>("/api/stylists");
  const [editing, setEditing] = useState<Partial<Stylist> | null>(null);

  const save = async () => {
    if (!editing?.name) return;
    const body = { name: editing.name, specialties: editing.specialties || "", color: editing.color || SWATCHES[0], active: editing.active ?? true };
    await api(editing.id ? `/api/stylists/${editing.id}` : "/api/stylists", { method: editing.id ? "PUT" : "POST", json: body });
    setEditing(null);
    reload();
  };

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {!stylists && [0, 1, 2].map((i) => <Skeleton key={i} className="h-32" />)}
        {stylists?.map((s) => (
          <Card key={s.id} className="p-5">
            <div className="flex items-start gap-3">
              <Avatar name={s.name} color={s.color} size={44} />
              <div className="min-w-0 flex-1">
                <p className="font-semibold text-ink">{s.name}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-muted">{s.specialties || "No specialties listed"}</p>
              </div>
              <button onClick={() => setEditing(s)} className="rounded-lg p-1.5 text-muted hover:bg-canvas hover:text-ink" aria-label={`Edit ${s.name}`}>
                <Pencil size={15} />
              </button>
            </div>
          </Card>
        ))}
        <button
          onClick={() => setEditing({ color: SWATCHES[(stylists?.length || 0) % SWATCHES.length] })}
          className="flex min-h-32 flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-line-strong text-sm font-medium text-muted transition-colors hover:border-rose/40 hover:text-rose"
        >
          <Plus size={20} /> Add a stylist
        </button>
      </div>

      {editing && (
        <Modal title={editing.id ? "Edit stylist" : "New stylist"} onClose={() => setEditing(null)}>
          <div className="space-y-4">
            <Field label="Name">
              <Input value={editing.name || ""} onChange={(e) => setEditing({ ...editing, name: e.target.value })} autoFocus />
            </Field>
            <Field label="Specialties" hint="Helps FullChair match requests like 'someone good with curls'">
              <Input value={editing.specialties || ""} onChange={(e) => setEditing({ ...editing, specialties: e.target.value })} />
            </Field>
            <Field label="Calendar color">
              <div className="flex gap-2">
                {SWATCHES.map((c) => (
                  <button
                    key={c}
                    type="button"
                    onClick={() => setEditing({ ...editing, color: c })}
                    className={clsx("h-8 w-8 rounded-full ring-offset-2 transition-all", editing.color === c && "ring-2 ring-ink")}
                    style={{ background: c }}
                    aria-label={`Color ${c}`}
                  />
                ))}
              </div>
            </Field>
          </div>
          <div className="mt-6 flex items-center gap-2">
            {editing.id && (
              <Button
                variant="danger"
                onClick={async () => {
                  await api(`/api/stylists/${editing.id}`, { method: "PUT", json: { name: editing.name, specialties: editing.specialties, color: editing.color, active: false } });
                  setEditing(null);
                  reload();
                }}
              >
                <Trash2 size={14} /> Remove
              </Button>
            )}
            <Button variant="ghost" className="ml-auto" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={save} disabled={!editing.name?.trim()}>
              Save
            </Button>
          </div>
        </Modal>
      )}
    </>
  );
}

// ------------------------------------------------------------------ plan & connections

const PLANS = [
  { id: "starter", name: "Starter", who: "Solo studios, 1–3 chairs", monthly: 199, setup: 500, features: ["Text + Instagram receptionist", "Direct booking & deposits", "Owner dashboard"] },
  { id: "pro", name: "Pro", who: "Salons, 4–15 chairs", monthly: 399, setup: 1000, features: ["Everything in Starter", "Voice receptionist", "Cancellation refill"] },
  { id: "growth", name: "Growth", who: "Busy or multi-location salons", monthly: 699, setup: 1500, features: ["Everything in Pro", "Rebooking nudges", "Multiple locations", "Monthly performance review"] },
];

function PlanPanel({ salon, onChange }: { salon: Salon; onChange: (patch: Partial<Salon>) => Promise<void> }) {
  const { data: status } = useApi<Status>("/api/status");
  const conns = status
    ? [
        { name: "AI receptionist (Claude)", ok: status.ai.enabled, how: "Set ANTHROPIC_API_KEY in backend/.env" },
        { name: `Booking platform · ${status.integrations.booking.platform}`, ok: status.integrations.booking.connected, how: "Built-in demo calendar until your platform's API is connected" },
        { name: "SMS & voice (Twilio)", ok: status.integrations.sms, how: "Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER" },
        { name: "Instagram DMs (Meta)", ok: status.integrations.instagram, how: "Set META_PAGE_ACCESS_TOKEN and subscribe the webhook" },
        { name: "Deposits (Stripe)", ok: status.integrations.payments, how: "Set STRIPE_SECRET_KEY — demo checkout until then" },
      ]
    : [];

  return (
    <div className="space-y-6">
      <Card className="flex flex-wrap items-center gap-4 p-5">
        <span className={clsx("flex h-10 w-10 items-center justify-center rounded-xl", salon.ai_paused ? "bg-amber-soft text-amber" : "bg-sage-soft text-sage")}>
          {salon.ai_paused ? <Pause size={18} /> : <Play size={18} />}
        </span>
        <div className="flex-1">
          <p className="font-semibold text-ink">{salon.ai_paused ? "Receptionist is paused" : "Receptionist is answering"}</p>
          <p className="text-sm text-muted">{salon.ai_paused ? "New messages wait in the inbox for your team." : "Pause anytime — e.g. during a staff meeting or holiday."}</p>
        </div>
        <Button variant={salon.ai_paused ? "primary" : "secondary"} onClick={() => onChange({ ai_paused: !salon.ai_paused })}>
          {salon.ai_paused ? "Resume" : "Pause"}
        </Button>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        {PLANS.map((p) => {
          const current = salon.plan === p.id;
          return (
            <Card key={p.id} className={clsx("relative flex flex-col p-6", current && "ring-2 ring-rose")}>
              {current && <Badge tone="rose" className="absolute top-5 right-5">Current plan</Badge>}
              <p className="font-serif text-2xl text-ink">{p.name}</p>
              <p className="text-sm text-muted">{p.who}</p>
              <p className="mt-4">
                <span className="font-serif text-4xl text-ink">${p.monthly}</span>
                <span className="text-sm text-muted"> /month</span>
              </p>
              <p className="text-xs text-muted">+ ${p.setup.toLocaleString()} one-time setup</p>
              <ul className="mt-5 flex-1 space-y-2">
                {p.features.map((f) => (
                  <li key={f} className="flex gap-2 text-sm text-ink-2">
                    <Check size={16} className="mt-0.5 shrink-0 text-sage" /> {f}
                  </li>
                ))}
              </ul>
              {!current && (
                <Button variant="secondary" className="mt-6" onClick={() => onChange({ plan: p.id })}>
                  Switch to {p.name}
                </Button>
              )}
            </Card>
          );
        })}
      </div>

      <Card>
        <CardHeader title="Connections" subtitle="FullChair runs in demo mode for anything not connected yet" />
        <ul className="divide-y divide-line px-5 pb-3">
          {conns.map((c) => (
            <li key={c.name} className="flex items-center gap-3 py-3">
              {c.ok ? <CircleCheck size={18} className="text-sage" /> : <TriangleAlert size={18} className="text-amber" />}
              <div className="flex-1">
                <p className="text-sm font-medium text-ink">{c.name}</p>
                {!c.ok && <p className="text-[13px] text-muted">{c.how}</p>}
              </div>
              <Badge tone={c.ok ? "sage" : "amber"}>{c.ok ? "Connected" : "Demo mode"}</Badge>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}

function Modal({ title, onClose, children }: { title: string; onClose: () => void; children: React.ReactNode }) {
  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center p-4 sm:items-center">
      <div className="absolute inset-0 bg-ink/25 backdrop-blur-[2px]" onClick={onClose} />
      <div className="animate-fade-up relative w-full max-w-lg rounded-3xl bg-surface p-6 shadow-[var(--shadow-pop)]">
        <div className="mb-5 flex items-center justify-between">
          <h2 className="font-serif text-xl">{title}</h2>
          <button onClick={onClose} className="rounded-lg p-1.5 text-muted hover:bg-canvas" aria-label="Close">
            <X size={18} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}
