import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output for the Docker image: `next build` emits a
  // self-contained server (server.js + traced node_modules) so the runtime
  // stage ships without the full dependency tree. Local `pnpm dev`/`pnpm
  // start` behavior is unchanged.
  output: "standalone",
};

export default nextConfig;
