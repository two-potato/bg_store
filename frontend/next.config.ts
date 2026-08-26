import path from "node:path";
import type { NextConfig } from "next";

const backendOrigin = (process.env.BACKEND_ORIGIN || "http://backend:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  outputFileTracingRoot: path.join(process.cwd(), ".."),
  async rewrites() {
    return [
      {
        source: "/api/storefront/:path*",
        destination: `${backendOrigin}/api/storefront/:path*`,
      },
      {
        source: "/legacy/:path*",
        destination: `${backendOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
