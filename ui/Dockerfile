# 使用官方 Node.js镜像作为基础镜像
FROM node:24 AS builder

# 设置工作目录
WORKDIR /app/web

# 将 package.json 和 package-lock.json 拷贝到镜像内
COPY package.json .
COPY package-lock.json .

# 使用 npm ci 精准安装锁定版本依赖
RUN npm ci --ignore-scripts --legacy-peer-deps

# 将项目代码拷贝到容器中
COPY . .

# 配置环境变量（同源相对路径，由外层nginx将/api反代到后端，换域名/IP无需改此处）
ENV VITE_API_PREFIX=/api

#构建/编译项目
RUN npm run build

# 二阶段使用 Nginx 来部署vue 静态页面
FROM nginx:alpine AS production
COPY --from=builder /app/web/dist /usr/share/nginx/html
COPY --from=builder /app/web/docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 设置目录权限为755，确保Nginx可以访问目录
RUN find /usr/share/nginx/html -type d -exec chmod 755 {} \;

# 设置文件权限为 644 ，确保文件可以读但不可执行
RUN find /usr/share/nginx/html -type f -exec chmod 644 {} \;

# 暴露 3000 端口号
EXPOSE 3000

# 启动 Nginx
CMD ["nginx","-g","daemon off;"]
