"use client";

import clsx from "clsx";
import { Globe, MessageSquare, Phone } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, TextareaHTMLAttributes } from "react";
import type { Channel } from "@/lib/api";
import { initials } from "@/lib/format";

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <div className={clsx("rounded-2xl border border-line bg-surface shadow-[var(--shadow-card)]", className)}>
      {children}
    </div>
  );
}

export function CardHeader({ title, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
      <div className="min-w-0">
        <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
        {subtitle && <p className="mt-0.5 text-[13px] text-muted">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: string; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-serif text-[30px] leading-tight font-medium tracking-[-0.01em] text-ink sm:text-[34px]">{title}</h1>
        {subtitle && <p className="mt-1 text-[15px] text-muted">{subtitle}</p>}
      </div>
      {action && <div className="flex flex-wrap items-center gap-2">{action}</div>}
    </div>
  );
}

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...rest
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md" }) {
  return (
    <button
      {...rest}
      className={clsx(
        "inline-flex items-center justify-center gap-1.5 rounded-xl font-medium whitespace-nowrap transition-all disabled:cursor-not-allowed disabled:opacity-50",
        "focus-visible:ring-2 focus-visible:ring-rose/40 focus-visible:outline-none",
        size === "sm" ? "h-8 px-3 text-[13px]" : "h-10 px-4 text-sm",
        variant === "primary" && "bg-ink text-white hover:bg-ink/90 active:scale-[.98]",
        variant === "secondary" && "border border-line-strong bg-surface text-ink hover:bg-canvas",
        variant === "ghost" && "text-ink-2 hover:bg-canvas hover:text-ink",
        variant === "danger" && "border border-danger/20 bg-danger-soft text-danger hover:bg-danger/10",
        className,
      )}
    >
      {children}
    </button>
  );
}

export function Input({ className, ...rest }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      {...rest}
      className={clsx(
        "h-10 w-full rounded-xl border border-line-strong bg-surface px-3 text-sm text-ink placeholder:text-muted/70",
        "focus:border-rose/50 focus:ring-4 focus:ring-rose/10 focus:outline-none",
        className,
      )}
    />
  );
}

export function Textarea({ className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      {...rest}
      className={clsx(
        "w-full rounded-xl border border-line-strong bg-surface px-3 py-2.5 text-sm leading-relaxed text-ink placeholder:text-muted/70",
        "focus:border-rose/50 focus:ring-4 focus:ring-rose/10 focus:outline-none",
        className,
      )}
    />
  );
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-ink-2">{label}</span>
      {children}
      {hint && <span className="mt-1 block text-xs text-muted">{hint}</span>}
    </label>
  );
}

type Tone = "neutral" | "rose" | "sage" | "amber" | "sky" | "danger";

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap",
        tone === "neutral" && "bg-canvas text-ink-2 ring-1 ring-line",
        tone === "rose" && "bg-rose-soft text-rose",
        tone === "sage" && "bg-sage-soft text-sage",
        tone === "amber" && "bg-amber-soft text-amber",
        tone === "sky" && "bg-sky-soft text-sky",
        tone === "danger" && "bg-danger-soft text-danger",
        className,
      )}
    >
      {children}
    </span>
  );
}

export function Avatar({ name, color, size = 36 }: { name: string; color?: string; size?: number }) {
  return (
    <span
      className="inline-flex shrink-0 items-center justify-center rounded-full font-semibold text-white"
      style={{ width: size, height: size, fontSize: size * 0.36, background: color || avatarColor(name) }}
      aria-hidden
    >
      {initials(name)}
    </span>
  );
}

const AVATAR_TONES = ["#b77a8a", "#8a9b7a", "#c09a6b", "#7d8fa3", "#a48bb0", "#c08470", "#6f9a95"];
function avatarColor(name: string) {
  let h = 0;
  for (const c of name || "?") h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return AVATAR_TONES[h % AVATAR_TONES.length];
}

export function InstagramIcon({ size = 16, className }: { size?: number; className?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={className} aria-hidden>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <circle cx="17.5" cy="6.5" r="0.6" fill="currentColor" />
    </svg>
  );
}

export const CHANNEL_LABEL: Record<Channel, string> = { sms: "Text", instagram: "Instagram", voice: "Call", web: "Web chat" };

export function ChannelIcon({ channel, size = 14, className }: { channel: Channel; size?: number; className?: string }) {
  if (channel === "instagram") return <InstagramIcon size={size} className={className} />;
  if (channel === "voice") return <Phone size={size} className={className} />;
  if (channel === "web") return <Globe size={size} className={className} />;
  return <MessageSquare size={size} className={className} />;
}

export function ChannelBadge({ channel }: { channel: Channel }) {
  return (
    <Badge tone="neutral">
      <ChannelIcon channel={channel} size={12} />
      {CHANNEL_LABEL[channel]}
    </Badge>
  );
}

export function Empty({ icon, title, body }: { icon?: ReactNode; title: string; body?: string }) {
  return (
    <div className="flex flex-col items-center justify-center px-6 py-14 text-center">
      {icon && <div className="mb-3 rounded-2xl bg-canvas p-3 text-muted">{icon}</div>}
      <p className="font-medium text-ink">{title}</p>
      {body && <p className="mt-1 max-w-xs text-sm text-muted">{body}</p>}
    </div>
  );
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("animate-pulse rounded-xl bg-line/60", className)} />;
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <Card className="border-danger/20 bg-danger-soft/40! p-5 text-sm text-danger">
      <p className="font-medium">Can&apos;t reach the FullChair API</p>
      <p className="mt-1 text-danger/80">
        {message}. Make sure the backend is running (<code className="rounded bg-white/60 px-1">uvicorn app.main:app</code>).
      </p>
    </Card>
  );
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label?: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className={clsx(
        "relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors",
        checked ? "bg-sage" : "bg-line-strong",
      )}
    >
      <span className={clsx("inline-block h-5 w-5 rounded-full bg-white shadow transition-transform", checked ? "translate-x-5.5" : "translate-x-0.5")} />
    </button>
  );
}

export function Segmented<T extends string>({
  value,
  options,
  onChange,
}: {
  value: T;
  options: { value: T; label: ReactNode }[];
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-xl border border-line bg-canvas p-0.5">
      {options.map((o) => (
        <button
          key={o.value}
          onClick={() => onChange(o.value)}
          className={clsx(
            "flex h-8 items-center gap-1.5 rounded-[10px] px-3 text-[13px] font-medium transition-all",
            value === o.value ? "bg-surface text-ink shadow-sm ring-1 ring-line" : "text-muted hover:text-ink",
          )}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}
