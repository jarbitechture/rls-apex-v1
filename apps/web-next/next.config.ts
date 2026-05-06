import type { NextConfig } from "next";

// Static export — required because GitHub Pages can't run a Node server.
// `trailingSlash: true` so each route emits as `/me/index.html` (Pages
// serves directories cleanly that way).
//
// basePath/assetPrefix only on CI: GitHub Pages serves the repo at
// `/rls-apex-v1/`, but local `next dev` and the gateway's static mount
// expect the app at `/`. Detecting via GITHUB_ACTIONS keeps both worlds.
const REPO = "rls-apex-v1";
const isCI = process.env.GITHUB_ACTIONS === "true";

const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  basePath: isCI ? `/${REPO}` : "",
  assetPrefix: isCI ? `/${REPO}/` : "",
  images: { unoptimized: true }, // static export cannot use Image optimization
  turbopack: { root: __dirname }, // multi-lockfile workspace — anchor explicitly
};

export default nextConfig;
