import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",       // small production image (see Dockerfile)
  poweredByHeader: false,
  reactStrictMode: true,
};

export default config;
