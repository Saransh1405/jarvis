import { JARVIS_ARC_CORE } from "../constants";

type ArcCoreLogoProps = {
  size?: "sm" | "md" | "lg" | "hero";
  className?: string;
  alt?: string;
};

const sizeClass: Record<NonNullable<ArcCoreLogoProps["size"]>, string> = {
  sm: "h-8 w-8",
  md: "h-12 w-12",
  lg: "h-24 w-24 md:h-28 md:w-28",
  hero: "w-32 h-32 md:w-36 md:h-36",
};

const glowClass: Record<NonNullable<ArcCoreLogoProps["size"]>, string> = {
  sm: "drop-shadow-[0_0_12px_rgba(25,227,255,0.7)]",
  md: "drop-shadow-[0_0_16px_rgba(25,227,255,0.75)]",
  lg: "drop-shadow-[0_0_28px_rgba(25,227,255,0.85)]",
  hero: "drop-shadow-[0_0_28px_rgba(25,227,255,0.9)]",
};

export function ArcCoreLogo({ size = "sm", className = "", alt = "JARVIS Arc Core" }: ArcCoreLogoProps) {
  return (
    <img
      src={JARVIS_ARC_CORE}
      alt={alt}
      className={`object-contain ${sizeClass[size]} ${glowClass[size]} ${className}`.trim()}
    />
  );
}
