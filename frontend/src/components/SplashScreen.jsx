import { useEffect, useState } from "react";

export default function SplashScreen({ onDone }) {
  const [phase, setPhase] = useState("in"); // 'in' | 'out'

  useEffect(() => {
    const t1 = setTimeout(() => setPhase("out"), 1800);
    const t2 = setTimeout(() => onDone(), 2500);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
    };
  }, [onDone]);

  return (
    <div className={`splash splash--${phase}`}>
      <div className="splash-bg" />

      <div className="splash-content">
        {/* Logo */}
        <div className="splash-logo-wrap">
          <div className="splash-logo-ring splash-logo-ring--outer" />
          <div className="splash-logo-ring splash-logo-ring--inner" />
          <div className="splash-logo-mark">📜</div>
        </div>

        {/* Name */}
        <h1 className="splash-title">Context</h1>
        <p className="splash-subtitle">Converse com seus documentos</p>

        {/* Loader */}
        <div className="splash-loader">
          <div className="splash-loader-track">
            <div className="splash-loader-bar" />
          </div>
        </div>
      </div>
    </div>
  );
}
