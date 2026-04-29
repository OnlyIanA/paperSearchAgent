# AI Research Assistant

一个完整的 AI 论文研究助手，支持 arXiv 检索、论文总结、短期/长期记忆、Chroma RAG、SQLite 持久化、MCP 工具入口和 Next.js 流式聊天界面。

## 项目结构

```text
paperSearchAgent/
├── backend/
│   ├── app/
│   │   ├── agent.py                         # Agent 编排：工具调用、RAG、记忆、流式回答
│   │   ├── main.py                          # FastAPI 入口
│   │   ├── mcp_server.py                    # MCP stdio server，暴露 arxiv_search
│   │   ├── core/
│   │   │   ├── config.py                    # 环境变量与路径配置
│   │   │   └── llm.py                       # DeepSeek 模型客户端工厂
│   │   ├── memory/
│   │   │   ├── short_term.py                # in-memory conversation buffer
│   │   │   └── sqlite_store.py              # SQLite 长期记忆
│   │   ├── models/
│   │   │   └── schemas.py                   # Pydantic 数据模型
│   │   ├── rag/
│   │   │   ├── local_embeddings.py          # 本地 hashing embedding，无外部 API
│   │   │   └── vector_store.py              # Chroma RAG
│   │   ├── skills/
│   │   │   ├── paper_summary_skill.py       # 论文总结技能
│   │   │   └── conversation_summary_skill.py# 对话压缩技能
│   │   └── tools/
│   │       ├── arxiv.py                     # arXiv Atom API 工具
│   │       ├── cache.py                     # TTL 缓存
│   │       ├── langchain_tools.py           # LangChain StructuredTool 定义
│   │       └── mcp.py                       # MCP 风格工具注册与调用
│   ├── data/                                # SQLite 与 Chroma 本地数据
│   └── requirements.txt
├── frontend/
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx
│   ├── components/
│   │   └── ChatShell.tsx                    # ChatGPT 风格流式聊天 UI
│   ├── lib/
│   │   └── types.ts
│   ├── package.json
│   └── tailwind.config.ts
├── .env.example
├── frontend/.env.local.example
├── Makefile
└── PROJECT_INTRO.md
```

## 核心能力

- `arxiv_search(query)`：通过 arXiv Atom API 检索论文，返回标题、作者、摘要、分类、发布时间、PDF 链接。
- `summarize_paper(paper_text)`：调用 `paper_summary_skill` 用中文总结论文。
- `retrieve_memory(query)`：从 Chroma 中语义检索论文片段、摘要和对话长期记忆。
- 短期记忆：后端内存中的 session conversation buffer。
- 长期记忆：SQLite 保存聊天日志、论文、摘要、记忆；Chroma 保存语义向量。
- DeepSeek：论文总结、对话压缩、最终回答全部通过 DeepSeek API 调用。
- RAG：论文元数据、摘要和技能总结会被切块，用本地 embedding 写入持久化 Chroma，不再调用外部 embedding API。
- MCP：`backend/app/mcp_server.py` 提供 stdio MCP server；后端 Agent 同时通过 MCP 风格 registry 调用 arXiv 工具。
- 流式响应：前端通过 `fetch` 读取 SSE，实时展示 token、论文和摘要。
- 简单缓存：arXiv 检索结果有进程内 TTL 缓存，默认 1 小时。

## 后端启动

```bash
cd /home/jizihe/project/paperSearchAgent
cp .env.example .env
```

编辑 `.env`，填入：

```bash
DEEPSEEK_API_KEY=sk-your-deepseek-api-key
```

安装并启动：

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 1299
```

健康检查：

```bash
curl http://localhost:1299/health
```

查看工具：

```bash
curl http://localhost:1299/api/tools
```

## 前端启动

```bash
cd /home/jizihe/project/paperSearchAgent/frontend
cp .env.local.example .env.local
npm install
npm run dev
```

浏览器打开：

```text
http://localhost:2299
```

## MCP Server

后端也提供一个 stdio MCP server：

```bash
cd /home/jizihe/project/paperSearchAgent/backend
python -m app.mcp_server
```

可用工具：

```text
arxiv_search(query: str, max_results: int = 5)
```

返回字段：

```text
title, authors, abstract, pdf_url, source_url, published, updated, categories
```

## 数据流

```text
User query
  -> FastAPI /api/chat/stream
  -> ResearchAgent
  -> retrieve_memory(query)
  -> 判断是否需要检索
  -> MCP arxiv_search(query)
  -> SQLite 保存论文和聊天日志
  -> paper_summary_skill 总结论文
  -> Chroma 写入论文 chunks / summary memory
  -> DeepSeek 模型结合短期记忆、长期记忆和论文摘要生成回答
  -> SSE 流式返回前端
```

## API 示例

流式聊天：

```bash
curl -N http://localhost:1299/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "message": "检索 diffusion transformer 在图像生成中的最新论文",
    "max_results": 5,
    "top_k": 5
  }'
```

一次性聊天：

```bash
curl http://localhost:1299/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "找几篇 RAG evaluation 的论文"}'
```

## 环境变量

| 变量 | 说明 | 默认值 |
| --- | --- | --- |
| `DEEPSEEK_API_KEY` | DeepSeek API key | 空 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | `https://api.deepseek.com` |
| `DEEPSEEK_MODEL` | DeepSeek 回答与总结模型 | `deepseek-v4-flash` |
| `LOCAL_EMBEDDING_DIMENSIONS` | 本地 embedding 向量维度 | `384` |
| `SQLITE_PATH` | SQLite 文件路径 | `./backend/data/paper_agent.sqlite3` |
| `CHROMA_PERSIST_DIR` | Chroma 持久化目录 | `./backend/data/chroma` |
| `ARXIV_API_URL` | arXiv API 地址 | `https://export.arxiv.org/api/query` |
| `CACHE_TTL_SECONDS` | arXiv 缓存时间 | `3600` |
| `CHUNK_SIZE` | RAG chunk 大小 | `900` |
| `CHUNK_OVERLAP` | RAG chunk overlap | `120` |
| `CORS_ORIGINS` | 前端跨域白名单 | `http://localhost:2299,http://127.0.0.1:2299` |

## 无 API Key 行为

没有配置 `DEEPSEEK_API_KEY` 时，服务仍可启动并可检索 arXiv；论文总结和最终回答会退化为抽取式/规则生成内容。RAG 使用本地 embedding，不依赖任何 embedding API。
