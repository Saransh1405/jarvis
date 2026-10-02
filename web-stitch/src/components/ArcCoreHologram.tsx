import { JARVIS_ARC_CORE } from "../constants";

type ArcCoreHologramProps = {
  /** hero = landing intro; auth = sign-in orb; chat = assistant badge; sm = header mark */
  variant?: "hero" | "auth" | "chat" | "sm";
  className?: string;
  alt?: string;
  animate?: boolean;
};

const imgSize: Record<NonNullable<ArcCoreHologramProps["variant"]>, string> = {
  hero: "w-[58%] h-[58%] max-w-[9rem] max-h-[9rem] md:max-w-[10.5rem] md:max-h-[10.5rem]",
  auth: "w-[70%] h-[70%] max-w-[4.5rem] max-h-[4.5rem]",
  chat: "w-[72%] h-[72%] max-w-[2.25rem] max-h-[2.25rem]",
  sm: "w-[75%] h-[75%] max-w-[1.75rem] max-h-[1.75rem]",
};

const boxSize: Record<NonNullable<ArcCoreHologramProps["variant"]>, string> = {
  hero: "w-48 h-48 md:w-60 md:h-60",
  auth: "w-20 h-20",
  chat: "w-11 h-11",
  sm: "w-9 h-9",
};

function HudRings({ variant }: { variant: NonNullable<ArcCoreHologramProps["variant"]> }) {
  const ringOrigin = "origin-center [transform-box:fill-box]";

  if (variant === "hero") {
    return (
      <svg
        className="absolute inset-0 h-full w-full drop-shadow-[0_0_24px_rgba(25,227,255,0.65)] pointer-events-none"
        viewBox="0 0 100 100"
        fill="none"
        aria-hidden
      >
        <circle
          className={`${ringOrigin} animate-arc-spin-32`}
          cx="50"
          cy="50"
          r="46"
          stroke="#19E3FF"
          strokeDasharray="10 8"
          strokeOpacity="0.4"
          strokeWidth="1.5"
        />
        <circle
          className={`${ringOrigin} animate-arc-spin-18-rev`}
          cx="50"
          cy="50"
          r="38"
          stroke="#19E3FF"
          strokeDasharray="24 16"
          strokeOpacity="0.75"
          strokeWidth="2"
        />
        <circle
          className={`${ringOrigin} animate-arc-spin-10`}
          cx="50"
          cy="50"
          r="30"
          stroke="#19E3FF"
          strokeDasharray="32 10 8 10"
          strokeOpacity="0.9"
          strokeWidth="2.5"
        />
      </svg>
    );
  }

  if (variant === "auth") {
    return (
      <>
        <div className="absolute inset-0 rounded-full border border-dashed border-primary-container/40 animate-arc-spin-18" />
        <div className="absolute inset-1.5 rounded-full border border-primary/20" />
        <div className="absolute inset-3 rounded-full bg-primary-container/20 blur-md" />
      </>
    );
  }

  if (variant === "chat") {
    return (
      <svg className="absolute inset-0 h-full w-full pointer-events-none" viewBox="0 0 100 100" fill="none" aria-hidden>
        <circle
          className={`${ringOrigin} animate-arc-spin-8`}
          cx="50"
          cy="50"
          r="44"
          stroke="#19E3FF"
          strokeDasharray="12 8"
          strokeOpacity="0.5"
          strokeWidth="2.5"
        />
        <polygon
          points="50,22 75,70 25,70"
          stroke="#19E3FF"
          strokeWidth="2"
          fill="none"
          opacity="0.85"
        />
        <circle cx="50" cy="52" r="10" stroke="#19E3FF" strokeWidth="2" fill="none" opacity="0.9" />
      </svg>
    );
  }

  /* sm header mark */
  return (
    <div className="absolute inset-0 rounded-full border border-primary-container/30 animate-arc-spin-18-rev" />
  );
}

export function ArcCoreHologram({
  variant = "hero",
  className = "",
  alt = "JARVIS Arc Core",
  animate = true,
}: ArcCoreHologramProps) {
  return (
    <div
      className={`relative flex shrink-0 items-center justify-center ${boxSize[variant]} ${className}`.trim()}
    >
      {animate ? <HudRings variant={variant} /> : null}
      <img
        src={JARVIS_ARC_CORE}
        alt={alt}
        className={`relative z-10 object-contain drop-shadow-[0_0_20px_rgba(25,227,255,0.85)] ${imgSize[variant]}`}
      />
    </div>
  );
}

/** Large hero with outer glow halo — matches Stitch intro / demo */
export function ArcCoreHero({ className = "" }: { className?: string }) {
  return (
    <div className={`relative mb-8 group ${className}`.trim()}>
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-64 h-64 md:w-80 md:h-80 rounded-full bg-primary-container/20 blur-3xl animate-pulse" />
      <div className="relative transition-transform duration-700 group-hover:scale-105">
        <ArcCoreHologram variant="hero" />
      </div>
    </div>
  );
}
