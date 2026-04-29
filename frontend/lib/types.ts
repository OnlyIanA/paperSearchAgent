export type Role = "user" | "assistant";

export type ChatMessage = {
  id: string;
  role: Role;
  content: string;
};

export type Paper = {
  arxiv_id: string;
  title: string;
  authors: string[];
  abstract: string;
  pdf_url: string;
  source_url: string;
  published?: string | null;
  updated?: string | null;
  categories: string[];
};

export type PaperSummary = {
  arxiv_id: string;
  title: string;
  summary: string;
};

export type MemoryHit = {
  content: string;
  score: number;
  metadata: Record<string, unknown>;
};

export type ChatEvent = {
  type:
    | "session"
    | "status"
    | "memory"
    | "papers"
    | "summary"
    | "token"
    | "warning"
    | "error"
    | "done";
  content?: string | null;
  session_id?: string | null;
  papers?: Paper[] | null;
  summaries?: PaperSummary[] | null;
  memories?: MemoryHit[] | null;
  metadata?: Record<string, unknown>;
};

