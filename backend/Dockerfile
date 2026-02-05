FROM python:3.11-slim

# 1. 环境变量：建立底层运行规范
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 2. 预构建阶段：解决系统级依赖 (因果：psycopg2 等库需要编译环境)
# 如果你以后需要从源码编译一些包，这里需要安装 gcc, libpq-dev 等
# RUN apt-get update && apt-get install -y --no-install-recommends gcc python3-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt

# 3.升级 pip 并设置国内镜像源（显著提升下载速度，避免超时导致的解析失败）
# 同时增加 --upgrade 确保构建工具是最新的，解决 metadata 报错
RUN pip install --upgrade pip setuptools wheel -i https://pypi.tuna.tsinghua.edu.cn/simple && \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 4. 特殊依赖处理：处理你手动下载的 wheels
COPY backend/wheels /wheels
RUN pip install --no-index --find-links /wheels psycopg2-binary==2.9.9

# 5. 代码层：最后拷贝，利用 Docker 层缓存 (因果：代码改动频繁，依赖改动少)
COPY backend /app

EXPOSE 8000

# 6. 运行指令：生产级部署配置
# 注意：确保 app.main:app 的路径与你的目录结构一致
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "app.main:app", "--bind", "0.0.0.0:8000", "--workers", "2", "--chdir", "/app"]



