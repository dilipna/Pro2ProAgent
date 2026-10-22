"use client";
import { useState } from "react";
import Link from "next/link";
import { CASES } from "@/lib/cases";
export function RecordedSearch() {
  const [query, setQuery] = useState("");
  const matches = CASES.filter((c) =>
    `${c.id} ${c.title} ${c.insight} ${c.source}`
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );
  return (
    <section id="search" className="mx-auto max-w-6xl px-6 py-20">
      <p className="font-mono text-xs uppercase tracking-widest text-maroon-300">
        Recorded library / browser search
      </p>
      <h2 className="mt-4 text-3xl md:text-4xl">
        Find a problem worth understanding.
      </h2>
      <p className="mt-4 max-w-2xl leading-relaxed text-mist-300">
        Search the bundled project records. This filters existing examples; it
        does not crawl sources, start agents or verify that a previously
        deployed product is still available.
      </p>
      <label
        htmlFor="recorded-search"
        className="mt-8 block text-sm text-mist-300"
      >
        Search recorded problems
      </label>
      <input
        id="recorded-search"
        type="search"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Try cost, evaluation, or review"
        className="mt-3 w-full rounded-xl border border-white/20 bg-ink-900 px-5 py-4 text-mist-50 focus-visible:outline-2 focus-visible:outline-maroon-300"
      />
      <p role="status" className="my-4 text-sm text-mist-300">
        {matches.length} recorded{" "}
        {matches.length === 1 ? "problem" : "problems"}
      </p>
      {matches.length ? (
        <ul className="grid gap-3 md:grid-cols-2">
          {matches.map((c) => (
            <li key={c.id} className="glass rounded-xl p-5">
              <span className="font-mono text-xs text-maroon-300">
                {c.id} · {c.source}
              </span>
              <h3 className="mt-2 text-lg">{c.title}</h3>
              <p className="mt-3 text-sm leading-relaxed text-mist-300">
                {c.insight}
              </p>
              {c.storyHref && (
                <Link
                  href={c.storyHref}
                  className="mt-4 inline-block text-sm text-maroon-300"
                >
                  Read recorded case →
                </Link>
              )}
            </li>
          ))}
        </ul>
      ) : (
        <div className="glass rounded-xl p-6">
          <h3 className="text-xl">No recorded problems match.</h3>
          <button
            type="button"
            onClick={() => setQuery("")}
            className="mt-4 text-maroon-300 underline"
          >
            Clear library search
          </button>
        </div>
      )}
    </section>
  );
}
