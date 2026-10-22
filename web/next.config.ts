import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for the Docker image: `next build` emits a
  // self-contained server (server.js + traced node_modules) so the runtime
  // stage ships without the full dependency tree. Local `pnpm dev`/`pnpm
  // start` behavior is unchanged.
  output: "standalone",
  async headers() {
    return [{ source: "/demos/decision-desk/:path*", headers: [
      { key: "Content-Security-Policy", value: "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'none'; object-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'none'" },
      { key: "X-Content-Type-Options", value: "nosniff" },
      { key: "Referrer-Policy", value: "no-referrer" },
    ] }];
  },
  turbopack: { root: process.cwd() },
  outputFileTracingRoot: process.cwd(),
};

export default nextConfig;
