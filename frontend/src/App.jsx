import { useEffect, useState } from "react";
import ChatInterface from "./components/ChatInterface";
import DocumentList from "./components/DocumentList";
import DocumentUpload from "./components/DocumentUpload";
import { listDocuments } from "./api/client";

function BrandMark() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="m12 3-1.9 5.8a2 2 0 0 1-1.3 1.3L3 12l5.8 1.9a2 2 0 0 1 1.3 1.3L12 21l1.9-5.8a2 2 0 0 1 1.3-1.3L21 12l-5.8-1.9a2 2 0 0 1-1.3-1.3z" />
    </svg>
  );
}

function DocListSkeleton() {
  return (
    <div aria-hidden="true">
      <div className="doclist__label">
        <span className="eyebrow">Documentos</span>
      </div>
      {[68, 82, 54].map((w, i) => (
        <div className="doc-skeleton" key={i}>
          <div className="skeleton doc-skeleton__thumb" />
          <div className="doc-skeleton__lines">
            <div className="skeleton doc-skeleton__line" style={{ width: `${w}%` }} />
            <div className="skeleton doc-skeleton__line" style={{ width: `${w - 28}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

function InfoIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <path d="M12 16v-4" /><path d="M12 8h.01" />
    </svg>
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M18 6 6 18" /><path d="M6 6l12 12" />
    </svg>
  );
}

function InfoModal({ onClose }) {
  return (
    <div className="info-overlay" onClick={onClose}>
      <div className="info-modal" onClick={(e) => e.stopPropagation()}>
        <div className="info-modal__header">
          <span className="info-modal__title">Como o RAG funciona</span>
          <button className="info-modal__close" onClick={onClose} aria-label="Fechar"><CloseIcon /></button>
        </div>
        <div className="info-modal__body">
          <div className="info-step">
            <span className="info-step__num">1</span>
            <div>
              <strong>Chunking</strong>
              <p>O documento é dividido em trechos menores com sobreposição parcial entre eles, preservando o contexto nas bordas de cada pedaço.</p>
            </div>
          </div>
          <div className="info-step">
            <span className="info-step__num">2</span>
            <div>
              <strong>Embeddings</strong>
              <p>Cada trecho é convertido em um vetor numérico por um modelo de linguagem local (all-MiniLM-L6-v2). Textos semanticamente similares ficam próximos nesse espaço vetorial.</p>
            </div>
          </div>
          <div className="info-step">
            <span className="info-step__num">3</span>
            <div>
              <strong>Busca semântica</strong>
              <p>Ao receber uma pergunta, ela também vira um vetor. O banco de dados (pgvector) busca os trechos com maior similaridade por cosseno — não por palavras-chave, mas por significado.</p>
            </div>
          </div>
          <div className="info-step">
            <span className="info-step__num">4</span>
            <div>
              <strong>Geração aumentada</strong>
              <p>Os trechos recuperados são inseridos no prompt enviado ao LLM (Groq / Llama 3). O modelo responde baseando-se apenas nesse contexto, sem inventar informações.</p>
            </div>
          </div>
        </div>
        <p className="info-modal__footer">Arquitetura: FastAPI · pgvector · Celery · fastembed · Groq</p>
      </div>
    </div>
  );
}

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);
  const [showInfo, setShowInfo] = useState(false);
  const [chatHistories, setChatHistories] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem("chatHistories") ?? "{}");
    } catch {
      return {};
    }
  });

  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(console.error)
      .finally(() => setIsLoadingDocs(false));
  }, []);

  const handleUploaded = (doc) => {
    setDocuments((prev) => [doc, ...prev]);
    setActiveDoc(doc);
  };

  const handleDocUpdate = (updatedDoc) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === updatedDoc.id ? updatedDoc : d))
    );
    if (activeDoc?.id === updatedDoc.id) setActiveDoc(updatedDoc);
  };

  const handleDocDelete = (docId) => {
    setDocuments((prev) => prev.filter((d) => d.id !== docId));
    if (activeDoc?.id === docId) setActiveDoc(null);
    setChatHistories((prev) => {
      const next = { ...prev };
      delete next[docId];
      localStorage.setItem("chatHistories", JSON.stringify(next));
      return next;
    });
  };

  const handleMessagesChange = (docId, messages) => {
    setChatHistories((prev) => {
      const next = { ...prev, [docId]: messages };
      localStorage.setItem("chatHistories", JSON.stringify(next));
      return next;
    });
  };

  return (
    <div className="app">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark"><BrandMark /></div>
          <div className="brand-text">
            <h1>Context</h1>
            <p>Converse com seus documentos</p>
          </div>
        </div>

        <div className="sidebar-section">
          <DocumentUpload
            onUploaded={handleUploaded}
            existingFilenames={documents.map((d) => d.filename)}
          />
        </div>

        <div className="sidebar-scroll">
          {isLoadingDocs ? (
            <DocListSkeleton />
          ) : (
            <DocumentList
              documents={documents}
              activeDocId={activeDoc?.id}
              onSelect={setActiveDoc}
              onUpdate={handleDocUpdate}
              onDelete={handleDocDelete}
            />
          )}
        </div>

        <div className="sidebar-footer">
          <button
            className="info-btn"
            onClick={() => setShowInfo(true)}
            aria-label="Como funciona"
          >
            <span className="info-btn__dot" aria-hidden="true" />
            <span className="info-btn__dot" aria-hidden="true" />
            <InfoIcon /> Como funciona
          </button>
        </div>
      </aside>

      {showInfo && <InfoModal onClose={() => setShowInfo(false)} />}

      {/* ── Chat ── */}
      <main className="main">
        <ChatInterface
          activeDoc={activeDoc}
          messages={chatHistories[activeDoc?.id] ?? []}
          onMessagesChange={(msgs) => activeDoc && handleMessagesChange(activeDoc.id, msgs)}
        />
      </main>
    </div>
  );
}
