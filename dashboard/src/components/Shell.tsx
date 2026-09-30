"use client";

import clsx from "clsx";
import {
  CalendarDays,
  LayoutDashboard,
  ListChecks,
  Menu,
  MessageCircle,
  Settings,
  Sparkles,
  Users,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useApi, type ConversationRow, type Status } from "@/lib/api";

const NAV = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/inbox", label: "Inbox", icon: MessageCircle, badge: true },
  { href: "/calendar", label: "Calendar", icon: CalendarDays },
  { href: "/clients", label: "Clients", icon: Users },
  { href: "/waitlist", label: "Refill & nudges", icon: ListChecks },
  { href: "/try", label: "Try it live", icon: Sparkles },
  { href: "/settings", label: "Settings", icon: Settings },
];

function Logo() {
  return (
    <Link href="/" className="flex items-center gap-2.5 px-2">
      <span className="relative flex h-9 w-9 items-center justify-center rounded-xl bg-ink text-white">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" aria-hidden>
          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
          <rect x="5" y="11" width="14" height="6" rx="2" />
          <path d="M8 17v3M16 17v3" />
        </svg>
        <span className="absolute -top-0.5 -right-0.5 h-2.5 w-2.5 rounded-full border-2 border-canvas bg-rose" />
      </span>
      <span className="font-serif text-[21px] font-medium tracking-tight text-ink">FullChair</span>
    </Link>
  );
}

function StatusCard({ status }: { status: Status | null }) {
  if (!status) return null;
  const live = status.ai.enabled && !status.ai.paused;
  return (
    <div className="rounded-2xl border border-line bg-surface p-3.5">
      <div className="flex items-center gap-2">
        <span className="relative flex h-2.5 w-2.5">
          {live && <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-sage opacity-50" />}
          <span className={clsx("relative inline-flex h-2.5 w-2.5 rounded-full", status.ai.paused ? "bg-amber" : "bg-sage")} />
        </span>
        <span className="text-[13px] font-semibold text-ink">
          {status.ai.paused ? "Receptionist paused" : "Receptionist on duty"}
        </span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted">
        {status.ai.enabled ? "Powered by Claude · answering 24/7" : "Demo mode — add an Anthropic key to go live"}
      </p>
    </div>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  const { data: status } = useApi<Status>("/api/status", 30000);
  const { data: handoffs } = useApi<ConversationRow[]>("/api/conversations?status=handoff", 20000);
  const pending = handoffs?.length || 0;

  useEffect(() => setOpen(false), [pathname]);

  const nav = (
    <nav className="flex flex-col gap-0.5">
      {NAV.map(({ href, label, icon: Icon, badge }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={clsx(
              "group flex h-10 items-center gap-3 rounded-xl px-3 text-[14px] font-medium transition-colors",
              active ? "bg-surface text-ink shadow-[var(--shadow-card)] ring-1 ring-line" : "text-ink-2 hover:bg-surface/60 hover:text-ink",
            )}
          >
            <Icon size={17} className={clsx(active ? "text-rose" : "text-muted group-hover:text-ink-2")} />
            <span className="flex-1">{label}</span>
            {badge && pending > 0 && (
              <span className="rounded-full bg-rose px-1.5 py-px text-[11px] font-semibold text-white" title="Needs a human">
                {pending}
              </span>
            )}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="min-h-screen">
      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col gap-6 border-r border-line bg-canvas px-4 py-6 lg:flex">
        <Logo />
        <div className="px-2">
          <p className="text-[11px] font-semibold tracking-[0.08em] text-muted uppercase">Salon</p>
          <p className="mt-0.5 truncate text-[15px] font-medium text-ink">{status?.salon.name || "…"}</p>
        </div>
        {nav}
        <div className="mt-auto">
          <StatusCard status={status} />
        </div>
      </aside>

      {/* Mobile top bar */}
      <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-line bg-canvas/90 px-4 backdrop-blur lg:hidden">
        <Logo />
        <button onClick={() => setOpen(true)} className="rounded-xl p-2 text-ink hover:bg-surface" aria-label="Open menu">
          <Menu size={22} />
        </button>
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink/30 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <div className="animate-fade-up absolute inset-y-0 right-0 flex w-72 flex-col gap-6 bg-canvas p-5 shadow-[var(--shadow-pop)]">
            <div className="flex items-center justify-between">
              <span className="font-serif text-lg">{status?.salon.name}</span>
              <button onClick={() => setOpen(false)} className="rounded-xl p-2 hover:bg-surface" aria-label="Close menu">
                <X size={20} />
              </button>
            </div>
            {nav}
            <div className="mt-auto">
              <StatusCard status={status} />
            </div>
          </div>
        </div>
      )}

      <main className="min-w-0 overflow-x-clip lg:pl-64">
        <div className="mx-auto max-w-[1240px] px-4 py-6 sm:px-6 lg:px-10 lg:py-10">{children}</div>
      </main>
    </div>
  );
}
