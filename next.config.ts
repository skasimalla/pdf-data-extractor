import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async rewrites() {
    // In development, proxy /v1/* to the local FastAPI server.
    // In production on Vercel, vercel.json rewrites /v1/* to the Python function.
    if (process.env.NODE_ENV === "development") {
      return [
        {
          source: "/v1/:path*",
          destination: "http://localhost:8000/v1/:path*",
        },
      ];
    }
    return [];
  },
};

export default nextConfig;
