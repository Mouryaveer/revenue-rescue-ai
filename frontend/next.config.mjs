/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000",
    NEXT_PUBLIC_APP_MODE: process.env.NEXT_PUBLIC_APP_MODE ?? "simulation",
    NEXT_PUBLIC_LLM_PROVIDER: process.env.LLM_PROVIDER ?? "mock",
  },
};

export default nextConfig;
