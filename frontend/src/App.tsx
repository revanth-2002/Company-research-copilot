import React, { useEffect, useMemo, useRef, useState } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuth } from "@clerk/clerk-react";
import { Bot, Building2, History, Loader2, MessageSquare, Play, Send } from "lucide-react";
// @ts-ignore: side-effect import for CSS file
import "./styles.css";
import Login from "./pages/login";
import Signup from "./pages/signup";
import ProtectedRoute from "./components/ProtectedRoute";

const API_URL = import.meta.env.VITE_API_URL ?? "http://localhost:8001";

type ProgressItem = {
  node: string;
  status: string;
  message: string;
  timestamp: string;
  payload?: Record<string, unknown>;
};

type Session = {
  id: string;
  company_name: string;
  website: string;
  objective: string;
  status: string;
  created_at: string;
  updated_at: string;
  progress?: ProgressItem[];
  report?: Report | null;
  errors?: string[];
  chat?: ChatMessage[];
};

type Report = {
  title: string;
  objective: string;
  quality_score: number;
  sections: Record<string, string | string[] | { title: string; url: string }[]>;
};

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  timestamp: string;
  loading?: boolean;
};

type ChatResponse = {
  answer: string;
};

const sectionLabels: Record<string, string> = {
  company_overview: "Company Overview",
  products_services: "Products & Services",
  target_customers: "Target Customers",
  business_signals: "Business Signals",
  risks_challenges: "Risks & Challenges",
  discovery_questions: "Suggested Discovery Questions",
  outreach_strategy: "Suggested Outreach Strategy",
  unknowns: "Unknowns",
  sources: "Sources",
};

function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <SessionApp />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function SessionApp() {
  const { getToken } = useAuth();
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [active, setActive] = useState<Session | null>(null);
  const [form, setForm] = useState({
    company_name: "ZyLabs",
    website: "https://zylabs.ai",
    objective: "Prepare for a sales discovery meeting with the revenue leadership team.",
  });
  const [chatInput, setChatInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [chatLoading, setChatLoading] = useState(false);
  const [error, setError] = useState("");
  const eventSourceRef = useRef<EventSource | null>(null);
  const chatRef = useRef<HTMLDivElement | null>(null);

  async function request<T>(path: string, options?: RequestInit): Promise<T> {
    const token = await getToken();
    const response = await fetch(`${API_URL}${path}`, {
      ...options,
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...((options?.headers as Record<string, string>) ?? {}),
      },
    });
    if (!response.ok) {
      throw new Error(await response.text());
    }
    return response.json();
  }

  async function loadSessions() {
    const data = await request<Session[]>("/sessions");
    setSessions(data);
    if (!activeId && data.length) setActiveId(data[0].id);
  }

  async function loadActive(id: string) {
    const data = await request<Session>(`/sessions/${id}`);
    setActive(data);
  }

  useEffect(() => {
    loadSessions().catch((err) => setError(err.message));
  }, []);

  useEffect(() => {
    if (!activeId) return;

    loadActive(activeId).catch((err) => setError(err.message));

    eventSourceRef.current?.close();

    getToken().then((token) => {
      const url = new URL(`${API_URL}/sessions/${activeId}/events`);
      if (token) url.searchParams.set("token", token);
      const source = new EventSource(url.toString());
      eventSourceRef.current = source;

      source.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data?.type === "session") {
            setActive(data.session);
          }
        } catch (err) {
          console.error("SSE parse error", err);
        }
      };

      source.onerror = () => {
        source.close();
        eventSourceRef.current = null;
      };
    });

    return () => {
      eventSourceRef.current?.close();
      eventSourceRef.current = null;
    };
  }, [activeId]);

  useEffect(() => {
    chatRef.current?.scrollTo({
      top: chatRef.current.scrollHeight,
      behavior: "smooth",
    });
  }, [active?.chat]);

  async function createSession(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const session = await request<Session>("/sessions", {
        method: "POST",
        body: JSON.stringify({ ...form, auto_run: true }),
      });
      setActiveId(session.id);
      setActive(session);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to create session.");
    } finally {
      setBusy(false);
    }
  }

  async function rerun() {
    if (!active) return;
    await request<Session>(`/sessions/${active.id}/run`, { method: "POST" });
    await loadActive(active.id);
  }

  async function sendChat(event: React.FormEvent) {
    event.preventDefault();
    if (!active || !chatInput.trim() || chatLoading) return;
    const message = chatInput.trim();
    setChatInput("");
    const sessionId = active.id;
    const placeholderTimestamp = `pending-${Date.now()}`;

    setActive((prev) =>
      prev
        ? {
            ...prev,
            chat: [
              ...(prev.chat ?? []),
              { role: "user", content: message, timestamp: new Date().toISOString() },
              { role: "assistant", content: "", timestamp: placeholderTimestamp, loading: true },
            ],
          }
        : prev
    );
    setChatLoading(true);

    try {
      const response = await request<ChatResponse>(`/sessions/${sessionId}/chat`, {
        method: "POST",
        body: JSON.stringify({ message }),
      });

      const answer = response.answer;
      const chunkSize = 20;
      for (let i = 1; i <= answer.length; i += chunkSize) {
        const partial = answer.slice(0, i);
        setActive((prev) =>
          prev
            ? {
                ...prev,
                chat: prev.chat?.map((item) =>
                  item.timestamp === placeholderTimestamp
                    ? { ...item, content: partial }
                    : item
                ),
              }
            : prev
        );
        await new Promise((resolve) => setTimeout(resolve, 40));
      }

      await loadActive(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to send chat.");
      setActive((prev) =>
        prev
          ? {
              ...prev,
              chat: prev.chat?.filter((item) => item.timestamp !== placeholderTimestamp),
            }
          : prev
      );
    } finally {
      setChatLoading(false);
    }
  }

  const workflowSteps = ["planner", "research", "analysis", "quality_check", "report_generation"];
  const completedNodes = useMemo(() => {
    return new Set((active?.progress ?? []).filter((item) => item.status === "complete").map((item) => item.node));
  }, [active]);

  const progressPercent = useMemo(() => {
    if (!active) return 0;
    return Math.round((completedNodes.size / workflowSteps.length) * 100);
  }, [active, completedNodes]);

  const statusMessage = useMemo(() => {
    if (!active) return "";
    if (active.status === "completed") return "Research complete.";
    if (active.status === "failed") return "Workflow failed."

    const runningItem = [...(active.progress ?? [])].reverse().find((item) => item.status === "running");
    const nextIndex = Math.min(completedNodes.size, workflowSteps.length - 1);
    const currentStep = runningItem?.node ?? workflowSteps[nextIndex];
    const labels: Record<string, string> = {
      planner: "Working on planning...",
      research: "Research under process...",
      analysis: "Analyzing the details...",
      quality_check: "Checking report quality...",
      report_generation: "Formatting the final briefing...",
    };
    return labels[currentStep] ?? "Working on the research workflow...";
  }, [active, completedNodes, workflowSteps]);

  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">
          <Bot size={24} />
          <div>
            <strong>Research Copilot</strong>
            <span>ZyLabs</span>
          </div>
        </div>

        <form className="create" onSubmit={createSession}>
          <label>
            Company
            <input
              value={form.company_name}
              onChange={(event) => setForm({ ...form, company_name: event.target.value })}
              required
            />
          </label>
          <label>
            Website
            <input value={form.website} onChange={(event) => setForm({ ...form, website: event.target.value })} required />
          </label>
          <label>
            Research objective
            <textarea
              value={form.objective}
              onChange={(event) => setForm({ ...form, objective: event.target.value })}
              required
            />
          </label>
          <button type="submit" disabled={busy}>
            {busy ? <Loader2 className="spin" size={16} /> : <Play size={16} />}
            Create & Run
          </button>
        </form>

        <div className="history-title">
          <History size={16} />
          Sessions
        </div>
        <div className="sessions">
          {sessions.map((session) => (
            <button
              className={session.id === activeId ? "session active" : "session"}
              key={session.id}
              onClick={() => setActiveId(session.id)}
            >
              <span>{session.company_name}</span>
              <small>{session.status}</small>
            </button>
          ))}
        </div>
      </aside>

      <section className="workspace">
        {error && <div className="error">{error}</div>}
        {!active ? (
          <div className="empty">Create a research session to generate a meeting brief.</div>
        ) : (
          <>
            <header className="session-header">
              <div>
                <p>{active.website}</p>
                <h1>{active.company_name}</h1>
                <span>{active.objective}</span>
              </div>
              <button className="secondary" onClick={rerun}>
                <Play size={16} />
                Run
              </button>
            </header>

            <section className="progress-bar-section">
              <div className="progress-bar-track">
                <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }} />
              </div>
              <div className="progress-bar-labels">
                <span>{progressPercent}% complete</span>
                <span>{statusMessage}</span>
              </div>
            </section>

            <div className="content-grid">
              <section className="report">
                <div className="section-heading">
                  <Building2 size={18} />
                  Briefing Report
                </div>
                {active.status === "running" && !active.report && <LoadingProgress progress={active.progress ?? []} />}
                {active.report ? <ReportView report={active.report} /> : <p className="muted">Report will appear after the graph completes.</p>}
                {!!active.errors?.length && <div className="warning">{active.errors.join("\n")}</div>}
              </section>

              <section className="chat">
                <div className="section-heading">
                  <MessageSquare size={18} />
                  Follow-up Chat
                </div>
                <div ref={chatRef} className="follow-up-chat-scroll">
                  {(active.chat ?? []).map((message, index) => (
                    <div
                      className={`message ${message.role} ${message.loading ? "loading" : ""}`}
                      key={`${message.timestamp}-${index}`}
                    >
                      {message.loading ? <span className="loading-dots">Loading context</span> : message.content}
                    </div>
                  ))}
                  {!active.chat?.length && <p className="muted">Ask about risks, discovery questions, or outreach once the report is ready.</p>}
                </div>
                <div className="chat-composer">
                  <form className="chat-form" onSubmit={sendChat}>
                    <input
                      value={chatInput}
                      onChange={(event) => setChatInput(event.target.value)}
                      placeholder="Ask a follow-up..."
                      disabled={chatLoading}
                    />
                    <button type="submit" disabled={chatLoading || !chatInput.trim()}>
                      <Send size={16} />
                    </button>
                  </form>
                </div>
              </section>
            </div>
          </>
        )}
      </section>
    </main>
  );
}

function LoadingProgress({ progress }: { progress: ProgressItem[] }) {
  return (
    <div className="activity">
      {progress.slice(-5).map((item) => (
        <div key={`${item.node}-${item.timestamp}`}>
          <strong>{item.node.replace("_", " ")}</strong>
          <span>{item.message}</span>
        </div>
      ))}
    </div>
  );
}

function ReportView({ report }: { report: Report }) {
  return (
    <div className="report-body">
      <div className="score">Quality score: {Math.round(report.quality_score * 100)}%</div>
      {Object.entries(report.sections).map(([key, value]) => (
        <article key={key}>
          <h2>{sectionLabels[key] ?? key}</h2>
          {renderValue(value)}
        </article>
      ))}
    </div>
  );
}

function renderValue(value: Report["sections"][string]) {
  if (Array.isArray(value)) {
    return (
      <ul>
        {value.map((item, index) => {
          if (typeof item === "object" && "url" in item) {
            return (
              <li key={item.url}>
                <a href={item.url} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
              </li>
            );
          }
          return <li key={index}>{String(item)}</li>;
        })}
      </ul>
    );
  }
  return <p>{value}</p>;
}

export default App;
