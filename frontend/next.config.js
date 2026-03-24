/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: "standalone",
  // Skip trailing slash redirects so /api/dashboard/ goes to middleware
  // instead of being 308-redirected to /api/dashboard first
  skipTrailingSlashRedirect: true,
  // API proxying is handled by src/middleware.ts (rewrites don't work in standalone mode)
};

module.exports = nextConfig;
