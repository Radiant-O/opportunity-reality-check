import { useCallback, useRef, useState } from "react";
import { AnalysisPanel } from "./components/AnalysisPanel";
import { ClarityCheck } from "./components/ClarityCheck";
import { Footer, Header } from "./components/Header";
import { Hero } from "./components/Hero";
import { JobSearch } from "./components/JobSearch";
import { ModeTabs, panelId, tabId, type Mode } from "./components/ModeTabs";
import { DEFAULT_PREFERENCES, PreferencesForm, type Preferences } from "./components/PreferencesForm";
import type { JobSummary } from "./types";

export default function App() {
  const [mode, setMode] = useState<Mode>("candidate");
  // Preferences live in React state only — never persisted.
  const [preferences, setPreferences] = useState<Preferences>(DEFAULT_PREFERENCES);
  const [selectedJob, setSelectedJob] = useState<JobSummary | null>(null);
  const analysisRef = useRef<HTMLDivElement>(null);

  const onSelectJob = useCallback((job: JobSummary) => {
    setSelectedJob(job);
    // On stacked (mobile) layouts, bring the analysis into view.
    if (typeof window !== "undefined" && window.matchMedia?.("(max-width: 1023px)").matches) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      requestAnimationFrame(() => analysisRef.current?.scrollIntoView?.({ behavior: reduce ? "auto" : "smooth", block: "start" }));
    }
  }, []);

  return (
    <div className="flex min-h-screen flex-col">
      <a
        href="#main"
        className="bg-accent sr-only z-50 rounded-md px-3 py-2 text-white focus:not-sr-only focus:fixed focus:top-2 focus:left-2"
      >
        Skip to content
      </a>
      <Header />
      <main id="main" className="mx-auto w-full max-w-[1240px] flex-1 px-4 sm:px-6">
        <Hero />
        <div className="mb-4">
          <ModeTabs mode={mode} onChange={setMode} />
        </div>

        <div role="tabpanel" id={panelId("candidate")} aria-labelledby={tabId("candidate")} hidden={mode !== "candidate"}>
          <div className="grid gap-4 lg:grid-cols-[380px_minmax(0,1fr)] lg:items-start">
            <div className="space-y-4">
              <PreferencesForm value={preferences} onChange={setPreferences} />
              <JobSearch selectedId={selectedJob?.id ?? null} onSelect={onSelectJob} />
            </div>
            <div ref={analysisRef} className="scroll-mt-16">
              <AnalysisPanel job={selectedJob} preferences={preferences} />
            </div>
          </div>
        </div>

        <div role="tabpanel" id={panelId("clarity")} aria-labelledby={tabId("clarity")} hidden={mode !== "clarity"}>
          <ClarityCheck />
        </div>
      </main>
      <Footer />
    </div>
  );
}
