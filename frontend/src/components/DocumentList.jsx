import { useEffect } from "react";
import { getDocumentStatus } from "../api/client";

const STATUS_BADGE = {
  pending:    { label: "Aguardando", cls: "badge-pending" },
  processing: { label: "Processando", cls: "badge-processing" },
  done:       { label: "Pronto", cls: "badge-done" },
  error:      { label: "Erro", cls: "badge-error" },
};

const FILE_ICON = {
  pdf: "📕",
  docx: "📘",
};

/**
 * Lista de documentos na sidebar.
 * Faz polling para documentos com status pending/processing.
 *
 * Props:
 *  documents     — array de documentos
 *  activeDocId   — ID do documento selecionado (para highlight)
 *  onSelect(doc) — chamado ao clicar num documento
 *  onUpdate(doc) — chamado quando o status de um documento muda
 */
export default function DocumentList({ documents, activeDocId, onSelect, onUpdate }) {

  // Polling: para documentos em processamento, verifica o status a cada 3s
  useEffect(() => {
    const processing = documents.filter(
      (d) => d.status === "pending" || d.status === "processing"
    );
    if (processing.length === 0) return;

    const interval = setInterval(async () => {
      for (const doc of processing) {
        try {
          const updated = await getDocumentStatus(doc.id);
          if (updated.status !== doc.status) {
            onUpdate({ ...doc, ...updated });
          }
        } catch {
          // silencioso
        }
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [documents]);

  if (documents.length === 0) {
    return (
      <div className="doc-list">
        <h3>Documentos</h3>
        <p style={{ fontSize: 12, color: "var(--text-muted)", padding: "8px 4px" }}>
          Nenhum documento ainda. Envie um arquivo acima.
        </p>
      </div>
    );
  }

  return (
    <div className="doc-list">
      <h3>Documentos ({documents.length})</h3>

      {documents.map((doc) => {
        const ext = doc.filename.split(".").pop().toLowerCase();
        const icon = FILE_ICON[ext] || "📄";
        const badge = STATUS_BADGE[doc.status] || STATUS_BADGE.pending;
        const isActive = doc.id === activeDocId;
        const isProcessing = doc.status === "pending" || doc.status === "processing";

        return (
          <div
            key={doc.id}
            className={`doc-item ${isActive ? "active" : ""}`}
            onClick={() => onSelect(doc)}
            title={doc.filename}
          >
            <span className="doc-icon">{icon}</span>

            <div className="doc-info">
              <div className="doc-name">{doc.filename}</div>
              <div className="doc-meta">
                {doc.status === "done"
                  ? `${doc.total_chunks} chunks`
                  : doc.status === "error"
                  ? "Erro no processamento"
                  : "Processando..."}
              </div>
            </div>

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
