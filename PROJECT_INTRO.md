# 项目介绍与技术栈

## 项目定位

`paperSearchAgent` 是一个面向 AI 研究工作的全栈论文助手。用户可以在网页端输入研究问题，系统会自动结合短期对话上下文、长期记忆、arXiv 检索结果和向量检索结果，给出中文论文摘要与研究建议。

## 技术栈

| 层级 | 技术 | 用途 |
| --- | --- | --- |
| 前端 | Next.js | App Router 单页聊天工作台 |
| 前端 | React | 流式消息、论文列表、摘要状态管理 |
| 前端 | TailwindCSS | 响应式布局与 UI 样式 |
| 后端 | Python | Agent、工具、记忆、RAG 主逻辑 |
| 后端 | FastAPI | REST API、SSE 流式聊天接口 |
| Agent | LangChain Core + DeepSeek API | DeepSeek Chat 模型、StructuredTool |
| 工具 | arXiv Atom API | 论文检索来源 |
| MCP | mcp Python SDK | stdio MCP server，暴露 `arxiv_search` |
| 向量库 | Chroma | 本地持久化论文 chunks 与长期记忆 |
| LLM API | DeepSeek API | 论文总结、对话压缩、最终回答 |
| Embedding | 本地 hashing embedding | 无外部 API 的向量生成 |
| 短期记忆 | Python in-memory buffer | 当前 session 的对话窗口 |
| 长期记忆 | SQLite | 聊天日志、论文、摘要、记忆元数据 |
| 缓存 | TTL in-process cache | 减少重复 arXiv 查询 |

## 模块说明

### Frontend

前端在 `frontend/` 下，使用 Next.js + React + TailwindCSS。主组件为 `components/ChatShell.tsx`，包含：

- ChatGPT 风格对话流。
- `fetch` + ReadableStream 解析 SSE。
- 左侧显示检索模式、RAG 参数、长期记忆命中。
- 右侧显示 arXiv 检索论文与技能摘要。
- 支持自动检索、强制检索、仅记忆三种模式。

### Backend

后端在 `backend/app/` 下，使用 FastAPI 提供接口：

- `GET /health`：服务健康检查。
- `GET /api/tools`：查看 MCP 工具、LangChain 工具和技能。
- `POST /api/chat/stream`：SSE 流式聊天接口。
- `POST /api/chat`：一次性聚合返回接口。

### Agent System

`app/agent.py` 是主编排层。它按下面顺序工作：

1. 将用户输入写入短期记忆和 SQLite chat logs。
2. 调用 `retrieve_memory` 从 Chroma 检索相关长期记忆。
3. 根据意图判断是否需要搜索 arXiv。
4. 通过 MCP 风格 registry 调用 `arxiv_search`。
5. 保存论文到 SQLite。
6. 调用 `paper_summary_skill` 总结论文。
7. 将论文 chunks 和摘要写入 Chroma。
8. 用 DeepSeek 模型结合上下文生成最终中文回答。
9. 对较长对话调用 `conversation_summary_skill` 写入长期记忆。

### MCP Integration

项目包含两层 MCP 支持：

- `app/tools/mcp.py`：后端内部的 MCP 风格工具 registry，用统一 schema 管理 `arxiv_search` 调用。
- `app/mcp_server.py`：真实 stdio MCP server，可被 MCP client 连接，暴露 `arxiv_search` 工具。

### Memory + RAG

短期记忆由 `ShortTermMemory` 维护，只保存在进程内，适合当前会话上下文。

长期记忆分两部分：

- SQLite：结构化保存论文、摘要、聊天日志和记忆记录。
- Chroma：保存论文 chunk、论文摘要和对话摘要的向量，用于语义检索。

RAG 管线位于 `app/rag/vector_store.py`：

1. 拼接论文标题、作者、分类、摘要、技能总结。
2. 使用 `RecursiveCharacterTextSplitter` 切块。
3. 使用本地 hashing embedding 生成向量，不调用外部 embedding API。
4. 写入本地 persistent Chroma collection。
5. 回答前按 query 检索 top-k 相关 chunks。

## 可扩展点

- 新增工具：在 `backend/app/tools/` 增加工具实现，并在 `langchain_tools.py` 或 MCP registry 中注册。
- 新增技能：在 `backend/app/skills/` 增加 skill class，提供 `name`、`description` 和 `run()`。
- 替换模型：修改 `.env` 中的 `DEEPSEEK_MODEL`。
- 替换向量库：保留 `ChromaRAGStore` 对外方法，替换内部实现即可。

## 运行入口

后端：

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 1299
```

前端：

```bash
cd frontend
npm run dev
```

MCP：

```bash
cd backend
python -m app.mcp_server
```
