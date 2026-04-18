import { useEffect, useRef, useState } from "react";
import { deleteDocument, getDocumentStatus, reprocessDocument } from "../api/client";

const STATUS = {
  pending:    { label: "Aguardando", cls: "badge-pending" },
  processing: { label: "Processando", cls: "badge-processing" },
  done:       { label: "Pronto",      cls: "badge-done" },
  error:      { label: "Erro",        cls: "badge-error" },
};

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
      <div className="doc-list">
        <div className="doc-list-label">Documentos</div>
        <p className="doc-empty">
          Nenhum documento ainda.<br />Envie um arquivo acima para começar.
        </p>
      </div>
    );
  }

  return (
    <div className="doc-list">
      <div className="doc-list-label">Documentos · {documents.length}</div>

      {documents.map((doc) => {
        const ext = doc.filename.split(".").pop().toLowerCase();
        const isActive = doc.id === activeDocId;
        const isProcessing = doc.status === "pending" || doc.status === "processing";
        const isError = doc.status === "error";
        const isDeleting = deletingId === doc.id;
        const isReprocessing = reprocessingId === doc.id;
        const isHovered = hoveredId === doc.id;
        const badge = STATUS[doc.status] || STATUS.pending;
        const icon = ext === "pdf" ? "📕" : "📘";

        return (
          <div
            key={doc.id}
            className={`doc-item ${isActive ? "active" : ""}`}
            onClick={() => !isDeleting && onSelect(doc)}
            onMouseEnter={() => setHoveredId(doc.id)}
            onMouseLeave={() => setHoveredId(null)}
            title={doc.filename}
          >
            <div className={`doc-thumb ${ext}`}>{icon}</div>

            <div className="doc-info">
              <div className="doc-name">{doc.filename}</div>
              <div className="doc-meta">
                {doc.status === "done"
                  ? `${doc.total_chunks} trechos indexados`
                  : doc.status === "error"
                  ? "Erro no processamento"
                  : "Indexando..."}
              </div>
            </div>

            {/* Estado: deletando */}
            {isDeleting || isReprocessing ? (
              <div className="spinner" />
            ) : isProcessing ? (
              /* Estado: processando — hover mostra botão de cancelar */
              isHovered || isActive ? (
                <button
                  className="doc-delete-btn doc-delete-btn--cancel"
                  onClick={(e) => handleDelete(e, doc)}
                  title="Cancelar e deletar"
                >
                  ✕
                </button>
              ) : (
                <div className="spinner" />
              )
            ) : isError && (isHovered || isActive) ? (
              /* Estado: erro — hover mostra reprocessar + deletar */
              <div className="doc-error-actions">
                <button
                  className="doc-action-btn doc-action-btn--retry"
                  onClick={(e) => handleReprocess(e, doc)}
                  title="Tentar novamente"
                >
                  ↺
                </button>
                <button
                  className="doc-delete-btn"
                  onClick={(e) => handleDelete(e, doc)}
                  title="Deletar documento"
                >
                  ✕
                </button>
              </div>
            ) : isHovered || isActive ? (
              /* Estado: pronto — hover mostra deletar */
              <button
                className="doc-delete-btn"
                onClick={(e) => handleDelete(e, doc)}
                title="Deletar documento"
              >
                ✕
              </button>
            ) : (
              <span className={`badge ${badge.cls}`}>{badge.label}</span>
            )}
          </div>
        );
      })}
    </div>
  );
}
