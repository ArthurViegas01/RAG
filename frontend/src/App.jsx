import { useEffect, useState } from "react";
import ChatInterface from "./components/ChatInterface";
import DocumentList from "./components/DocumentList";
import DocumentUpload from "./components/DocumentUpload";
import { listDocuments } from "./api/client";

export default function App() {
  const [documents, setDocuments] = useState([]);
  const [activeDoc, setActiveDoc] = useState(null);
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);

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

  return (
    <div className="app-layout">
      {/* ── Sidebar ── */}
      <aside className="sidebar">
        {/* Logo */}
        <div className="sidebar-logo">
          <div className="logo-mark">📜</div>
          <div className="logo-text">
            <h1>Papyrus</h1>
            <p>Converse com seus documentos</p>
          </div>
        </div>

        {/* Upload */}
        <div className="upload-section">
          <DocumentUpload onUploaded={handleUploaded} />
        </div>

        {/* Lista */}
        {isLoadingDocs ? (
          <div style={{ padding: "14px 16px", display: "flex", gap: 8, alignItems: "center" }}>
            <div className="spinner" />
            <span style={{ fontSize: 12, color: "var(--text-3)" }}>Carregando...</span>
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

      {/* ── Chat ── */}
      <main className="main-area">
        <ChatInterface activeDoc={activeDoc} />
      </main>
    </div>
  );
}
