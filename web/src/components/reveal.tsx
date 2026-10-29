import type { ReactNode } from "react";

/** Server content stays visible; optional CSS entrances respect reduced motion. */
export function Reveal({ children, delay = 0, immediate = false, className }: {
  children: ReactNode; delay?: number; immediate?: boolean; className?: string;
}) {
  return <div className={`${immediate ? "animate-rise " : ""}${className ?? ""}`}
    style={immediate ? { animationDelay: `${delay}s` } : undefined}>{children}</div>;
}
