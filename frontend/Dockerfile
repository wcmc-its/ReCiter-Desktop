FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
# Next.js evaluates next.config.mjs at build time and bakes the
# rewrites into the standalone server. The compose file passes this
# build arg so the proxy target is correct in the built image.
ARG API_INTERNAL_URL=http://api:8090
ENV API_INTERNAL_URL=${API_INTERNAL_URL}
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000

CMD ["node", "server.js"]
