import { useEffect, useRef, useState } from "react"; // useState usado para input e isLoading
import ReactMarkdown from "react-markdown";
import { chat } from "../api/client";

export default function ChatInterface({ activeDoc, messages, onMessagesChange }) {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Ref sempre atualizado com o valor mais recente de messages.
  // Necessário para evitar stale closure em handleSend (função async):
  // sem o ref, o segundo setMessages (resposta do assistente) usaria o
  // valor de `messages` capturado no início da chamada, apagando o
  // user message que foi adicionado no primeiro setMessages.
  const messagesRef = useRef(messages);
  useEffect(() => {
    messagesRef.current = messages;
  }, [messages]);

  // Wrapper que propaga atualizações ao pai (App.jsx)
  const setMessages = (updater) => {
    const next = typeof updater === "function" ? updater(messagesRef.current) : updater;
    onMessagesChange(next);
  };

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || isLoading) return;

    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setIsLoading(true);

    try {
      const docId = activeDoc?.status === "done" ? activeDoc.id : null;
      const response = await chat(question, docId);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: response.answer, citations: response.citations || [] },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠️ ${err.message}`, isError: true },
      ]);
    } finally {
      setIsLoading(false);
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasReady = activeDoc?.status === "done";

  /* ── Header ── */
  const renderHeader = () => (
    <div className="chat-header">
      <div className="chat-header-icon">
        {activeDoc ? (activeDoc.filename.endsWith(".pdf") ? "📕" : "📘") : "📜"}
      </div>
      <div className="chat-header-info">
        <h2>
          {activeDoc ? activeDoc.filename : "Papyrus Assistant"}
        </h2>
        <p>
          {activeDoc
            ? activeDoc.status === "done"
              ? `${activeDoc.total_chunks} trechos indexados · pronto para perguntas`
              : activeDoc.status === "error"
              ? "Erro ao indexar este documento"
              : "Indexando documento, aguarde..."
            : "Selecione um documento na barra lateral"}
        </p>
      </div>
      {hasReady && (
        <span className="chat-header-badge">● Online</span>
      )}
    </div>
  );

  /* ── Empty ── */
  const renderEmpty = () => (
    <div className="empty-state">
      <div className="empty-illustration">
        <div className="empty-circle">📜</div>
        <div className="empty-dot">✦</div>
      </div>
      <h3>
        {hasReady
          ? `Pergunte sobre "${activeDoc.filename}"`
          : "Carregue um documento"}
      </h3>
      <p>
        {hasReady
          ? "O Papyrus vai buscar os trechos mais relevantes e responder com base no conteúdo do documento."
          : "Envie um PDF ou DOCX, aguarde a indexação e faça perguntas em linguagem natural."}
      </p>
      {!hasReady && (
        <div className="empty-steps">
          <div className="empty-step">
            <span className="empty-step-num">1</span> Enviar documento
          </div>
          <div className="empty-step">
            <span className="empty-step-num">2</span> Aguardar indexação
          </div>
          <div className="empty-step">
            <span className="empty-step-num">3</span> Fazer perguntas
          </div>
        </div>
      )}
    </div>
  );

  return (
    <>
      {renderHeader()}

      {/* Mensagens */}
      <div className="chat-messages">
        {messages.length === 0 && renderEmpty()}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === "user" ? "🧑" : "📜"}
            </div>
            <div className="message-body">
              {msg.role === "assistant"
                ? <ReactMarkdown>{msg.content}</ReactMarkdown>
                : <p>{msg.content}</p>
              }
              {msg.citations?.length > 0 && (
                <div className="citations">
                  <span className="citations-label">Fontes</span>
                  {msg.citations.map((c, j) => (
                    <span key={j} className="citation" title={c.content}>
                      📎 {c.source} · trecho {c.chunk_index + 1}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="message assistant">
            <div className="message-avatar">📜</div>
            <div className="message-body">
              <div className="thinking">
                <span /><span /><span />
              </div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="chat-input-area">
        <div className="chat-input-wrapper">
          <textarea
            ref={textareaRef}
            className="chat-input"
            rows={1}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || !hasReady}
            placeholder={
              hasReady
                ? `Pergunte sobre "${activeDoc.filename}"...`
                : "Selecione um documento indexado para perguntar..."
            }
            onInput={(e) => {
              e.target.style.height = "auto";
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
            }}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isLoading || !hasReady}
          >
            ↑
          </button>
        </div>
        <p className="chat-hint">Enter para enviar · Shift+Enter para nova linha</p>
      </div>
    </>
  );
}
