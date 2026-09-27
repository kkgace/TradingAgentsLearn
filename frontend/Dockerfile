# TradingAgents-Calv v3.0 | 教育用途，不构成投资建议
# 构建上下文为仓库根目录（见根目录 docker-compose.yml）
# 阶段一：node 构建前端
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json ./
RUN npm install --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# 阶段二：nginx 托管静态文件并反代 /api、/sse
FROM nginx:alpine
COPY nginx/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
