import { useEffect, useRef, useState } from "react";
import { deleteDocument, getDocumentStatus, reprocessDocument } from "../api/client";

const STATUS = {
  pending:    { label: "Aguardando", cls: "badge--pending" },
  processing: { label: "Processando", cls: "badge--processing" },
  done:       { label: "Pronto",      cls: "badge--done" },
  error:      { label: "Erro",        cls: "badge--error" },
};

const FileIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7z" />
    <path d="M14 2v5h5" />
  </svg>
);

const XIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M18 6 6 18" /><path d="m6 6 12 12" />
  </svg>
);

const RetryIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M3 12a9 9 0 1 0 3-6.7L3 8" /><path d="M3 3v5h5" />
  </svg>
);

const FolderIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20 20a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.69-.9L9.6 3.9A2 2 0 0 0 7.93 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2z" />
  </svg>
);

export default function DocumentList({ documents, activeDocId, onSelect, onUpdate, onDelete }) {
  const [deletingId, setDeletingId] = useState(null);
  const [reprocessingId, setReprocessingId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);

  // Polling adaptativo para docs em processamento.
  // Começa em 2s, cresce até 8s para não sobrecarregar o servidor.
  // Para automaticamente quando não há mais docs ativos.
  const pollIntervalRef = useRef(2000);
  const pollTimeoutRef = useRef(null);

  useEffect(() => {
    const processing = documents.filter(
      (d) => d.status === "pending" || d.status === "processing"
    );

    // Cancela timeout anterior ao mudar a lista
    if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);

    if (processing.length === 0) {
      pollIntervalRef.current = 2000; // reset para próxima vez
      return;
    }

    const poll = async () => {
      let anyChange = false;
      for (const doc of processing) {
        try {
          const updated = await getDocumentStatus(doc.id);
          if (updated.status !== doc.status) {
            onUpdate({ ...doc, ...updated });
            anyChange = true;
          }
        } catch { /* silencioso */ }
      }

      // Se houve mudança, mantém intervalo rápido; senão, aumenta (até 8s)
      if (anyChange) {
        pollIntervalRef.current = 2000;
      } else {
        pollIntervalRef.current = Math.min(pollIntervalRef.current * 1.5, 8000);
      }

      pollTimeoutRef.current = setTimeout(poll, pollIntervalRef.current);
    };

    pollTimeoutRef.current = setTimeout(poll, pollIntervalRef.current);
    return () => {
      if (pollTimeoutRef.current) clearTimeout(pollTimeoutRef.current);
    };
  }, [documents]);

  const handleDelete = async (e, doc) => {
    e.stopPropagation();
    if (deletingId) return;
    setDeletingId(doc.id);
    try {
      await deleteDocument(doc.id);
      onDelete(doc.id);
    } catch (err) {
      console.error("Erro ao deletar:", err);
    } finally {
      setDeletingId(null);
    }
  };

  const handleReprocess = async (e, doc) => {
    e.stopPropagation();
    if (reprocessingId) return;
    setReprocessingId(doc.id);
    try {
      const updated = await reprocessDocument(doc.id);
      onUpdate({ ...doc, ...updated });
    } catch (err) {
      console.error("Erro ao reprocessar:", err);
    } finally {
      setReprocessingId(null);
    }
  };

  if (documents.length === 0) {
    return (
      <div>
        <div className="doclist__label"><span className="eyebrow">Documentos</span></div>
        <div className="doclist__empty">
          <FolderIcon />
          <p>Nenhum documento ainda.<br />Envie um arquivo acima para começar.</p>
        </div>
      </div>
    );
  }

  return (
    <div>
      <div className="doclist__label">
        <span className="eyebrow">Documentos</span>
        <span className="doclist__count">{documents.length}</span>
      </div>

      {documents.map((doc) => {
        const ext = doc.filename.split(".").pop().toLowerCase();
        const isActive = doc.id === activeDocId;
        const isProcessing = doc.status === "pending" || doc.status === "processing";
        const isError = doc.status === "error";
        const isDeleting = deletingId === doc.id;
        const isReprocessing = reprocessingId === doc.id;
        const showActions = hoveredId === doc.id || isActive;
        const badge = STATUS[doc.status] || STATUS.pending;

        const meta =
          doc.status === "done"
            ? `${doc.total_chunks} trechos indexados`
            : doc.status === "error"
            ? "Erro no processamento"
            : doc.status === "pending"
            ? "Na fila…"
            : "Indexando…";

        return (
          <div
            key={doc.id}
            className={`doc ${isActive ? "is-active" : ""}`}
            onClick={() => !isDeleting && onSelect(doc)}
            onMouseEnter={() => setHoveredId(doc.id)}
            onMouseLeave={() => setHoveredId(null)}
            title={doc.filename}
          >
            <div className={`doc__thumb doc__thumb--${ext}`}>
              <FileIcon />
              <span className="doc__ext">{ext}</span>
            </div>

            <div className="doc__main">
              <div className="doc__name">{doc.filename}</div>
              <div className="doc__meta">{meta}</div>
            </div>

            <div className="doc__status">
              {isDeleting || isReprocessing ? (
                <div className="spinner" />
              ) : isProcessing ? (
                showActions ? (
                  <button
                    className="icon-btn icon-btn--warning"
                    onClick={(e) => handleDelete(e, doc)}
                    title="Cancelar e deletar"
                  >
                    <XIcon />
                  </button>
                ) : (
                  <span className={`badge ${badge.cls}`}>{badge.label}</span>
                )
              ) : isError && showActions ? (
                <>
                  <button
                    className="icon-btn icon-btn--accent"
                    onClick={(e) => handleReprocess(e, doc)}
                    title="Tentar novamente"
                  >
                    <RetryIcon />
                  </button>
                  <button
                    className="icon-btn icon-btn--danger"
                    onClick={(e) => handleDelete(e, doc)}
                    title="Deletar documento"
                  >
                    <XIcon />
                  </button>
                </>
              ) : showActions ? (
                <button
                  className="icon-btn icon-btn--danger"
                  onClick={(e) => handleDelete(e, doc)}
                  title="Deletar documento"
                >
                  <XIcon />
                </button>
              ) : (
                <span className={`badge ${badge.cls}`}>{badge.label}</span>
              )}
            </div>

            {isProcessing && <div className="doc__progress" />}
          </div>
        );
      })}
    </div>
  );
}
