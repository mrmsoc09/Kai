# Build stage
FROM node:20-alpine AS build
WORKDIR /app
COPY apps/frontend/package*.json ./
RUN npm ci || npm install
COPY apps/frontend/ ./
RUN npm run build

# Serve stage
FROM nginx:alpine
WORKDIR /usr/share/nginx/html
COPY --from=build /app/dist/ ./
COPY apps/frontend/nginx.conf /etc/nginx/nginx.conf
EXPOSE 8081
CMD ["nginx", "-g", "daemon off;"]
