import { useEffect, useId, useRef, useState } from "react";
import { Check, Copy } from "lucide-react";

interface DraftInquiryProps {
  text: string;
}

type CopyState = "idle" | "copied" | "failed";

export function DraftInquiry({ text }: DraftInquiryProps) {
  const [state, setState] = useState<CopyState>("idle");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const textareaId = useId();
  const noteId = useId();

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  async function copy() {
    let ok = false;
    try {
      if (navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
        ok = true;
      } else if (textareaRef.current) {
        textareaRef.current.select();
        ok = document.execCommand("copy");
      }
    } catch {
      ok = false;
    }
    setState(ok ? "copied" : "failed");
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setState("idle"), 2000);
  }

  const rows = Math.min(14, Math.max(6, text.split("\n").length + 1));

  return (
    <div>
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <label htmlFor={textareaId} className="text-[13px] font-medium">
          Message to the employer
        </label>
        <div className="flex items-center gap-2">
          <span aria-live="polite" className={`text-[12px] font-medium ${state === "failed" ? "text-bad" : "text-ink-2"}`}>
            {state === "copied" ? "Copied" : state === "failed" ? "Copy failed — select the text manually" : ""}
          </span>
          <button type="button" className="btn-secondary" onClick={copy}>
            {state === "copied" ? <Check aria-hidden="true" className="size-3.5" /> : <Copy aria-hidden="true" className="size-3.5" />}
            Copy
          </button>
        </div>
      </div>
      <textarea
        id={textareaId}
        ref={textareaRef}
        readOnly
        value={text}
        rows={rows}
        aria-describedby={noteId}
        className="border-line-strong bg-subtle text-ink focus:border-accent w-full resize-y rounded-lg border p-3 font-mono text-[12.5px] leading-relaxed outline-none focus:ring-2 focus:ring-[#2448e0]/20"
      />
      <p id={noteId} className="text-ink-2 mt-1 text-[12px]">
        We never contact employers. Edit before sending.
      </p>
    </div>
  );
}
