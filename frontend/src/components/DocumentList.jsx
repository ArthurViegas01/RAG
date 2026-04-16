import { useEffect, useState } from "react";
import { deleteDocument, getDocumentStatus } from "../api/client";

const STATUS = {
  pending:    { label: "Aguardando", cls: "badge-pending" },
  processing: { label: "Processando", cls: "badge-processing" },
  done:       { label: "Pronto",      cls: "badge-done" },
  error:      { label: "Erro",        cls: "badge-error" },
};

export default function DocumentList({ documents, activeDocId, onSelect, onUpdate, onDelete }) {
  const [deletingId, setDeletingId] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);

  // Polling a cada 3s para docs em processamento
  useEffect(() => {
    const processing = documents.filter(
      (d) => d.status === "pending" || d.status === "processing"
    );
    if (processing.length === 0) return;

    const interval = setInterval(async () => {
      for (const doc of processing) {
        try {
          const updated = await getDocumentStatus(doc.id);
          if (updated.status !== doc.status) onUpdate({ ...doc, ...updated });
        } catch { /* silencioso */ }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [documents]);

  const handleDelete = async (e, doc) => {
    e.stopPropagation(); // não seleciona o doc ao clicar no delete
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
        const isDeleting = deletingId === doc.id;
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

            {/* Spinner + botão de delete lado a lado durante processamento */}
            {isDeleting ? (
              <div className="spinner" />
            ) : isProcessing ? (
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
            ) : isHovered || isActive ? (
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
