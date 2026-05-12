/** @type {import('next').NextConfig} */
const nextConfig = {
  output: "standalone",
  async rewrites() {
    // Proxy /api/* to the FastAPI backend so the browser only talks to
    // a single origin (the Next.js port). In docker compose the backend
    // is reachable as http://api:8090 over the service network; in
    // native dev the developer typically runs uvicorn on localhost:8090.
    const target = process.env.API_INTERNAL_URL || "http://localhost:8090";
    return [
      { source: "/api/:path*", destination: `${target}/api/:path*` },
    ];
  },
};

export default nextConfig;
