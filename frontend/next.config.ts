import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  async redirects() {
    return [
      { source: "/matchup", destination: "/dashboard", permanent: false },
      { source: "/waivers", destination: "/players", permanent: false },
    ];
  },
  images: {
    remotePatterns: [{ protocol: "https", hostname: "sleepercdn.com" }],
  },
};

export default nextConfig;
