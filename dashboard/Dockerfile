# ── Stage 1: Build React Dashboard ──────────────────────────────────────────
FROM node:18-alpine AS builder

WORKDIR /app

# Copy package files and install dependencies
COPY dashboard/package*.json ./
RUN npm ci

# Copy source and build configurations
COPY dashboard/tsconfig*.json ./
COPY dashboard/vite.config.ts ./
COPY dashboard/tailwind.config.js ./
COPY dashboard/postcss.config.js ./
COPY dashboard/eslint.config.js ./
COPY dashboard/index.html ./
COPY dashboard/src/ ./src/
COPY dashboard/public/ ./public/
COPY dashboard/.env ./

# Build production bundle
RUN npm run build

# ── Stage 2: Serve using Nginx ──────────────────────────────────────────────
FROM nginx:alpine

# Copy custom nginx configuration from root context
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
