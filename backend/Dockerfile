FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖 + Node.js (Path A 渲染需要)
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    curl \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY . .

# 创建输出目录和上传目录
RUN mkdir -p /app/output /app/output/tmp /app/uploads

# 安装 html2pptx.js 所需的 Node 模块到独立位置 (/opt/node_libs)
# 运行时 /app/huashu-slides 是 volume 挂载，build-time 的 node_modules 会被覆盖
# 因此安装到 /opt/node_libs 并通过 NODE_PATH 让脚本找到依赖
RUN mkdir -p /opt/node_libs && \
    cd /opt/node_libs && \
    npm init -y > /dev/null 2>&1 && \
    npm install playwright pptxgenjs sharp --save

# 安装 Playwright Chromium 浏览器及其系统依赖 (Path A HTML→PPTX 渲染)
RUN cd /opt/node_libs && npx playwright install --with-deps chromium

# 设置 NODE_PATH 让 require() 能找到全局安装的 node_modules
ENV NODE_PATH=/opt/node_libs/node_modules

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
