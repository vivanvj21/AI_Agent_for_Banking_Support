import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  // Enable React 19 server components optimizations
  reactStrictMode: true,
  // Image domains for external sources
  images: {
    remotePatterns: [
      { protocol: 'https', hostname: '**' },
    ],
  },
  // Env variables exposed to the browser must be prefixed NEXT_PUBLIC_
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000',
    NEXT_PUBLIC_API_KEY: process.env.NEXT_PUBLIC_API_KEY ?? '',
  },
};

export default nextConfig;
