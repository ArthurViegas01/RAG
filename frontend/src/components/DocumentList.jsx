import { useEffect } from "react";
import { getDocumentStatus } from "../api/client";

const STATUS = {
  pending:    { label: "Aguardando", cls: "badge-pending" },
  processing: { label: "Processando", cls: "badge-processing" },
  done:       { label: "Pronto",      cls: "badge-done" },
  error:      { label: "Erro",        cls: "badge-error" },
};

export default function DocumentList({ documents, activeDocId, onSelect, onUpdate }) {

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
        const badge = STATUS[doc.status] || STATUS.pending;

        const icon = ext === "pdf" ? "📕" : "📘";

        return (
          <div
            key={doc.id}
            className={`doc-item ${isActive ? "active" : ""}`}
            onClick={() => onSelect(doc)}
            title={doc.filename}
          >
            {/* Thumbnail */}
            <div className={`doc-thumb ${ext}`}>{icon}</div>

            {/* Info */}
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

            {/* Status */}
            {isProcessing
              ? <div className="spinner" />
              : <span className={`badge ${badge.cls}`}>{badge.label}</span>
            }
          </div>
        );
      })}
    </div>
  );
}
