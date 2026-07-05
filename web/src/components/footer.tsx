import Link from "next/link";
import { Wordmark } from "./nav";

export function Footer() {
  return (
    <footer className="grain relative border-t hairline">
      <div className="mx-auto max-w-6xl px-6 py-16">
        <div className="flex flex-wrap items-start justify-between gap-10">
          <div className="max-w-xs">
            <Wordmark />
            <p className="mt-4 text-sm leading-relaxed text-mist-500">
              Built by a company of agents.
              <br />
              Supervised by a human.
            </p>
          </div>

          <nav className="flex gap-16 text-sm">
            <div className="flex flex-col gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600">
                Product
              </span>
              <a href="#showcase" className="text-mist-300 transition-colors hover:text-mist-50">
                Showcase
              </a>
              <a href="#method" className="text-mist-300 transition-colors hover:text-mist-50">
                Method
              </a>
            </div>
            <div className="flex flex-col gap-3">
              <span className="font-mono text-[10px] uppercase tracking-[0.16em] text-mist-600">
                Engineering
              </span>
              <Link href="/console" className="text-mist-300 transition-colors hover:text-mist-50">
                Operations console
              </Link>
            </div>
          </nav>
        </div>

        <div className="mt-14 flex flex-wrap items-center justify-between gap-4 border-t hairline pt-8">
          <p className="font-mono text-[11px] text-mist-600">
            © 2026 ProToPro — problems in, products out.
          </p>
          <p className="font-mono text-[10px] uppercase tracking-[0.14em] text-mist-600">
            LangGraph · MCP · Guardrails · Evals
          </p>
        </div>
      </div>
    </footer>
  );
}
