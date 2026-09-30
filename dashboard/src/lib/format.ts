export const money = (n: number, cents = false) =>
  n.toLocaleString("en-US", { style: "currency", currency: "USD", maximumFractionDigits: cents ? 2 : 0 });

export const num = (n: number) => n.toLocaleString("en-US");

export function pctChange(value: number, prev: number): number | null {
  if (!prev) return null;
  return Math.round(((value - prev) / prev) * 100);
}

/** "2026-10-04T14:30" (salon-local, no zone) -> Date in local display terms */
export const parseLocal = (s: string) => new Date(s.length <= 16 ? s + ":00" : s);

export const timeOf = (s: string) =>
  parseLocal(s).toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit" });

export const dayOf = (s: string) =>
  parseLocal(s).toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric" });

export function ago(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  if (diff < 86400 * 7) return `${Math.floor(diff / 86400)}d ago`;
  return new Date(iso).toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

export const initials = (name: string) =>
  (name || "?")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase())
    .join("") || "?";

export const firstName = (name: string) => (name || "").split(" ")[0] || name;
