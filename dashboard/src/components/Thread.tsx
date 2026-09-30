"use client";

import clsx from "clsx";
import { Sparkles } from "lucide-react";
import { useEffect, useRef } from "react";
import type { MessageRow } from "@/lib/api";

function linkify(text: string) {
  const parts = text.split(/(https?:\/\/\S+)/g);
  return parts.map((p, i) =>
    /^https?:\/\//.test(p) ? (
      <a key={i} href={p} target="_blank" rel="noreferrer" className="break-all underline underline-offset-2">
        {p}
      </a>
    ) : (
      p
    ),
  );
}

/** perspective="salon": salon messages on the right (inbox). "client": the client's on the right (phone preview). */
export function Bubbles({
  messages,
  typing,
  dense,
  perspective = "salon",
}: {
  messages: MessageRow[];
  typing?: boolean;
  dense?: boolean;
  perspective?: "salon" | "client";
}) {
  const flip = perspective === "client";
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => {
    end.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, typing]);

  return (
    <div className={clsx("flex flex-col", dense ? "gap-1.5" : "gap-2.5")}>
      {messages.map((m, i) => {
        const out = m.direction === "out";
        const prev = messages[i - 1];
        const showLabel = out && (!prev || prev.sender !== m.sender);
        const right = flip ? !out : out;
        return (
          <div key={m.id} className={clsx("animate-fade-up flex flex-col", right ? "items-end" : "items-start")}>
            {showLabel && (
              <span className="mb-1 flex items-center gap-1 px-1 text-[11px] font-medium text-muted">
                {m.sender === "ai" ? (
                  <>
                    <Sparkles size={11} className="text-rose" /> FullChair
                  </>
                ) : (
                  "Your team"
                )}
              </span>
            )}
            <div
              className={clsx(
                "max-w-[82%] rounded-[20px] px-3.5 py-2 text-[14px] leading-relaxed whitespace-pre-wrap",
                right ? "rounded-br-md" : "rounded-bl-md",
                !out && !flip && "bg-canvas text-ink ring-1 ring-line",
                !out && flip && "bg-sky text-white",
                out && m.sender === "ai" && (flip ? "bg-canvas text-ink ring-1 ring-line" : "bg-rose text-white"),
                out && m.sender === "staff" && (flip ? "bg-canvas text-ink ring-1 ring-line" : "bg-ink text-white"),
              )}
            >
              {linkify(m.text)}
            </div>
          </div>
        );
      })}
      {typing && (
        <div className={clsx("flex", flip ? "justify-start" : "justify-end")}>
          <div className="flex gap-1 rounded-[20px] rounded-bl-md bg-canvas px-4 py-3 ring-1 ring-line">
            {[0, 1, 2].map((i) => (
              <span key={i} className="typing-dot h-1.5 w-1.5 rounded-full bg-muted" style={{ animationDelay: `${i * 0.15}s` }} />
            ))}
          </div>
        </div>
      )}
      <div ref={end} />
    </div>
  );
}
