# India 3D ULPIN - frontend image (static SPA served by nginx)
FROM node:20-alpine AS build
WORKDIR /app
ARG VITE_API_BASE=/api/v1
ENV VITE_API_BASE=$VITE_API_BASE
COPY package*.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
HEALTHCHECK --interval=20s --timeout=5s --retries=3 \
  CMD wget -q -O - http://localhost/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
