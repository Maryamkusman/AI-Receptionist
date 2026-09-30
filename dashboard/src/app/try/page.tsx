"use client";

import clsx from "clsx";
import { ArrowUp, CalendarDays, Info, RotateCcw, Sparkles, Wrench } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Bubbles } from "@/components/Thread";
import { Badge, Button, Card, CardHeader, ChannelIcon, CHANNEL_LABEL, PageHeader, Segmented } from "@/components/ui";
import { api, useApi, type Channel, type ConversationDetail, type MessageRow, type Status } from "@/lib/api";
import { dayOf, timeOf } from "@/lib/format";

const SUGGESTIONS = [
  "How much is balayage?",
  "Can I get in Saturday with Jess?",
  "Any men's cuts tomorrow after 5?",
  "Is there parking?",
  "I need to cancel my appointment",
  "Can I talk to a real person?",
];

const TOOL_LABEL: Record<string, string> = {
  check_availability: "Checked live availability",
  create_booking: "Booked the appointment",
  reschedule_booking: "Rescheduled",
  cancel_booking: "Cancelled & started refill",
  send_deposit_link: "Sent a deposit link",
  add_to_waitlist: "Added to waitlist",
  lookup_service_info: "Looked up menu & policies",
  handoff_to_human: "Handed off to your team",
};

function newIdentity() {
  return `+1555${Math.floor(1000000 + Math.random() * 8999999)}`;
}

export default function TryPage() {
  const { data: status } = useApi<Status>("/api/status");
  const [channel, setChannel] = useState<Channel>("sms");
  const [identity, setIdentity] = useState("");
  const [messages, setMessages] = useState<MessageRow[]>([]);
  const [conv, setConv] = useState<ConversationDetail | null>(null);
  const [draft, setDraft] = useState("");
  const [typing, setTyping] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    let id = "";
    try {
      id = localStorage.getItem("fullchair-try-id") || "";
    } catch {}
    if (!id) id = newIdentity();
    setIdentity(id);
    try {
      localStorage.setItem("fullchair-try-id", id);
    } catch {}
  }, []);

  const send = async (text: string) => {
    if (!text.trim() || typing) return;
    setErr(null);
    setDraft("");
    const temp: MessageRow = { id: -Date.now(), direction: "in", sender: "client", text, at: new Date().toISOString() };
    setMessages((m) => [...m, temp]);
    setTyping(true);
    try {
      const ident = channel === "instagram" ? `@guest${identity.slice(-5)}` : identity;
      const r = await api<{ reply: string | null; conversation: ConversationDetail }>("/api/chat", {
        method: "POST",
        json: { text, phone: ident, channel },
      });
      setConv(r.conversation);
      setMessages(r.conversation.messages);
      if (!r.reply && r.conversation.status === "handoff") {
        setMessages((m) => [...m, { id: -1, direction: "out", sender: "staff", text: "(Your team has this thread now — FullChair stays quiet until they hand it back.)", at: "" }]);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Couldn't reach the API");
    } finally {
      setTyping(false);
      inputRef.current?.focus();
    }
  };

  const reset = async () => {
    if (identity) await api("/api/chat/reset", { method: "POST", json: { phone: identity, channel: "sms" } }).catch(() => {});
    const id = newIdentity();
    setIdentity(id);
    try {
      localStorage.setItem("fullchair-try-id", id);
    } catch {}
    setMessages([]);
    setConv(null);
  };

  const tools = conv?.traces.flatMap((t) => t.tool_calls) || [];

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Try it live"
        subtitle="Message your receptionist exactly like a client would. Bookings land on the real calendar."
        action={
          <Button variant="secondary" onClick={reset}>
            <RotateCcw size={15} /> Start over as a new client
          </Button>
        }
      />

      <div className="grid gap-8 lg:grid-cols-[400px_1fr]">
        {/* Phone */}
        <div className="mx-auto w-full max-w-[400px]">
          <div className="rounded-[44px] bg-ink p-3 shadow-[var(--shadow-pop)]">
            <div className="flex h-[640px] flex-col overflow-hidden rounded-[34px] bg-surface">
              <div className="flex flex-col items-center border-b border-line bg-canvas/70 px-4 pt-3 pb-3 backdrop-blur">
                <div className="mb-3 h-1.5 w-20 rounded-full bg-ink/15" />
                <div className="flex h-11 w-11 items-center justify-center rounded-full bg-rose text-white">
                  <ChannelIcon channel={channel} size={18} />
                </div>
                <p className="mt-1.5 text-sm font-semibold text-ink">{status?.salon.name || "Your salon"}</p>
                <p className="text-[11px] text-muted">{CHANNEL_LABEL[channel]} · usually replies instantly</p>
              </div>
              <div className="scroll-thin flex-1 overflow-y-auto px-3 py-4">
                {messages.length === 0 && !typing && (
                  <div className="flex h-full flex-col items-center justify-center px-6 text-center">
                    <Sparkles className="mb-3 text-rose" size={22} />
                    <p className="text-sm font-medium text-ink">Say hi to your front desk</p>
                    <p className="mt-1 text-[13px] text-muted">Tap a suggestion or type anything a client might ask.</p>
                  </div>
                )}
                <Bubbles messages={messages} typing={typing} perspective="client" dense />
              </div>
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  send(draft);
                }}
                className="flex items-center gap-2 border-t border-line p-2.5"
              >
                <input
                  ref={inputRef}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                  placeholder={channel === "instagram" ? "Message…" : "Text message"}
                  className="h-10 flex-1 rounded-full border border-line-strong bg-canvas px-4 text-sm focus:border-sky/50 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!draft.trim() || typing}
                  className="flex h-9 w-9 items-center justify-center rounded-full bg-sky text-white transition-opacity disabled:opacity-40"
                  aria-label="Send"
                >
                  <ArrowUp size={18} />
                </button>
              </form>
            </div>
          </div>
        </div>

        {/* Side panel */}
        <div className="space-y-5">
          <Card className={clsx("p-4", status?.ai.enabled ? "bg-sage-soft/40!" : "bg-amber-soft/50!")}>
            <div className="flex gap-3">
              <Info size={18} className={clsx("mt-0.5 shrink-0", status?.ai.enabled ? "text-sage" : "text-amber")} />
              <div className="text-sm">
                {status?.ai.enabled ? (
                  <p>
                    <span className="font-semibold">Live with Claude.</span> Replies come from the real receptionist agent, using your menu, policies and live availability.
                  </p>
                ) : (
                  <p>
                    <span className="font-semibold">Demo mode.</span> A simple scripted receptionist is answering so you can explore. Add <code className="rounded bg-white/70 px-1">ANTHROPIC_API_KEY</code> to{" "}
                    <code className="rounded bg-white/70 px-1">backend/.env</code> for natural conversations powered by Claude.
                  </p>
                )}
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Channel" subtitle="The receptionist adapts its style to where the client is" />
            <div className="px-5 pb-5">
              <Segmented
                value={channel}
                onChange={(c) => {
                  setChannel(c);
                  setMessages([]);
                  setConv(null);
                }}
                options={(["sms", "instagram", "web"] as Channel[]).map((c) => ({
                  value: c,
                  label: (
                    <>
                      <ChannelIcon channel={c} size={13} /> {CHANNEL_LABEL[c]}
                    </>
                  ),
                }))}
              />
            </div>
          </Card>

          <Card>
            <CardHeader title="Try asking" />
            <div className="flex flex-wrap gap-2 px-5 pb-5">
              {SUGGESTIONS.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  disabled={typing}
                  className="rounded-full border border-line-strong bg-surface px-3.5 py-1.5 text-[13px] text-ink-2 transition-all hover:border-rose/40 hover:bg-rose-soft hover:text-rose disabled:opacity-50"
                >
                  {s}
                </button>
              ))}
            </div>
          </Card>

          <Card>
            <CardHeader title="Behind the scenes" subtitle="What FullChair did in this conversation" />
            <div className="px-5 pb-5">
              {err && <p className="mb-3 rounded-xl bg-danger-soft px-3 py-2 text-sm text-danger">{err}</p>}
              {tools.length === 0 && (!conv || conv.upcoming.length === 0) && <p className="text-sm text-muted">Actions will appear here as the receptionist works.</p>}
              <ol className="space-y-2">
                {tools.map((t, i) => (
                  <li key={i} className="animate-fade-up flex items-center gap-2.5 text-sm">
                    <span className={clsx("flex h-6 w-6 items-center justify-center rounded-lg", t.error ? "bg-danger-soft text-danger" : "bg-canvas text-ink-2")}>
                      <Wrench size={12} />
                    </span>
                    <span className="text-ink">{TOOL_LABEL[t.name] || t.name}</span>
                    {t.error && <span className="truncate text-xs text-danger">{t.error}</span>}
                  </li>
                ))}
              </ol>
              {conv && conv.upcoming.length > 0 && (
                <div className="mt-4 space-y-2 border-t border-line pt-4">
                  {conv.upcoming.map((a) => (
                    <div key={a.id} className="animate-fade-up flex items-center gap-3 rounded-2xl bg-canvas p-3">
                      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-surface text-rose ring-1 ring-line">
                        <CalendarDays size={16} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium text-ink">{a.service.name}</p>
                        <p className="text-xs text-muted">
                          {dayOf(a.start)} · {timeOf(a.start)} · {a.stylist.name.split(" ")[0]}
                        </p>
                      </div>
                      <Badge tone={a.status === "pending_deposit" ? "amber" : "sage"}>{a.status === "pending_deposit" ? "Awaiting deposit" : "Booked"}</Badge>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
