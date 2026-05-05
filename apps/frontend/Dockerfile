# ── Stage 1: build ───────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci --prefer-offline

COPY . .

# Build args injected at image-build time (docker build --build-arg ...)
ARG VITE_API_URL=https://yourdomain.com
ARG VITE_TELEGRAM_BOT_LINK=https://t.me/YourBotName
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_TELEGRAM_BOT_LINK=$VITE_TELEGRAM_BOT_LINK

RUN npm run build

# ── Stage 2: serve ───────────────────────────────────────────────────────────
FROM nginx:1.25-alpine

# SPA routing: all paths fall back to index.html
COPY nginx-spa.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
