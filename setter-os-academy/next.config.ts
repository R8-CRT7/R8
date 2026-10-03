import type { NextConfig } from "next";

// Static export: the prototype runs without any server or paid backend.
// Any free static host (or `npm start` locally) can serve the `out/` folder.
const nextConfig: NextConfig = {
  output: "export",
  trailingSlash: true,
  images: { unoptimized: true },
  poweredByHeader: false,
};

export default nextConfig;
