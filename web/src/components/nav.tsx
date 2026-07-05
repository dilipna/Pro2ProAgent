import Link from "next/link";

/** Wordmark: sans weight for "Pro…Pro", italic serif ember for the "To". */
export function Wordmark() {
  return (
    <span className="text-[17px] font-semibold tracking-tight text-mist-50">
      Pro
      <span className="font-display italic font-normal text-maroon-300">To</span>
      Pro
    </span>
  );
}

export function Nav() {
  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Link href="/" aria-label="ProToPro home" className="select-none">
          <Wordmark />
        </Link>

        <nav className="hidden items-center gap-8 text-sm text-mist-300 md:flex">
          <a href="#showcase" className="transition-colors hover:text-mist-50">
            Showcase
          </a>
          <a href="#method" className="transition-colors hover:text-mist-50">
            Method
          </a>
          <a href="#pipeline" className="transition-colors hover:text-mist-50">
            Pipeline
          </a>
        </nav>

        {/* Deliberately quiet: this is the operators' door, not a CTA. */}
        <Link
          href="/console"
          className="glass rounded-full px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-mist-500 transition-colors hover:text-maroon-300 hover:border-maroon-700/60"
        >
          Console
        </Link>
      </div>
      {/* Soft gradient scrim so content scrolls away cleanly under the nav */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-ink-950/90 via-ink-950/60 to-transparent" />
    </header>
  );
}
