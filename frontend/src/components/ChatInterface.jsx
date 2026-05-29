import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";
import { chat } from "../api/client";

const Sparkles = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z" />
  </svg>
);

const FileText = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" />
    <path d="M14 2v5h5" /><path d="M16 13H8" /><path d="M16 17H8" /><path d="M10 9H8" />
  </svg>
);

const UserIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M19 21v-2a4 4 0 0 0-4-4H9a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
  </svg>
);

const SendIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 19V5" /><path d="M5 12l7-7 7 7" />
  </svg>
);

const ChevronIcon = () => (
  <svg className="citation__chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="m6 9 6 6 6-6" />
  </svg>
);

const AlertIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="m21.7 18-8-14a2 2 0 0 0-3.4 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3z" />
    <path d="M12 9v4" /><path d="M12 17h.01" />
  </svg>
);

export default function ChatInterface({ activeDoc, messages, onMessagesChange }) {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [openCites, setOpenCites] = useState(() => new Set());
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

  const toggleCite = (key) => {
    setOpenCites((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

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
      const isOllamaError = err.message.includes("Ollama");
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: err.message,
          isError: true,
          isOllamaError,
        },
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
    <div className={`chat__header ${activeDoc ? "" : "is-empty"}`}>
      <div className={`chat__header-icon ${activeDoc ? "" : "is-empty"}`}>
        <FileText />
      </div>
      <div className="chat__header-info">
        <h2>{activeDoc ? activeDoc.filename : "Nenhum documento selecionado"}</h2>
        <p>
          {activeDoc
            ? activeDoc.status === "done"
              ? `${activeDoc.total_chunks} trechos indexados · pronto para perguntas`
              : activeDoc.status === "error"
              ? "Erro ao indexar este documento"
              : "Indexando documento, aguarde…"
            : "Selecione um documento na barra lateral para conversar"}
        </p>
      </div>
    </div>
  );

  /* ── Empty ── */
  const renderEmpty = () => (
    <div className="chat__empty">
      <div className="chat__empty-art">
        <div className="chat__empty-orb"><Sparkles /></div>
      </div>
      <h3>{hasReady ? `Pergunte sobre "${activeDoc.filename}"` : "Carregue um documento"}</h3>
      <p>
        {hasReady
          ? "O Context busca os trechos mais relevantes e responde com base no conteúdo do documento."
          : "Envie um PDF ou DOCX, aguarde a indexação e faça perguntas em linguagem natural."}
      </p>
      {!hasReady && (
        <div className="steps">
          <div className="step"><span className="step__num">1</span> Enviar documento</div>
          <div className="step"><span className="step__num">2</span> Aguardar indexação</div>
          <div className="step"><span className="step__num">3</span> Fazer perguntas</div>
        </div>
      )}
    </div>
  );

  return (
    <>
      {renderHeader()}

      <div className="chat__scroll">
        {messages.length === 0 && renderEmpty()}

        {messages.map((msg, i) => (
          <div key={i} className={`msg msg--${msg.role}`}>
            <div className="msg__avatar">
              {msg.role === "user" ? <UserIcon /> : <Sparkles />}
            </div>
            <div className="msg__bubble">
              {msg.role === "assistant" && msg.isError ? (
                <div className="errorcard">
                  {msg.isOllamaError ? (
                    <>
                      <p className="errorcard__title"><AlertIcon /> Ollama não está acessível</p>
                      <p>O modelo de linguagem local não está rodando. Para corrigir:</p>
                      <ol>
                        <li>Abra um terminal no seu computador</li>
                        <li>Execute: <code>ollama serve</code></li>
                        <li>Aguarde alguns segundos e tente novamente</li>
                      </ol>
                      <p className="errorcard__hint">
                        Se o Ollama não estiver instalado: <a href="https://ollama.com" target="_blank" rel="noreferrer">ollama.com</a>
                      </p>
                    </>
                  ) : (
                    <>
                      <p className="errorcard__title"><AlertIcon /> Erro ao gerar resposta</p>
                      <p>{msg.content}</p>
                    </>
                  )}
                </div>
              ) : msg.role === "assistant" ? (
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              ) : (
                <p>{msg.content}</p>
              )}

              {msg.citations?.length > 0 && (() => {
                const shown = msg.citations.slice(0, Math.ceil(msg.citations.length / 2));
                return (
                  <div className="citations">
                    <span className="eyebrow">Fontes · {shown.length}</span>
                    <div className="citations__chips">
                      {shown.map((c, j) => {
                        const key = `${i}:${j}`;
                        const open = openCites.has(key);
                        return (
                          <button
                            key={j}
                            className={`citation ${open ? "is-open" : ""}`}
                            onClick={() => toggleCite(key)}
                            title={`${c.source} · trecho ${c.chunk_index + 1}`}
                          >
                            <FileText />
                            <span className="citation__name">{c.source}</span>
                            · trecho {c.chunk_index + 1}
                            <ChevronIcon />
                          </button>
                        );
                      })}
                    </div>
                    {shown.some((_, j) => openCites.has(`${i}:${j}`)) && (
                      <div className="citation-panels">
                        {shown.map((c, j) =>
                          openCites.has(`${i}:${j}`) ? (
                            <div key={j} className="citation-panel">
                              <span className="citation-panel__src">{c.source} · trecho {c.chunk_index + 1}</span>
                              {c.content}
                            </div>
                          ) : null
                        )}
                      </div>
                    )}
                  </div>
                );
              })()}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="msg msg--assistant">
            <div className="msg__avatar"><Sparkles /></div>
            <div className="msg__bubble">
              <div className="thinking"><span /><span /><span /></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Composer */}
      <div className="composer">
        <div className="composer__inner">
          <div className="composer__field">
            <textarea
              ref={textareaRef}
              className="composer__input"
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={isLoading || !hasReady}
              placeholder={
                hasReady
                  ? `Pergunte sobre "${activeDoc.filename}"…`
                  : "Selecione um documento indexado para perguntar…"
              }
              onInput={(e) => {
                e.target.style.height = "auto";
                e.target.style.height = Math.min(e.target.scrollHeight, 132) + "px";
              }}
            />
            <button
              className="composer__send"
              onClick={handleSend}
              disabled={!input.trim() || isLoading || !hasReady}
              title="Enviar"
            >
              <SendIcon />
            </button>
          </div>
          <p className="composer__hint">
            <kbd>Enter</kbd> para enviar · <kbd>Shift</kbd>+<kbd>Enter</kbd> para nova linha
          </p>
        </div>
      </div>
    </>
  );
}
