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

        <nav className="hidden items-center gap-6 text-sm text-mist-300 md:flex">
          <Link href="/discover" className="transition-colors hover:text-mist-50">Discover</Link>
          <Link href="/workspace" className="transition-colors hover:text-mist-50">Workspace</Link>
          <Link href="/#showcase" className="transition-colors hover:text-mist-50">
            Showcase
          </Link>
          <Link href="/#method" className="transition-colors hover:text-mist-50">
            Method
          </Link>
          <Link href="/prototypes" className="transition-colors hover:text-mist-50">
            Try a prototype
          </Link>
        </nav>

        {/* Deliberately quiet: this is the operators' door, not a CTA. */}
        <Link
          href="/console"
          className="glass rounded-full px-4 py-1.5 font-mono text-[11px] uppercase tracking-[0.14em] text-mist-500 transition-colors hover:text-maroon-300 hover:border-maroon-700/60"
        >
          Console
        </Link>
      </div>
      <nav aria-label="Mobile product navigation" className="flex justify-center gap-6 border-t border-white/5 bg-ink-950/95 px-4 py-3 text-xs text-mist-300 md:hidden">
        <Link href="/discover">Discover</Link>
        <Link href="/workspace">Review workspace</Link>
        <Link href="/prototypes">Try a prototype</Link>
      </nav>
      {/* Soft gradient scrim so content scrolls away cleanly under the nav */}
      <div className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-ink-950/90 via-ink-950/60 to-transparent" />
    </header>
  );
}
