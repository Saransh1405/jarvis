import { ArcCoreHero, ArcCoreHologram } from "./ArcCoreHologram";
import {
  CapabilitiesSection,
  CopilotSection,
  LandingFooter,
  LandingStatsRow,
} from "./landing/LandingSections";
import { MaterialIcon } from "./MaterialIcon";

type LandingViewProps = {
  onGetStarted: () => void;
  onSignIn: () => void;
};

const NAV = [
  { label: "Features", href: "#features" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Command core", href: "#command-core" },
  { label: "FAQ", href: "#faq" },
];

function scrollToHash(href: string) {
  const id = href.replace("#", "");
  document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
}

export function LandingView({ onGetStarted, onSignIn }: LandingViewProps) {
  return (
    <div className="min-h-screen bg-[#050608] text-on-surface flex flex-col scroll-smooth">
      <div className="fixed top-0 w-full z-[60] border-b border-white/5 bg-[#030405]/95 backdrop-blur-md">
        <div className="hidden sm:flex h-7 px-gutter items-center justify-between font-label-sm text-[10px] sm:text-label-sm text-on-surface-variant font-mono tracking-wide">
          <span>J.A.R.V.I.S. · VERSION 2.0 · STATUS: ONLINE</span>
          <span className="hidden md:inline">CPU: 22% · RAM: 1.2 GB · DISK: 20%</span>
        </div>
        <header className="h-14 sm:h-16 w-full px-gutter flex items-center justify-between gap-space-md border-t border-white/5">
          <button
            type="button"
            onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
            className="flex items-center gap-space-sm shrink-0"
          >
            <ArcCoreHologram variant="sm" />
            <span className="font-headline-md text-headline-md tracking-tight uppercase text-primary font-bold">JARVIS</span>
          </button>
          <nav className="hidden lg:flex items-center gap-6 font-label-md text-label-md text-on-surface-variant uppercase tracking-wider">
            {NAV.map((item) => (
              <button
                key={item.href}
                type="button"
                onClick={() => scrollToHash(item.href)}
                className="hover:text-primary transition-colors"
              >
                {item.label}
              </button>
            ))}
          </nav>
          <div className="flex items-center gap-2 sm:gap-3">
            <button type="button" className="hidden sm:flex p-2 text-on-surface-variant hover:text-primary" aria-label="Community">
              <MaterialIcon name="forum" />
            </button>
            <button
              type="button"
              onClick={onSignIn}
              className="px-space-md py-1.5 font-label-md text-label-md text-primary border border-primary-container/40 rounded-lg hover:bg-primary-container/10 transition-colors"
            >
              Sign In
            </button>
          </div>
        </header>
        <div className="hidden md:flex h-8 px-gutter items-center justify-between font-label-sm text-label-sm text-on-surface-variant/80 font-mono border-t border-white/5 bg-black/20">
          <span>47.6062° N · 122.3321° W · NODE: WEST-02</span>
          <span>PROTOCOL 12.4.8 · EXPLORE DATASET</span>
        </div>
      </div>

      <main className="flex-1 pt-[7.25rem] sm:pt-[7.75rem] md:pt-[9.5rem] relative overflow-hidden">
        <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(#19e3ff_1px,transparent_1px)] [background-size:32px_32px] opacity-15" />
        <div className="pointer-events-none absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[500px] bg-primary-container/5 blur-[120px] rounded-full" />

        <section id="command-core" className="relative z-10 flex flex-col items-center px-gutter py-12 sm:py-16">
          <ArcCoreHero />
          <div className="flex flex-wrap justify-center gap-2 mb-6">
            <div className="px-space-md py-1.5 rounded-full bg-surface-container-low/90 border border-white/10">
              <p className="font-label-sm text-label-sm text-primary font-mono tracking-wider">SYNC STATUS · OK</p>
            </div>
            <div className="px-space-md py-1.5 rounded-full bg-surface-container-low/90 border border-white/10">
              <p className="font-label-sm text-label-sm text-on-surface-variant font-mono tracking-wider">MEMORY BANK · LIVE</p>
            </div>
          </div>
          <h1 className="font-headline-xl text-3xl sm:text-4xl md:text-5xl lg:text-[3.25rem] text-center font-bold max-w-4xl leading-tight">
            Your <span className="text-primary-container drop-shadow-[0_0_24px_rgba(25,227,255,0.45)]">second brain.</span>
            <br className="hidden sm:block" /> Always on.
          </h1>
          <p className="font-body-lg text-body-md text-on-surface-variant text-center max-w-2xl mt-5 mb-8">
            A futuristic personal AI assistant built for young minds. Remembers everything, briefs your day, never forgets.
          </p>
          <div className="flex flex-col sm:flex-row items-center gap-3">
            <button
              type="button"
              onClick={onGetStarted}
              className="w-full sm:w-auto px-7 py-3.5 rounded-xl bg-primary-container text-on-primary-container font-headline-md text-headline-sm flex items-center justify-center gap-space-sm shadow-[0_0_24px_rgba(25,227,255,0.6)] hover:scale-[1.02] transition-all"
            >
              <MaterialIcon name="bolt" className="text-xl" />
              Get started
            </button>
            <button
              type="button"
              onClick={() => scrollToHash("#features")}
              className="w-full sm:w-auto px-7 py-3.5 rounded-xl border border-white/20 font-headline-md text-headline-sm flex items-center justify-center gap-2 hover:bg-white/5 transition-colors"
            >
              <MaterialIcon name="expand_more" className="text-xl" />
              Explore capabilities
            </button>
          </div>
          <LandingStatsRow />
        </section>

        <CapabilitiesSection />
        <CopilotSection />
        <LandingFooter onGetStarted={onGetStarted} onSignIn={onSignIn} />
      </main>
    </div>
  );
}
