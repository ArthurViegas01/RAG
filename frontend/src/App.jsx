import { useEffect, useState } from "react";
import ChatInterface from "./components/ChatInterface";
import DocumentList from "./components/DocumentList";
import DocumentUpload from "./components/DocumentUpload";
import { listDocuments } from "./api/client";

/**
 * Componente raiz.
 * Gerencia estado global: lista de documentos e documento ativo.
 */
export default function App() {
  const [documents, setDocuments] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);

  // Carrega documentos existentes ao abrir
  useEffect(() => {
    listDocuments()
      .then(setDocuments)
      .catch(console.error)
      .finally(() => setIsLoadingDocs(false));
  }, []);

  // Callback: novo upload realizado
  const handleUploaded = (doc) => {
    setDocuments((prev) => [doc, ...prev]);
    setActiveDoc(doc);
  };

  // Callback: status de um documento foi atualizado (polling)
  const handleDocUpdate = (updatedDoc) => {
    setDocuments((prev) =>
      prev.map((d) => (d.id === updatedDoc.id ? updatedDoc : d))
    );
    // Atualiza documento ativo se for o mesmo
    if (activeDoc?.id === updatedDoc.id) {
      setActiveDoc(updatedDoc);
    }
  };

  return (
    <div className="app-layout">
      {/* Sidebar */}
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>📚 RAG Pipeline</h1>
          <p>Upload de documentos e Q&A com IA</p>
        </div>

        <DocumentUpload onUploaded={handleUploaded} />

        {isLoadingDocs ? (
          <div style={{ padding: "16px", display: "flex", gap: 8, alignItems: "center" }}>
            <div className="spinner" />
            <span style={{ fontSize: 13, color: "var(--text-muted)" }}>
              Carregando...
            </span>
          </div>
        ) : (
          <DocumentList
            documents={documents}
            activeDocId={activeDoc?.id}
            onSelect={setActiveDoc}
            onUpdate={handleDocUpdate}
          />
        )}
      </aside>

      {/* Área principal: chat */}
      <main className="main-area">
        <ChatInterface activeDoc={activeDoc} />
      </main>
    </div>
  );
}
