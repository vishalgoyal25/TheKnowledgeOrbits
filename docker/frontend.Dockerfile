# Build Stage
FROM node:20-alpine AS builder
WORKDIR /app

# Install dependencies (including devDependencies needed for build)
COPY frontend/package*.json ./
RUN npm ci

# Copy source and build
COPY frontend/ .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# Production Stage
FROM node:20-alpine AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Copy necessary files from builder
COPY --from=builder /app/package*.json ./
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/public ./public
COPY --from=builder /app/node_modules ./node_modules

EXPOSE 3000

CMD ["npm", "start"]