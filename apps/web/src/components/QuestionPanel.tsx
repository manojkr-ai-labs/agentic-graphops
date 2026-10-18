import { ArrowRight, Terminal, Zap } from "lucide-react";

export const QUESTIONS = [
  {
    id: "change",
    label: "1 · Likely change",
    text: "The payment service started failing after the latest deployment. Identify the likely change, the downstream systems, the engineer with the strongest relevant history, and the safest next action.",
  },
  {
    id: "memory",
    label: "2 · Last decision",
    text: "A new payment failure looks similar. What did we decide last time, and who should own this?",
  },
  {
    id: "impact",
    label: "3 · What breaks",
    text: "What breaks if the payment service goes down, and which document supports the ownership claim?",
  },
] as const;

interface QuestionPanelProps {
  question: string;
  activeId: string | null;
  running: boolean;
  onQuestion: (value: string, id: string) => void;
  onRun: () => void;
  onNewSession: () => void;
}

export function QuestionPanel({
  question,
  activeId,
  running,
  onQuestion,
  onRun,
  onNewSession,
}: QuestionPanelProps) {
  return (
    <section className="flex w-full shrink-0 flex-col overflow-hidden rounded-xl border border-line bg-panel lg:w-[340px]">
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-2">
          <Terminal size={16} className="text-muted" />
          <h2 className="text-base font-semibold">Question</h2>
          <span className="rounded border border-line bg-canvas px-1.5 font-mono text-[11px] text-muted">
            3 queries
          </span>
        </div>
      </div>
      <div className="flex flex-1 flex-col gap-3 overflow-y-auto p-4">
        <div className="space-y-3 rounded-xl border border-line bg-canvas p-4">
          <div className="space-y-1.5">
            {QUESTIONS.map((preset) => {
              const active = preset.id === activeId;
              return (
                <button
                  key={preset.id}
                  type="button"
                  onClick={() => onQuestion(preset.text, preset.id)}
                  className={`flex h-8 w-full items-center justify-between rounded-md border px-2.5 text-left ${
                    active
                      ? "border-accent bg-accent/20 text-accent"
                      : "border-line bg-panel-2 text-ink hover:bg-hover"
                  }`}
                >
                  <span className="font-mono text-[11px]">{preset.label}</span>
                  <ArrowRight size={14} className={active ? "text-accent" : "text-muted"} />
                </button>
              );
            })}
          </div>
          <div className="rounded-md border border-line bg-canvas p-2.5 focus-within:border-accent">
            <div className="mb-1.5 flex items-center justify-between">
              <span className="text-[11px] font-semibold tracking-[0.04em] text-muted uppercase">
                Investigation query
              </span>
              <span className="font-mono text-[11px] text-accent">Natural language</span>
            </div>
            <textarea
              aria-label="Investigation query"
              rows={5}
              value={question}
              onChange={(event) => onQuestion(event.target.value, "")}
              className="w-full resize-none bg-transparent text-[13px] leading-relaxed text-ink outline-none placeholder:text-faint"
            />
          </div>
          <div className="flex items-center justify-between">
            <button
              type="button"
              onClick={onRun}
              disabled={running || question.trim().length === 0}
              className="flex h-8 items-center gap-1.5 rounded-md bg-accent px-3 text-[11px] font-semibold text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {running ? "Running" : "Run investigation"}
              <Zap size={13} />
            </button>
            <button
              type="button"
              onClick={onNewSession}
              className="flex h-8 items-center rounded-md border border-line bg-panel-2 px-2.5 font-mono text-[11px] text-ink hover:bg-hover"
            >
              New session
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
