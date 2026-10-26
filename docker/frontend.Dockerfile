FROM node:20-alpine

WORKDIR /app
RUN corepack enable && corepack prepare pnpm@10.4.1 --activate

# Install dependencies first for better layer caching
COPY frontend/package.json frontend/pnpm-lock.yaml ./
COPY frontend/patches ./patches
RUN pnpm install --frozen-lockfile

# Source is mounted as volume at runtime
EXPOSE 3000
CMD ["pnpm", "dev"]
