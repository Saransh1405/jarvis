import { MaterialIcon } from "../MaterialIcon";

function Panel({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={`rounded-2xl border border-white/10 bg-surface-container-low/80 backdrop-blur-sm shadow-[inset_0_1px_0_rgba(255,255,255,0.06)] ${className}`}
    >
      {children}
    </div>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="font-label-sm text-label-sm text-primary/90 font-mono tracking-widest uppercase mb-3">{children}</p>
  );
}

export function LandingStatsRow() {
  const stats = [
    { label: "Neural latency", value: "12ms" },
    { label: "Data retention", value: "100% zero-loss" },
    { label: "Computing load", value: "0.04% idle" },
    { label: "Node aperture", value: "Mandatory" },
  ];
  return (
    <div className="w-full max-w-5xl mx-auto grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4 mt-14">
      {stats.map((s) => (
        <Panel key={s.label} className="px-4 py-5 text-center">
          <p className="font-label-sm text-label-sm text-on-surface-variant uppercase tracking-wider">{s.label}</p>
          <p className="font-headline-md text-headline-sm text-on-surface mt-2 font-semibold">{s.value}</p>
        </Panel>
      ))}
    </div>
  );
}

export function CapabilitiesSection() {
  return (
    <section id="features" className="relative z-10 px-gutter py-20 sm:py-28 max-w-6xl mx-auto">
      <div className="text-center max-w-3xl mx-auto mb-14">
        <SectionLabel>Capabilities // matrix</SectionLabel>
        <h2 className="font-headline-lg text-2xl sm:text-3xl md:text-4xl font-bold text-on-surface">
          Engineered for{" "}
          <span className="text-primary-container">zero friction</span> existence.
        </h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-4">
          Every interaction is mapped, synthesized, and placed at your disposal before you even ask.
        </p>
      </div>

      <div className="grid md:grid-cols-2 gap-4 sm:gap-6">
        <Panel className="p-6 sm:p-8 md:col-span-1">
          <h3 className="font-headline-md text-headline-sm font-semibold mb-4">Remembers everything.</h3>
          <div className="relative h-48 rounded-xl border border-primary-container/20 bg-[#0a0c0f] overflow-hidden">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_center,rgba(25,227,255,0.12),transparent_70%)]" />
            <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-16 h-16 rounded-full border-2 border-primary-container flex items-center justify-center font-label-sm text-label-sm text-primary font-mono">
              CORE.THP
            </div>
            {[
              { t: "Mom's 50th Birthday", x: "12%", y: "18%" },
              { t: "Smartlight Coffee Break", x: "58%", y: "22%" },
              { t: "Lease renewal window", x: "8%", y: "68%" },
              { t: "Dentist follow-up", x: "62%", y: "72%" },
            ].map((n) => (
              <div
                key={n.t}
                className="absolute px-2 py-1 rounded-md bg-surface-container-high/90 border border-white/10 font-label-sm text-[9px] sm:text-label-sm text-on-surface-variant max-w-[42%]"
                style={{ left: n.x, top: n.y }}
              >
                {n.t}
              </div>
            ))}
            <svg className="absolute inset-0 w-full h-full opacity-40" aria-hidden>
              <line x1="50%" y1="50%" x2="20%" y2="25%" stroke="#19E3FF" strokeWidth="1" />
              <line x1="50%" y1="50%" x2="72%" y2="28%" stroke="#19E3FF" strokeWidth="1" />
              <line x1="50%" y1="50%" x2="18%" y2="75%" stroke="#19E3FF" strokeWidth="1" />
              <line x1="50%" y1="50%" x2="78%" y2="78%" stroke="#19E3FF" strokeWidth="1" />
            </svg>
          </div>
          <p className="font-body-sm text-body-sm text-on-surface-variant mt-4">Real-time Memory Matrix — events linked to your core timeline.</p>
        </Panel>

        <Panel className="p-6 sm:p-8">
          <h3 className="font-headline-md text-headline-sm font-semibold mb-4">Reminds you where you are.</h3>
          <div className="space-y-3">
            <div className="flex gap-3 p-3 rounded-xl bg-surface-container-high/60 border border-white/5">
              <MaterialIcon name="location_on" className="text-primary-container text-xl shrink-0" />
              <div>
                <p className="font-body-sm text-body-sm font-medium">Dentist — 2:30 PM</p>
                <p className="font-label-sm text-label-sm text-on-surface-variant mt-1">124 Market St · Room 4B</p>
              </div>
            </div>
            <div className="p-3 rounded-xl border border-amber-500/30 bg-amber-950/20">
              <p className="font-label-sm text-label-sm text-amber-200/90 font-mono">TRAFFIC // I-90</p>
              <p className="font-body-sm text-body-sm mt-2">
                Heavy delay detected. Leave in <span className="text-primary-container font-semibold">20 min</span> to arrive on time.
              </p>
              <div className="flex gap-2 mt-4">
                <button type="button" className="px-3 py-1.5 rounded-lg border border-white/15 font-label-sm text-label-sm hover:bg-white/5">
                  Reschedule
                </button>
                <button type="button" className="px-3 py-1.5 rounded-lg bg-primary-container/20 text-primary font-label-sm text-label-sm border border-primary-container/40">
                  Send to Phone
                </button>
              </div>
            </div>
          </div>
        </Panel>

        <Panel className="p-6 sm:p-8">
          <h3 className="font-headline-md text-headline-sm font-semibold mb-4">Ask your own files.</h3>
          <div className="rounded-xl border border-white/10 bg-surface-container-high/50 p-4">
            <div className="flex items-center gap-2 font-label-sm text-label-sm text-on-surface-variant">
              <MaterialIcon name="picture_as_pdf" className="text-red-400/80" />
              lease_agreement_2024.pdf
            </div>
            <div className="mt-4 space-y-2">
              <div className="rounded-lg bg-surface-container px-3 py-2 font-body-sm text-body-sm text-on-surface-variant">
                When do I actually get my deposit back?
              </div>
              <div className="rounded-lg border border-primary-container/30 bg-primary-container/5 px-3 py-2 font-body-sm text-body-sm">
                Clause 14: deposit returned within 30 days after move-out inspection, minus documented damages.
              </div>
            </div>
          </div>
        </Panel>

        <Panel className="p-6 sm:p-8">
          <h3 className="font-headline-md text-headline-sm font-semibold mb-4">Just talk. No prompt-craft.</h3>
          <div className="flex items-end justify-center gap-1 h-16 mb-4">
            {Array.from({ length: 24 }).map((_, i) => (
              <span
                key={i}
                className="w-1 rounded-full bg-primary-container/80 animate-pulse"
                style={{
                  height: `${20 + Math.sin(i * 0.8) * 18 + (i % 3) * 8}px`,
                  animationDelay: `${i * 0.05}s`,
                }}
              />
            ))}
          </div>
          <div className="flex items-center gap-3 p-3 rounded-xl border border-white/10 bg-surface-container-high/40">
            <MaterialIcon name="check_circle" className="text-primary-container" />
            <p className="font-body-sm text-body-sm">Pick up prescription at CVS — added to today&apos;s queue.</p>
          </div>
        </Panel>

        <Panel className="p-6 sm:p-8">
          <h3 className="font-headline-md text-headline-sm font-semibold mb-4">You stay in control.</h3>
          <div className="rounded-xl border-2 border-red-500/40 bg-red-950/15 p-4">
            <p className="font-label-sm text-label-sm text-red-300 font-mono tracking-wider">CRITICAL ACTION REQUIRED</p>
            <p className="font-body-sm text-body-sm mt-3 text-on-surface">
              Reschedule calendar block — you&apos;re running 20m behind due to traffic. Proposed: shift &quot;Design review&quot; by 25 minutes.
            </p>
            <div className="flex flex-wrap gap-2 mt-5">
              <button type="button" className="px-4 py-2 rounded-lg border border-white/20 font-label-md text-label-md">
                Reject Action
              </button>
              <button type="button" className="px-4 py-2 rounded-lg bg-primary-container text-on-primary-container font-label-md text-label-md shadow-[0_0_16px_rgba(25,227,255,0.4)]">
                Approve &amp; Reschedule
              </button>
            </div>
          </div>
        </Panel>

        <Panel className="p-6 sm:p-8">
          <h3 className="font-headline-md text-headline-sm font-semibold mb-4">Your morning brief.</h3>
          <ul className="space-y-2 font-body-sm text-body-sm">
            {["Finish Shard code", "Dentist appt · 2:30 PM", "Order flowers for Mom"].map((item) => (
              <li key={item} className="flex items-center gap-2 py-2 border-b border-white/5 last:border-0">
                <span className="w-1.5 h-1.5 rounded-full bg-primary-container shrink-0" />
                {item}
              </li>
            ))}
          </ul>
          <div className="mt-4 flex items-center justify-between rounded-lg bg-surface-container-high/50 px-3 py-2 font-label-sm text-label-sm text-on-surface-variant">
            <span className="flex items-center gap-1">
              <MaterialIcon name="partly_cloudy_day" className="text-primary" />
              68°F · Partly cloudy
            </span>
            <span>Day overview · 4h 20m focus</span>
          </div>
        </Panel>
      </div>
    </section>
  );
}

export function CopilotSection() {
  const presets = ["What's my coffee order?", "Reschedule dentist", "Summarize yesterday", "Draft a quick reply"];
  return (
    <section id="how-it-works" className="relative z-10 px-gutter py-20 border-t border-white/5">
      <div className="max-w-6xl mx-auto grid lg:grid-cols-2 gap-12 lg:gap-16 items-start">
        <div>
          <SectionLabel>Persistent co-pilot</SectionLabel>
          <h2 className="font-headline-lg text-2xl sm:text-3xl font-bold leading-tight">
            Not another chat box. An actual{" "}
            <span className="text-primary-container">persistent co-pilot</span>.
          </h2>
          <ul className="mt-8 space-y-4">
            {[
              { icon: "psychology", title: "Autonomous recall", desc: "Context follows you across days, devices, and tasks." },
              { icon: "shield", title: "Zero data resale", desc: "Your memory graph stays yours — no training on your life." },
              { icon: "mic", title: "Voice-first speed", desc: "Speak naturally; JARVIS handles structure and follow-through." },
              { icon: "bolt", title: "Sub-second execution", desc: "Actions queued with approval gates when it matters." },
            ].map((f) => (
              <li key={f.title} className="flex gap-4">
                <span className="w-10 h-10 rounded-xl bg-primary-container/10 border border-primary-container/30 flex items-center justify-center shrink-0">
                  <MaterialIcon name={f.icon} className="text-primary-container" />
                </span>
                <div>
                  <p className="font-headline-sm text-headline-sm font-semibold">{f.title}</p>
                  <p className="font-body-sm text-body-sm text-on-surface-variant mt-1">{f.desc}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>

        <Panel className="p-6 font-mono">
          <p className="font-label-sm text-label-sm text-primary tracking-widest mb-4">POP &amp; QUERY // LIVE I/O</p>
          <div className="flex flex-wrap gap-2 mb-4">
            {presets.map((p) => (
              <button
                key={p}
                type="button"
                className="px-3 py-1.5 rounded-lg border border-white/15 bg-surface-container-high/80 font-label-sm text-[10px] sm:text-label-sm text-on-surface-variant hover:border-primary-container/50 hover:text-primary transition-colors text-left"
              >
                {p}
              </button>
            ))}
          </div>
          <div className="min-h-[140px] rounded-xl bg-[#050608] border border-white/10 p-4 font-label-sm text-label-sm text-on-surface-variant leading-relaxed">
            <span className="text-primary">&gt;</span> Click any preset above to observe instantaneous neural retrieval.
            <span className="inline-block w-2 h-4 ml-1 bg-primary-container/80 animate-pulse align-middle" />
          </div>
        </Panel>
      </div>
    </section>
  );
}

type LandingFooterProps = {
  onGetStarted: () => void;
  onSignIn: () => void;
};

export function LandingFooter({ onGetStarted, onSignIn }: LandingFooterProps) {
  return (
    <footer id="faq" className="relative z-10 px-gutter pt-20 pb-10 border-t border-white/10">
      <div className="max-w-3xl mx-auto text-center">
        <SectionLabel>Initialize</SectionLabel>
        <h2 className="font-headline-xl text-3xl sm:text-4xl font-bold">Meet your JARVIS.</h2>
        <p className="font-body-md text-body-md text-on-surface-variant mt-4 max-w-xl mx-auto">
          Experience the clarity of having an omniscient digital confidant. Free during early protocol access.
        </p>
        <div className="flex flex-col sm:flex-row items-center justify-center gap-3 mt-10">
          <button
            type="button"
            onClick={onGetStarted}
            className="w-full sm:w-auto px-8 py-4 rounded-xl bg-primary-container text-on-primary-container font-headline-md text-headline-sm shadow-[0_0_32px_rgba(25,227,255,0.55)] hover:scale-[1.02] transition-transform"
          >
            Initialize Your Neural Link
          </button>
          <button
            type="button"
            onClick={onSignIn}
            className="w-full sm:w-auto px-8 py-4 rounded-xl border border-white/20 font-headline-md text-headline-sm hover:bg-white/5 transition-colors"
          >
            Sign In
          </button>
        </div>
        <div className="flex flex-wrap justify-center gap-6 mt-12 font-label-sm text-label-sm text-on-surface-variant">
          <span className="flex items-center gap-1">
            <MaterialIcon name="verified_user" className="text-primary text-base" />
            Zero data resale
          </span>
          <span className="flex items-center gap-1">
            <MaterialIcon name="lock" className="text-primary text-base" />
            E2EE encrypted
          </span>
          <span className="flex items-center gap-1">
            <MaterialIcon name="database" className="text-primary text-base" />
            Local-first vault
          </span>
        </div>
        <p className="font-label-sm text-label-sm text-on-surface-variant/60 mt-10 tracking-widest uppercase">
          © JARVIS Quantum Systems // All protocols reserved
        </p>
      </div>
    </footer>
  );
}
