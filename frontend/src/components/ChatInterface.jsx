import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { chat } from "../api/client";

/**
 * Interface de chat com RAG.
 * Recebe uma pergunta, chama o backend e exibe a resposta com citações.
 *
 * Props:
 *  activeDoc — documento selecionado (pode ser null para busca em todos)
 */
export default function ChatInterface({ activeDoc }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);
  const textareaRef = useRef(null);

  // Scroll para o fim quando novas mensagens chegam
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const handleSend = async () => {
    const question = input.trim();
    if (!question || isLoading) return;

    // Adiciona mensagem do usuário
    const userMsg = { role: "user", content: question };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsLoading(true);

    try {
      const docId = activeDoc?.status === "done" ? activeDoc.id : null;
      const response = await chat(question, docId);

      const assistantMsg = {
        role: "assistant",
        content: response.answer,
        citations: response.citations || [],
      };
      setMessages((prev) => [...prev, assistantMsg]);
    } catch (err) {
      const errorMsg = {
        role: "assistant",
        content: `⚠️ Erro: ${err.message}`,
        isError: true,
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      // Re-foca no input após resposta
      setTimeout(() => textareaRef.current?.focus(), 50);
    }
  };

  const handleKeyDown = (e) => {
    // Enter envia; Shift+Enter quebra linha
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasActiveDocs = activeDoc?.status === "done";
  const placeholder = hasActiveDocs
    ? `Pergunte sobre "${activeDoc.filename}"...`
    : "Selecione um documento pronto para perguntar...";

  return (
    <>
      {/* Header */}
      <div className="chat-header">
        <span style={{ fontSize: 22 }}>🤖</span>
        <div>
          <h2>RAG Assistant</h2>
          <p>
            {activeDoc
              ? activeDoc.status === "done"
                ? `${activeDoc.total_chunks} chunks indexados de "${activeDoc.filename}"`
                : `"${activeDoc.filename}" ainda está processando...`
              : "Envie e selecione um documento para começar"}
          </p>
        </div>
      </div>

      {/* Mensagens */}
      <div className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">💬</div>
            <h3>Nenhuma conversa ainda</h3>
            <p>
              {hasActiveDocs
                ? `Faça uma pergunta sobre "${activeDoc.filename}" e o sistema buscará os trechos mais relevantes para responder.`
                : "Envie um documento PDF ou DOCX na barra lateral, aguarde o processamento e faça perguntas."}
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            <div className="message-avatar">
              {msg.role === "user" ? "🧑" : "🤖"}
            </div>
            <div className="message-body">
              {msg.role === "assistant" ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                <p>{msg.content}</p>
              )}

              {/* Citações de fontes */}
              {msg.citations && msg.citations.length > 0 && (
                <div className="citations">
                  {msg.citations.map((c, j) => (
                    <span key={j} className="citation" title={c.content}>
                      📎 {c.source} · chunk {c.chunk_index}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}

        {/* Indicador de "pensando" */}
        {isLoading && (
          <div className="message assistant">
            <div className="message-avatar">🤖</div>
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
            placeholder={placeholder}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={isLoading || !hasActiveDocs}
            style={{ height: "auto" }}
            onInput={(e) => {
              e.target.style.height = "auto";
              e.target.style.height = Math.min(e.target.scrollHeight, 120) + "px";
            }}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim() || isLoading || !hasActiveDocs}
          >
            ↑
          </button>
        </div>
        <p style={{ fontSize: 11, color: "var(--text-muted)", marginTop: 8, textAlign: "center" }}>
          Enter para enviar · Shift+Enter para nova linha
        </p>
      </div>
    </>
  );
}
