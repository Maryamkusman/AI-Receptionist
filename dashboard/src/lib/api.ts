"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/$/, "");

export async function api<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init || {};
  const res = await fetch(`${API_URL}${path}`, {
    ...rest,
    headers: { ...(json !== undefined ? { "content-type": "application/json" } : {}), ...(rest.headers || {}) },
    body: json !== undefined ? JSON.stringify(json) : rest.body,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail || detail;
    } catch {}
    throw new Error(typeof detail === "string" ? detail : "Request failed");
  }
  return res.json();
}

/** Fetch + keep fresh. `poll` in ms re-fetches quietly in the background. */
export function useApi<T>(path: string | null, poll?: number) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const pathRef = useRef(path);
  pathRef.current = path;

  const load = useCallback(async (quiet = false) => {
    const p = pathRef.current;
    if (!p) return;
    if (!quiet) setLoading(true);
    try {
      const d = await api<T>(p);
      if (pathRef.current === p) {
        setData(d);
        setError(null);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
    if (!poll) return;
    const t = setInterval(() => load(true), poll);
    return () => clearInterval(t);
  }, [path, poll, load]);

  return { data, error, loading, reload: () => load(true), setData };
}

// ------------------------------------------------------------------ types

export type Channel = "sms" | "instagram" | "voice" | "web";

export interface Status {
  salon: { id: number; name: string; plan: string };
  ai: { enabled: boolean; model: string; paused: boolean };
  integrations: {
    booking: { platform: string; connected: boolean };
    sms: boolean;
    voice: boolean;
    instagram: boolean;
    payments: boolean;
  };
  features: string[];
  now: string;
}

export interface Kpi {
  value: number;
  prev: number;
}

export interface Overview {
  days: number;
  kpis: { conversations: Kpi; ai_bookings: Kpi; slots_refilled: Kpi; revenue_recovered: Kpi };
  roi: { plan: string; plan_cost: number; multiple: number | null };
  after_hours_share: number;
  by_source: Record<"ai" | "refill" | "nudge", { count: number; revenue: number }>;
  channels: Partial<Record<Channel, number>>;
  daily: { date: string; bookings: number; revenue: number; conversations: number }[];
  today: { id: number; start: string; client: string; service: string; stylist: string; color: string; booked_by_ai: boolean; status: string }[];
  handoffs: { id: number; client: string; channel: Channel; summary: string; at: string }[];
}

export interface ConversationRow {
  id: number;
  channel: Channel;
  status: "open" | "handoff" | "closed";
  outcome: string;
  handoff: boolean;
  handoff_summary: string;
  client: { id: number; name: string; phone: string; ig: string };
  last_message: string;
  last_sender: string;
  last_message_at: string;
  message_count: number;
}

export interface MessageRow {
  id: number;
  direction: "in" | "out";
  sender: "client" | "ai" | "staff" | "system";
  text: string;
  at: string;
}

export interface Appointment {
  id: number;
  start: string;
  end: string;
  when: string;
  status: string;
  price: number;
  booked_by_ai: boolean;
  source: string;
  deposit_status: string;
  deposit_url: string;
  client: { id: number; name: string; phone: string };
  service: { id: number; name: string; duration_min: number };
  stylist: { id: number; name: string; color: string };
  created_at: string;
}

export interface ConversationDetail extends ConversationRow {
  messages: MessageRow[];
  upcoming: Appointment[];
  traces: { id: number; model: string; tool_calls: { name: string; input?: unknown; error?: string }[]; input_tokens: number; output_tokens: number; latency_ms: number; error: string; at: string }[];
}

export interface ClientRow {
  id: number;
  name: string;
  phone: string;
  ig: string;
  email: string;
  opt_in: boolean;
  notes: string;
  preferred_stylist: string | null;
  preferred_stylist_id: number | null;
  visits: number;
  lifetime_value: number;
  last_visit: string | null;
  last_service: string | null;
  next_visit: string | null;
  visit_interval_days: number | null;
  due_for_rebook: boolean;
  last_nudged_at: string | null;
}

export interface Service {
  id: number;
  name: string;
  category: string;
  description: string;
  duration_min: number;
  price: number;
  deposit_required: boolean;
  deposit_amount: number;
  stylist_ids: number[];
  rebook_interval_days: number | null;
  active: boolean;
}

export interface Stylist {
  id: number;
  name: string;
  specialties: string;
  color: string;
  active: boolean;
}

export interface Salon {
  id: number;
  name: string;
  phone: string;
  address: string;
  timezone: string;
  voice_tone: string;
  policies: string;
  faq: string;
  hours: Record<string, [number, number] | null>;
  quiet_hours_start: number;
  quiet_hours_end: number;
  handoff_phone: string;
  avg_ticket: number;
  plan: string;
  ai_paused: boolean;
  booking_platform: string;
  sms_number: string;
  ig_account_id: string;
}

export interface WaitlistRow {
  id: number;
  client: { id: number; name: string; phone: string };
  service: string;
  service_id: number;
  stylist: string | null;
  preferred_times: string;
  flexible: boolean;
  created_at: string;
}

export interface RefillOffer {
  id: number;
  start: string;
  when: string;
  stylist: string;
  status: "open" | "filled" | "expired";
  contacted: number;
  filled_by: string | null;
  created_at: string;
}

export interface OutboxRow {
  id: number;
  channel: string;
  to: string;
  text: string;
  purpose: string;
  status: string;
  at: string;
}
