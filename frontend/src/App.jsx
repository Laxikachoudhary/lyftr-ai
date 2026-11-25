
import { useState, useEffect } from "react";
import "./App.css";

// Local backend for development; Render backend for deployment
const API = (
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"
).replace(/\/$/, "");

function App() {
  const [sessions, setSessions] = useState([]);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  // Load all conversations when the app opens
  useEffect(() => {
    initializeApp();
  }, []);

  const initializeApp = async () => {
    try {
      const res = await fetch(`${API}/sessions`);
      if (!res.ok) throw new Error("Could not load conversations");

      const data = await res.json();
      const savedSessions = data.sessions || [];

      setSessions(savedSessions);

      const savedId = localStorage.getItem("lyftr_session_id");

      if (savedId && savedSessions.some(s => s.session_id === savedId)) {
        setSessionId(savedId);
      } else if (savedSessions.length > 0) {
        setSessionId(savedSessions[0].session_id);
      } else {
        await createNewChat();
      }
    } catch (error) {
      console.error("Initialization error:", error);
    }
  };

  // Load messages whenever the selected conversation changes
  useEffect(() => {
    if (!sessionId) return;

    localStorage.setItem("lyftr_session_id", sessionId);
    loadMessages(sessionId);
  }, [sessionId]);

  const loadMessages = async (id) => {
    try {
      const res = await fetch(`${API}/sessions/${id}/messages`);
      if (!res.ok) throw new Error("Could not load messages");

      const data = await res.json();

      setMessages(
        (data.messages || []).map(msg => ({
          role: msg.role,
          content: msg.content,
          metadata: msg.role === "assistant" ? msg : null,
        }))
      );
    } catch (error) {
      console.error("Message loading error:", error);
      setMessages([]);
    }
  };

  // Create a new conversation
  const createNewChat = async () => {
    try {
      const res = await fetch(`${API}/sessions`, {
        method: "POST",
      });

      if (!res.ok) throw new Error("Could not create a new chat");

      const data = await res.json();

      setMessages([]);
      setSessionId(data.session_id);

      setSessions(prev => [
        {
          session_id: data.session_id,
          title: data.title,
          last_message: null,
        },
        ...prev,
      ]);
    } catch (error) {
      console.error("New chat error:", error);
    }
  };

  // Switch between conversations
  const switchChat = (id) => {
    if (loading || id === sessionId) return;
    setSessionId(id);
  };

  // Send a message
  const sendMessage = async (e) => {
    e.preventDefault();

    if (!input.trim() || loading || !sessionId) return;

    const userMessage = input.trim();
    setInput("");

    setMessages(prev => [
      ...prev,
      { role: "user", content: userMessage },
    ]);

    setLoading(true);

    try {
      const res = await fetch(`${API}/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || "Something went wrong");
      }

      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: data.response,
          metadata: data,
        },
      ]);

      // Refresh conversation list after sending
      const historyRes = await fetch(`${API}/sessions`);

      if (historyRes.ok) {
        const historyData = await historyRes.json();
        setSessions(historyData.sessions || []);
      }
    } catch (error) {
      setMessages(prev => [
        ...prev,
        {
          role: "assistant",
          content: `Error: ${error.message}`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app">
      <aside className={`sidebar ${sidebarOpen ? "open" : "closed"}`}>
        <div className="sidebar-header">
          <h2>✦ Lyftr AI</h2>

          <button
            className="icon-button"
            onClick={() => setSidebarOpen(false)}
            title="Close sidebar"
          >
            ×
          </button>
        </div>

        <button className="new-chat-button" onClick={createNewChat}>
          + New Chat
        </button>

        <p className="history-heading">YOUR CONVERSATIONS</p>

        <div className="session-list">
          {sessions.map(session => (
            <button
              key={session.session_id}
              className={`session-item ${
                session.session_id === sessionId ? "active" : ""
              }`}
              onClick={() => switchChat(session.session_id)}
              disabled={loading}
            >
              <span className="session-icon">◷</span>

              <span className="session-title">
                {session.title || "New Chat"}
              </span>
            </button>
          ))}
        </div>

        <div className="sidebar-footer">
          <span>✦</span> Powered by Lyftr AI
        </div>
      </aside>

      <main className="main-area">
        <header className="header">
          {!sidebarOpen && (
            <button
              className="icon-button"
              onClick={() => setSidebarOpen(true)}
              title="Open sidebar"
            >
              ☰
            </button>
          )}

          <span>AI Assistant</span>
          <span className="status">● Online</span>
        </header>

        <section className="chat-container">
          {messages.length === 0 && (
            <div className="welcome">
              <div className="welcome-icon">✦</div>
              <h1>Welcome to Lyftr AI</h1>
              <p>Your intelligent AI assistant. Ask me anything.</p>
            </div>
          )}

          <div className="messages">
            {messages.map((msg, index) => (
              <div key={index} className={`message ${msg.role}`}>
                <strong>
                  {msg.role === "user" ? "You" : "✦ Lyftr AI"}
                </strong>

                <p>{msg.content}</p>

                {msg.metadata && (
                  <small>
                    {msg.metadata.response_source} ·{" "}
                    {msg.metadata.model} ·{" "}
                    {msg.metadata.latency_ms} ms
                  </small>
                )}
              </div>
            ))}

            {loading && (
              <div className="loading">
                Lyftr AI is thinking...
              </div>
            )}
          </div>

          <form className="input-area" onSubmit={sendMessage}>
            <input
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder="Message Lyftr AI..."
              disabled={loading || !sessionId}
            />

            <button
              type="submit"
              disabled={loading || !input.trim() || !sessionId}
            >
              Send ↑
            </button>
          </form>

          <p className="disclaimer">
            Lyftr AI can make mistakes. Verify important information.
          </p>
        </section>
      </main>
    </div>
  );
}

export default App;
