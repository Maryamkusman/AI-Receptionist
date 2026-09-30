import path from "node:path";
import type { NextConfig } from "next";

// Pin the project root so a stray package-lock.json higher up (e.g. in ~) isn't mistaken for it.
const root = path.resolve(__dirname);

const nextConfig: NextConfig = {
  reactStrictMode: true,
  turbopack: { root },
  outputFileTracingRoot: root,
};

export default nextConfig;
