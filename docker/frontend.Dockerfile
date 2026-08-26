FROM node:20-alpine

WORKDIR /app

# Install dependencies first for better layer caching
COPY frontend/package.json ./
RUN npm install --legacy-peer-deps

# Source is mounted as volume at runtime
EXPOSE 3000
CMD ["npm", "run", "dev"]
