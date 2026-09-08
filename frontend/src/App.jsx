import { useEffect, useRef, useState } from "react";
import "./App.css";

function App() {
  const [messages, setMessages] = useState([
    {
      role: "agent",
      text: "LoanOps Agent ready. Ask me about a loan.",
    },
  ]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);

  const [sessionId, setSessionId] = useState(
    () => crypto.randomUUID()
  );

  const [backendConnected, setBackendConnected] =
    useState(false);

  const messagesEndRef = useRef(null);

  // --------------------------------------------------
  // Check whether backend is reachable
  // --------------------------------------------------

  useEffect(() => {
    async function checkBackend() {
      try {
        const response = await fetch(
          "http://127.0.0.1:8000/health"
        );

        setBackendConnected(response.ok);
      } catch {
        setBackendConnected(false);
      }
    }

    checkBackend();
  }, []);

  // --------------------------------------------------
  // Auto-scroll to newest message
  // --------------------------------------------------

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({
      behavior: "smooth",
    });
  }, [messages, loading]);

  // --------------------------------------------------
  // Send message
  // --------------------------------------------------

  async function handleSubmit(event) {
    event.preventDefault();

    const question = input.trim();

    if (!question || loading) {
      return;
    }

    const userMessage = {
      role: "user",
      text: question,
    };

    setMessages((current) => [
      ...current,
      userMessage,
    ]);

    setInput("");
    setLoading(true);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/chat",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            message: question,
            session_id: sessionId,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Server returned ${response.status}`
        );
      }

      const data = await response.json();

      const agentMessage = {
        role: "agent",
        text: data.answer,
      };

      setMessages((current) => [
        ...current,
        agentMessage,
      ]);

      setBackendConnected(true);
    } catch (error) {
      console.error(error);

      setBackendConnected(false);

      setMessages((current) => [
        ...current,
        {
          role: "agent",
          text: "I couldn't reach the LoanOps backend.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  // --------------------------------------------------
  // Start a new conversation
  // --------------------------------------------------

  function clearChat() {
    setMessages([
      {
        role: "agent",
        text: "LoanOps Agent ready. Ask me about a loan.",
      },
    ]);

    setSessionId(
      crypto.randomUUID()
    );
  }

  // --------------------------------------------------
  // UI
  // --------------------------------------------------

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>LoanOps</h1>
          <p>Commercial Loan AI Assistant</p>
        </div>

        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: "14px",
          }}
        >
          <div className="status">
            <span
              className={
                backendConnected
                  ? "status-dot"
                  : "status-dot offline"
              }
            ></span>

            {backendConnected
              ? "Connected"
              : "Disconnected"}
          </div>

          <button
            className="clear-button"
            onClick={clearChat}
          >
            Clear Chat
          </button>
        </div>
      </header>

      <main className="chat-container">
        <div className="messages">
          {messages.map(
            (message, index) => (
              <div
                key={index}
                className={`message-row ${message.role}`}
              >
                <div className="message">
                  <div className="message-role">
                    {message.role === "user"
                      ? "You"
                      : "LoanOps"}
                  </div>

                  <div className="message-text">
                    {message.text}
                  </div>
                </div>
              </div>
            )
          )}

          {loading && (
            <div className="message-row agent">
              <div className="message">
                <div className="message-role">
                  LoanOps
                </div>

                <div className="message-text">
                  Thinking...
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <form
          className="input-area"
          onSubmit={handleSubmit}
        >
          <input
            type="text"
            value={input}
            onChange={(event) =>
              setInput(event.target.value)
            }
            placeholder="Ask about a loan..."
            disabled={loading}
          />

          <button
            type="submit"
            disabled={loading}
          >
            Send
          </button>
        </form>
      </main>
    </div>
  );
}

export default App;