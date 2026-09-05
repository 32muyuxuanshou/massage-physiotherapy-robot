FROM node:22.22.0-alpine AS builder
WORKDIR /app
COPY . .

RUN npm cache clean --force
RUN npm install 

RUN npm run build

FROM nginx:alpine

# 复制自定义的 Nginx 配置文件到容器内
COPY nginx.conf /etc/nginx/nginx.conf
COPY nginx-default.conf /etc/nginx/conf.d/default.conf

COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
    