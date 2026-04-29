"use client";

import {
  BookOpen,
  Brain,
  CircleStop,
  Clock3,
  LoaderCircle,
  MessageSquareText,
  Search,
  Send,
  Sparkles
} from "lucide-react";
import type { FormEvent, ReactNode } from "react";
import { useEffect, useMemo, useRef, useState } from "react";

import type { ChatEvent, ChatMessage, MemoryHit, Paper, PaperSummary } from "@/lib/types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:1299";

type SearchMode = "auto" | "search" | "memory";

const initialMessages: ChatMessage[] = [
  {
    id: "welcome",
    role: "assistant",
    content:
      "你好，我是你的 AI 论文研究助手。可以直接问我一个研究方向，我会检索 arXiv、总结论文，并把结果写入长期记忆。"
  }
];

function createId() {
  return `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function searchModeToPayload(mode: SearchMode) {
  if (mode === "search") return true;
  if (mode === "memory") return false;
  return undefined;
}

export function ChatShell() {
  const [messages, setMessages] = useState<ChatMessage[]>(initialMessages);
  const [input, setInput] = useState("");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState("就绪");
  const [papers, setPapers] = useState<Paper[]>([]);
  const [summaries, setSummaries] = useState<PaperSummary[]>([]);
  const [memories, setMemories] = useState<MemoryHit[]>([]);
  const [searchMode, setSearchMode] = useState<SearchMode>("auto");
  const [maxResults, setMaxResults] = useState(5);
  const [topK, setTopK] = useState(5);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth"
    });
  }, [messages, status]);

  const assistantBusy = useMemo(
    () => isStreaming && status !== "回答完成",
    [isStreaming, status]
  );

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = input.trim();
    if (!text || isStreaming) return;

    const userMessage: ChatMessage = { id: createId(), role: "user", content: text };
    const assistantId = createId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: ""
    };

    setMessages((current) => [...current, userMessage, assistantMessage]);
    setInput("");
    setPapers([]);
    setSummaries([]);
    setMemories([]);
    setStatus("连接后端中...");
    setIsStreaming(true);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const response = await fetch(`${API_BASE_URL}/api/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          max_results: maxResults,
          top_k: topK,
          search: searchModeToPayload(searchMode)
        }),
        signal: controller.signal
      });

      if (!response.ok || !response.body) {
        throw new Error(`HTTP ${response.status}`);
      }

      await readSse(response.body, (eventData) => {
        handleStreamEvent(eventData, assistantId);
      });
      setStatus("回答完成");
    } catch (error) {
      const message = error instanceof Error ? error.message : "未知错误";
      if (message !== "The user aborted a request.") {
        setStatus(`请求失败：${message}`);
        setMessages((current) =>
          current.map((item) =>
            item.id === assistantId
              ? { ...item, content: item.content || `请求失败：${message}` }
              : item
          )
        );
      }
    } finally {
      setIsStreaming(false);
      abortRef.current = null;
    }
  }

  function handleStreamEvent(eventData: ChatEvent, assistantId: string) {
    if (eventData.type === "session" && eventData.session_id) {
      setSessionId(eventData.session_id);
      return;
    }
    if (eventData.type === "status" && eventData.content) {
      setStatus(eventData.content);
      return;
    }
    if (eventData.type === "warning" && eventData.content) {
      setStatus(eventData.content);
      return;
    }
    if (eventData.type === "error" && eventData.content) {
      setStatus(eventData.content);
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? { ...item, content: item.content || eventData.content || "服务端异常" }
            : item
        )
      );
      return;
    }
    if (eventData.type === "memory" && eventData.memories) {
      setMemories(eventData.memories);
      if (eventData.content) setStatus(eventData.content);
      return;
    }
    if (eventData.type === "papers" && eventData.papers) {
      setPapers(eventData.papers);
      if (eventData.content) setStatus(eventData.content);
      return;
    }
    if (eventData.type === "summary" && eventData.summaries) {
      setSummaries((current) => [...current, ...(eventData.summaries ?? [])]);
      return;
    }
    if (eventData.type === "token" && eventData.content) {
      setMessages((current) =>
        current.map((item) =>
          item.id === assistantId
            ? { ...item, content: `${item.content}${eventData.content}` }
            : item
        )
      );
      return;
    }
    if (eventData.type === "done") {
      setStatus("回答完成");
    }
  }

  function stopStreaming() {
    abortRef.current?.abort();
    setIsStreaming(false);
    setStatus("已停止");
  }

  return (
    <main className="min-h-screen bg-paper-bg text-paper-ink">
      <div className="mx-auto grid min-h-screen w-full max-w-[1680px] grid-cols-1 gap-0 lg:grid-cols-[280px_minmax(0,1fr)_380px]">
        <aside className="border-b border-paper-line bg-white/72 px-4 py-4 lg:border-b-0 lg:border-r">
          <div className="flex h-full flex-col gap-5">
            <div>
              <div className="flex items-center gap-2 text-lg font-semibold">
                <Sparkles className="h-5 w-5 text-paper-teal" />
                AI Research
              </div>
              <div className="mt-1 text-sm text-paper-muted">arXiv + Memory + RAG</div>
            </div>

            <section className="space-y-3">
              <SectionTitle icon={<Search className="h-4 w-4" />} title="模式" />
              <div className="grid grid-cols-3 rounded-lg border border-paper-line bg-white p-1">
                {[
                  ["auto", "自动"],
                  ["search", "检索"],
                  ["memory", "记忆"]
                ].map(([value, label]) => (
                  <button
                    key={value}
                    type="button"
                    onClick={() => setSearchMode(value as SearchMode)}
                    className={`h-9 rounded-md text-sm transition ${
                      searchMode === value
                        ? "bg-paper-teal text-white shadow-sm"
                        : "text-paper-muted hover:bg-paper-bg"
                    }`}
                  >
                    {label}
                  </button>
                ))}
              </div>
            </section>

            <section className="space-y-3">
              <SectionTitle icon={<Clock3 className="h-4 w-4" />} title="参数" />
              <label className="block text-sm text-paper-muted">
                论文数
                <input
                  type="number"
                  min={1}
                  max={10}
                  value={maxResults}
                  onChange={(event) => setMaxResults(Number(event.target.value))}
                  className="mt-1 h-10 w-full rounded-md border border-paper-line bg-white px-3 text-paper-ink outline-none focus:border-paper-teal"
                />
              </label>
              <label className="block text-sm text-paper-muted">
                RAG Top-K
                <input
                  type="number"
                  min={1}
                  max={12}
                  value={topK}
                  onChange={(event) => setTopK(Number(event.target.value))}
                  className="mt-1 h-10 w-full rounded-md border border-paper-line bg-white px-3 text-paper-ink outline-none focus:border-paper-teal"
                />
              </label>
            </section>

            <section className="min-h-0 flex-1 space-y-3">
              <SectionTitle icon={<Brain className="h-4 w-4" />} title="长期记忆" />
              <div className="thin-scrollbar max-h-[42vh] space-y-2 overflow-y-auto pr-1">
                {memories.length === 0 ? (
                  <EmptyLine text="暂无匹配记忆" />
                ) : (
                  memories.map((memory, index) => (
                    <article
                      key={`${memory.score}-${index}`}
                      className="rounded-lg border border-paper-line bg-white p-3 text-sm"
                    >
                      <div className="mb-2 font-medium text-paper-teal">
                        score {memory.score.toFixed(3)}
                      </div>
                      <p className="line-clamp-5 text-paper-muted">{memory.content}</p>
                    </article>
                  ))
                )}
              </div>
            </section>
          </div>
        </aside>

        <section className="flex min-h-screen min-w-0 flex-col">
          <header className="flex min-h-16 items-center justify-between border-b border-paper-line bg-white/82 px-4 py-3 backdrop-blur">
            <div className="min-w-0">
              <h1 className="truncate text-lg font-semibold">AI 论文研究助手</h1>
              <div className="mt-1 flex min-w-0 items-center gap-2 text-sm text-paper-muted">
                {assistantBusy ? (
                  <LoaderCircle className="h-4 w-4 animate-spin text-paper-teal" />
                ) : (
                  <MessageSquareText className="h-4 w-4 text-paper-sky" />
                )}
                <span className="truncate">{status}</span>
              </div>
            </div>
          </header>

          <div ref={scrollRef} className="thin-scrollbar flex-1 overflow-y-auto px-4 py-5">
            <div className="mx-auto flex w-full max-w-4xl flex-col gap-4">
              {messages.map((message) => (
                <MessageBubble key={message.id} message={message} streaming={assistantBusy} />
              ))}
            </div>
          </div>

          <form
            onSubmit={handleSubmit}
            className="border-t border-paper-line bg-white/88 px-4 py-4 backdrop-blur"
          >
            <div className="mx-auto flex w-full max-w-4xl items-end gap-2 rounded-lg border border-paper-line bg-white p-2 shadow-soft">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                rows={1}
                placeholder="输入研究问题或论文方向..."
                className="max-h-36 min-h-11 flex-1 resize-none bg-transparent px-3 py-2 text-base outline-none placeholder:text-paper-muted"
              />
              {isStreaming ? (
                <button
                  type="button"
                  onClick={stopStreaming}
                  title="停止"
                  aria-label="停止"
                  className="grid h-11 w-11 place-items-center rounded-md bg-paper-coral text-white transition hover:brightness-95"
                >
                  <CircleStop className="h-5 w-5" />
                </button>
              ) : (
                <button
                  type="submit"
                  title="发送"
                  aria-label="发送"
                  disabled={!input.trim()}
                  className="grid h-11 w-11 place-items-center rounded-md bg-paper-teal text-white transition hover:brightness-95 disabled:cursor-not-allowed disabled:bg-paper-line disabled:text-paper-muted"
                >
                  <Send className="h-5 w-5" />
                </button>
              )}
            </div>
          </form>
        </section>

        <aside className="border-t border-paper-line bg-white/76 px-4 py-4 lg:border-l lg:border-t-0">
          <div className="flex h-full flex-col gap-5">
            <section className="min-h-0 flex-1 space-y-3">
              <SectionTitle icon={<BookOpen className="h-4 w-4" />} title="检索论文" />
              <div className="thin-scrollbar max-h-[45vh] space-y-3 overflow-y-auto pr-1 lg:max-h-[52vh]">
                {papers.length === 0 ? (
                  <EmptyLine text="暂无论文" />
                ) : (
                  papers.map((paper) => <PaperCard key={paper.arxiv_id} paper={paper} />)
                )}
              </div>
            </section>

            <section className="min-h-0 flex-1 space-y-3">
              <SectionTitle icon={<Sparkles className="h-4 w-4" />} title="技能摘要" />
              <div className="thin-scrollbar max-h-[38vh] space-y-3 overflow-y-auto pr-1">
                {summaries.length === 0 ? (
                  <EmptyLine text="暂无摘要" />
                ) : (
                  summaries.map((summary) => (
                    <article
                      key={`${summary.arxiv_id}-${summary.title}`}
                      className="rounded-lg border border-paper-line bg-white p-3"
                    >
                      <h3 className="text-sm font-semibold leading-5">{summary.title}</h3>
                      <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-paper-muted">
                        {summary.summary}
                      </p>
                    </article>
                  ))
                )}
              </div>
            </section>
          </div>
        </aside>
      </div>
    </main>
  );
}

async function readSse(
  body: ReadableStream<Uint8Array>,
  onEvent: (event: ChatEvent) => void
) {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split("\n\n");
    buffer = parts.pop() ?? "";
    for (const part of parts) {
      const dataLine = part
        .split("\n")
        .map((line) => line.trim())
        .find((line) => line.startsWith("data:"));
      if (!dataLine) continue;
      const raw = dataLine.replace(/^data:\s?/, "");
      if (!raw) continue;
      onEvent(JSON.parse(raw) as ChatEvent);
    }
  }
}

function SectionTitle({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="flex items-center gap-2 text-sm font-semibold text-paper-ink">
      <span className="text-paper-teal">{icon}</span>
      {title}
    </div>
  );
}

function EmptyLine({ text }: { text: string }) {
  return (
    <div className="rounded-lg border border-dashed border-paper-line bg-white/62 px-3 py-4 text-center text-sm text-paper-muted">
      {text}
    </div>
  );
}

function MessageBubble({
  message,
  streaming
}: {
  message: ChatMessage;
  streaming: boolean;
}) {
  const isUser = message.role === "user";
  return (
    <article className={`flex ${isUser ? "justify-end" : "justify-start"}`}>
      <div
        className={`max-w-[88%] rounded-lg px-4 py-3 text-[15px] leading-7 shadow-sm ${
          isUser
            ? "bg-paper-teal text-white"
            : "border border-paper-line bg-white text-paper-ink"
        }`}
      >
        <div className="whitespace-pre-wrap break-words">
          {message.content || (streaming ? "正在生成..." : "")}
        </div>
      </div>
    </article>
  );
}

function PaperCard({ paper }: { paper: Paper }) {
  const authors = paper.authors.slice(0, 4).join(", ");
  const authorText = paper.authors.length > 4 ? `${authors} 等` : authors;

  return (
    <article className="rounded-lg border border-paper-line bg-white p-3">
      <div className="mb-2 flex flex-wrap gap-1">
        {paper.categories.slice(0, 3).map((category) => (
          <span
            key={category}
            className="rounded border border-paper-line bg-paper-bg px-2 py-0.5 text-xs text-paper-muted"
          >
            {category}
          </span>
        ))}
      </div>
      <h3 className="text-sm font-semibold leading-5">{paper.title}</h3>
      <p className="mt-2 text-xs leading-5 text-paper-muted">{authorText || "未知作者"}</p>
      <p className="mt-2 line-clamp-5 text-sm leading-6 text-paper-muted">{paper.abstract}</p>
      <div className="mt-3 flex items-center justify-between gap-3 text-xs">
        <span className="truncate text-paper-muted">{paper.arxiv_id}</span>
        <a
          href={paper.pdf_url}
          target="_blank"
          rel="noreferrer"
          className="shrink-0 rounded-md border border-paper-line px-2 py-1 text-paper-sky transition hover:border-paper-sky"
        >
          PDF
        </a>
      </div>
    </article>
  );
}
