import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1',
  },

  // @ts-ignore
  eslint: {
    ignoreDuringBuilds: true,
  },
};

export default nextConfig;
