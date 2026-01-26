# Graph Pivot

Graph Pivot 是一个从 0 到 1 的最小可运行全栈 MVP：用户上传 PDF，后端转换为 Markdown 并拆分章节，再将章节按文本块（chunk）发送给 LLM 提取实体关系，最终生成章节级知识图谱，并在前端可视化展示。

## 功能概览

- PDF 上传与缓存
- PDF -> Markdown 转换
- Markdown 章节识别与懒加载（仅书签/目录）
- 章节内容分块（chunk，按 LLM 类型不同规则）
- 异步 LLM 抽取实体与关系（qwen/gemini）
- JSON Schema 校验与失败重试
- 章节级图谱聚合与可视化
- 章节处理状态实时显示（含超时/跳过/暂停）
- 支持输入历史 book_id 直接加载

## 技术栈

- 后端：Python + FastAPI
- 异步任务：Celery + Redis
- 数据模型：Pydantic
- 数据库：SQLite（默认，可改为 PostgreSQL）
- 前端：Next.js + React
- Markdown 渲染：react-markdown
- 图谱渲染：react-force-graph

## 架构（流水线）

upload -> pdf_to_md -> chapter_split -> chunk_split -> llm_extract -> json_validate -> chapter_graph

所有 LLM 处理都在 Celery 任务中执行，支持失败重试，并进行 JSON Schema 校验。

## 快速开始

### 环境要求

- Python 3.8+
- Node.js 18+
- Redis（本地或 Docker）

### 后端启动

1) 复制并编辑环境变量：

```
copy backend\.env.example backend\.env
```

2) 安装依赖：

```
pip install -r backend/requirements.txt
```

3) 启动 API：

```
uvicorn app.main:app --reload --app-dir backend
```

4) 启动 Celery Worker：

```
cd backend
celery -A app.core.celery_app worker -l info
```

### 前端启动

1) 复制并编辑环境变量：

```
copy frontend\.env.local.example frontend\.env.local
```

2) 安装依赖并启动：

```
cd frontend
npm install
npm run dev
```

3) 访问：

```
http://localhost:3000
```

## 操作流程（从 0 到 1）

1) 打开前端页面 `http://localhost:3000`  
2) 上传一个可复制文本的 PDF（无需 OCR）  
3) 上传后会自动触发处理流程  
4) 左侧章节列表显示处理状态：
   - PENDING（灰色）
   - PROCESSING（蓝色）
   - DONE（绿色）
   - FAILED（红色）
   - SKIPPED_TOO_LARGE（红色）
   - TIMEOUT（红色）
   - PAUSED（灰色）
5) 点击章节查看图谱与对应 Markdown  
6) 点击节点或边，高亮对应证据文本（evidence）
7) 支持输入历史 book_id 直接加载，不重复消耗 LLM

## 环境变量说明

后端 `backend/.env`：

```
LLM_PROVIDER=qwen
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=qwen-plus
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3-flash-preview
LLM_MAX_TOKENS=30000
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
CORS_ORIGINS=http://localhost:3000
BOOK_INACTIVE_SECONDS=60
```

说明：
- 未设置 `LLM_API_KEY` 时，系统会返回一个最小 stub 结果，保证流程可运行。
- `LLM_BASE_URL` 兼容 OpenAI 协议，可改为你的代理或本地模型服务。
- `LLM_PROVIDER` 支持 `qwen`/`gemini`。
- `BOOK_INACTIVE_SECONDS`：前端断开后，书籍处理暂停的超时秒数。

前端 `frontend/.env.local`：

```
NEXT_PUBLIC_API_BASE=http://localhost:8000
```

## API 说明

### 上传 PDF

```
POST /api/books/upload
```

示例：

```
curl -F "file=@./sample.pdf" http://localhost:8000/api/books/upload
```

响应：

```
{
  "book_id": "b_xxx",
  "filename": "sample.pdf"
}
```

### 启动处理流程

```
POST /api/books/{book_id}/process?llm=qwen|gemini
```

### 获取章节列表

```
GET /api/books/{book_id}/chapters
```

### 获取章节 Markdown

```
GET /api/books/{book_id}/chapters/{chapter_id}/md
```

### 获取章节图谱

```
GET /api/books/{book_id}/chapters/{chapter_id}/graph
```

### 获取 PDF

```
GET /api/books/{book_id}/pdf
```

## 核心数据结构

Chapter：

```
{
  "chapter_id": "c01",
  "title": "章节标题",
  "status": "PENDING | PROCESSING | DONE | FAILED | SKIPPED_TOO_LARGE | TIMEOUT | PAUSED"
}
```

Knowledge Graph（章节级）：

```
{
  "chapter_id": "c01",
  "nodes": [
    {"id": "n1", "name": "Transformer", "type": "概念"}
  ],
  "edges": [
    {
      "source": "Transformer",
      "target": "自注意力机制",
      "relation": "包含",
      "evidence": "原文句子",
      "confidence": 0.85
    }
  ]
}
```

注意：node 的 id 由后端生成，LLM 只输出 name/type/relation/evidence。

## 目录结构

```
backend/
  app/
    api/routes/books.py
    core/{config.py, celery_app.py, database.py, schemas.py, json_schema.py}
    models/{book.py, chapter.py, chunk.py, graph.py}
    services/{pdf_service.py, md_service.py, chunk_service.py, llm_service.py, graph_builder.py}
    tasks/pipeline.py
    utils/file_store.py
  requirements.txt

frontend/
  pages/index.tsx
  components/{ChapterList.tsx, GraphView.tsx, ReaderPanel.tsx}
  styles/globals.css
```

## 常见问题

1) 章节一直是 pending/processing  
   - 检查 Redis 是否启动  
   - 检查 Celery worker 是否运行  

2) 图谱为空  
   - PDF 可能是扫描件无文字层  
   - 章节内容为空或目录页码不规范  
   - LLM 未配置或返回失败（查看 worker 日志）  

3) 前端无法访问后端  
   - 确认 `CORS_ORIGINS` 与 `NEXT_PUBLIC_API_BASE` 配置  

4) 章节解析失败  
   - 当前仅支持 PDF 书签/目录页解析章节，未检测到会直接报错  

## GitHub 上传建议

需要提交：
- `backend/`
- `frontend/`
- `README.md`
- `backend/.env.example`
- `frontend/.env.local.example`
- `package.json`/`package-lock.json`

不需要提交（建议加入 .gitignore）：
- `node_modules/`
- `.next/`
- `data/`（运行时生成的 PDF/MD/SQLite）
- `*.db`
- `__pycache__/`
- `.env` / `.env.local`
- `.venv/`

## 备注

- 本项目为最小可运行 MVP，便于新手理解与调试。  
- 后续可扩展：PostgreSQL、多模型路由、章节并行策略、OCR 支持等。  
