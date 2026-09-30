"use client";

import clsx from "clsx";
import { ChevronLeft, Hand, MessageCircle, Search, Send, Sparkles, UserRound, Wrench } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { Bubbles } from "@/components/Thread";
import { Avatar, Badge, Button, Card, ChannelBadge, ChannelIcon, Empty, ErrorNote, Input, PageHeader, Segmented, Skeleton } from "@/components/ui";
import { api, useApi, type ConversationDetail, type ConversationRow } from "@/lib/api";
import { ago, dayOf, timeOf } from "@/lib/format";

type Filter = "all" | "handoff" | "open" | "closed";

const OUTCOME: Record<string, { label: string; tone: "sage" | "rose" | "amber" | "sky" | "neutral" }> = {
  booked: { label: "Booked", tone: "sage" },
  handoff: { label: "Handed off", tone: "rose" },
  waitlisted: { label: "Waitlisted", tone: "sky" },
  answered: { label: "Answered", tone: "neutral" },
};

function InboxInner() {
  const params = useSearchParams();
  const router = useRouter();
  const selected = params.get("c") ? Number(params.get("c")) : null;
  const [filter, setFilter] = useState<Filter>("all");
  const [q, setQ] = useState("");

  const qs = new URLSearchParams();
  if (filter !== "all") qs.set("status", filter);
  if (q) qs.set("q", q);
  const { data: rows, error } = useApi<ConversationRow[]>(`/api/conversations?${qs}`, 8000);

  const select = (id: number | null) => router.replace(id ? `/inbox?c=${id}` : "/inbox", { scroll: false });

  // On wide screens, open the most recent conversation instead of an empty pane.
  useEffect(() => {
    if (!selected && rows?.length && window.matchMedia("(min-width: 768px)").matches) select(rows[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, selected]);

  if (error) return <ErrorNote message={error} />;

  return (
    <div className="animate-fade-up">
      <PageHeader title="Inbox" subtitle="Every call, text and DM FullChair has handled — jump in anytime." />
      <Card className="grid h-[calc(100vh-220px)] min-h-[560px] grid-cols-1 overflow-hidden md:grid-cols-[340px_1fr]">
        {/* List */}
        <div className={clsx("flex min-h-0 flex-col border-line md:border-r", selected && "hidden md:flex")}>
          <div className="space-y-3 border-b border-line p-3">
            <div className="relative">
              <Search size={15} className="absolute top-1/2 left-3 -translate-y-1/2 text-muted" />
              <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search clients" className="pl-9" />
            </div>
            <Segmented
              value={filter}
              onChange={setFilter}
              options={[
                { value: "all", label: "All" },
                { value: "handoff", label: "Needs you" },
                { value: "open", label: "Active" },
                { value: "closed", label: "Done" },
              ]}
            />
          </div>
          <div className="scroll-thin flex-1 overflow-y-auto p-2">
            {!rows && [0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="mb-2 h-[72px]" />)}
            {rows?.length === 0 && <Empty icon={<MessageCircle size={20} />} title="No conversations" body="Nothing matches this filter yet." />}
            {rows?.map((c) => (
              <button
                key={c.id}
                onClick={() => select(c.id)}
                className={clsx(
                  "mb-0.5 flex w-full gap-3 rounded-xl p-3 text-left transition-colors",
                  selected === c.id ? "bg-rose-soft/70" : "hover:bg-canvas",
                )}
              >
                <div className="relative">
                  <Avatar name={c.client.name || c.client.phone} />
                  <span className="absolute -right-1 -bottom-1 rounded-full bg-surface p-0.5 text-muted ring-1 ring-line">
                    <ChannelIcon channel={c.channel} size={11} />
                  </span>
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <span className="truncate text-sm font-semibold text-ink">{c.client.name || c.client.phone || c.client.ig}</span>
                    {c.status === "handoff" && <span className="h-2 w-2 shrink-0 rounded-full bg-rose" title="Needs you" />}
                    <span className="ml-auto shrink-0 text-[11px] text-muted">{ago(c.last_message_at)}</span>
                  </div>
                  <p className="mt-0.5 truncate text-[13px] text-muted">
                    {c.last_sender === "ai" && "FullChair: "}
                    {c.last_sender === "staff" && "You: "}
                    {c.last_message}
                  </p>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Thread */}
        <div className={clsx("min-h-0", !selected && "hidden md:block")}>
          {selected ? (
            <ThreadPane id={selected} onBack={() => select(null)} />
          ) : (
            <div className="flex h-full items-center justify-center">
              <Empty icon={<MessageCircle size={22} />} title="Pick a conversation" body="See exactly what FullChair said and step in whenever you like." />
            </div>
          )}
        </div>
      </Card>
    </div>
  );
}

function ThreadPane({ id, onBack }: { id: number; onBack: () => void }) {
  const { data: c, reload, setData } = useApi<ConversationDetail>(`/api/conversations/${id}`, 6000);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [showTrace, setShowTrace] = useState(false);

  if (!c) return <div className="p-6"><Skeleton className="h-full min-h-80" /></div>;

  const act = async (path: string) => {
    await api(`/api/conversations/${id}/${path}`, { method: "POST" });
    reload();
  };
  const send = async () => {
    if (!draft.trim()) return;
    setSending(true);
    try {
      const d = await api<ConversationDetail>(`/api/conversations/${id}/reply`, { method: "POST", json: { text: draft.trim() } });
      setData(d);
      setDraft("");
    } finally {
      setSending(false);
    }
  };

  const outcome = OUTCOME[c.outcome];
  const toolCalls = c.traces.flatMap((t) => t.tool_calls);

  return (
    <div className="flex h-full min-h-0 flex-col">
      {/* header */}
      <div className="flex flex-wrap items-center gap-3 border-b border-line px-4 py-3">
        <button onClick={onBack} className="rounded-lg p-1 text-muted hover:bg-canvas md:hidden" aria-label="Back">
          <ChevronLeft size={20} />
        </button>
        <Avatar name={c.client.name || c.client.phone} />
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold text-ink">{c.client.name || "New client"}</p>
          <p className="truncate text-xs text-muted">{c.client.phone || c.client.ig}</p>
        </div>
        <ChannelBadge channel={c.channel} />
        {outcome && <Badge tone={outcome.tone}>{outcome.label}</Badge>}
        {c.status === "handoff" ? (
          <>
            <Button size="sm" variant="secondary" onClick={() => act("resume-ai")}>
              <Sparkles size={14} /> Hand back to AI
            </Button>
            <Button size="sm" variant="primary" onClick={() => act("resolve")}>
              Mark resolved
            </Button>
          </>
        ) : (
          <Button size="sm" variant="secondary" onClick={() => act("take-over")}>
            <Hand size={14} /> Take over
          </Button>
        )}
      </div>

      {c.status === "handoff" && (
        <div className="flex gap-3 border-b border-rose/15 bg-rose-soft/60 px-5 py-3 text-sm">
          <Hand size={16} className="mt-0.5 shrink-0 text-rose" />
          <div>
            <p className="font-medium text-ink">FullChair handed this to your team — the AI is paused in this thread.</p>
            {c.handoff_summary && <p className="mt-0.5 text-ink-2">{c.handoff_summary}</p>}
          </div>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <div className="scroll-thin flex-1 overflow-y-auto px-5 py-5">
          <Bubbles messages={c.messages} />
        </div>
        {/* context rail */}
        <aside className="scroll-thin hidden w-64 shrink-0 space-y-5 overflow-y-auto border-l border-line bg-canvas/40 p-4 xl:block">
          <div>
            <p className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">Upcoming</p>
            {c.upcoming.length === 0 && <p className="text-[13px] text-muted">No upcoming appointments</p>}
            {c.upcoming.map((a) => (
              <div key={a.id} className="mb-2 rounded-xl bg-surface p-3 ring-1 ring-line">
                <p className="text-sm font-medium text-ink">{a.service.name}</p>
                <p className="text-xs text-muted">
                  {dayOf(a.start)} · {timeOf(a.start)} · {a.stylist.name.split(" ")[0]}
                </p>
                {a.status === "pending_deposit" && (
                  <Badge tone="amber" className="mt-2">
                    Awaiting deposit
                  </Badge>
                )}
              </div>
            ))}
          </div>
          {toolCalls.length > 0 && (
            <div>
              <button onClick={() => setShowTrace((s) => !s)} className="mb-2 flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.08em] text-muted uppercase hover:text-ink">
                <Wrench size={12} /> What the AI did ({toolCalls.length})
              </button>
              {showTrace && (
                <ol className="space-y-1.5">
                  {toolCalls.map((t, i) => (
                    <li key={i} className="rounded-lg bg-surface px-2.5 py-1.5 font-mono text-[11px] text-ink-2 ring-1 ring-line">
                      {t.name}
                      {t.error && <span className="block font-sans text-danger">{t.error}</span>}
                    </li>
                  ))}
                </ol>
              )}
            </div>
          )}
        </aside>
      </div>

      {/* composer */}
      <div className="border-t border-line p-3">
        <div className="flex items-end gap-2">
          <div className="flex h-10 items-center pl-1 text-muted" title="Replying as your team">
            <UserRound size={18} />
          </div>
          <textarea
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                send();
              }
            }}
            rows={1}
            placeholder={c.status === "handoff" ? "Reply to the client…" : "Reply as your team (FullChair will keep helping unless you take over)"}
            className="max-h-32 min-h-10 flex-1 resize-none rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm focus:border-rose/50 focus:ring-4 focus:ring-rose/10 focus:outline-none"
          />
          <Button variant="primary" onClick={send} disabled={sending || !draft.trim()} aria-label="Send">
            <Send size={15} />
          </Button>
        </div>
      </div>
    </div>
  );
}

export default function InboxPage() {
  return (
    <Suspense fallback={<Skeleton className="h-96" />}>
      <InboxInner />
    </Suspense>
  );
}
