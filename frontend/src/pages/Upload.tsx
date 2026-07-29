import { ChangeEvent, useRef, useState } from "react";
import { api } from "../services/api";
import logo from "../../img/logo.png";

export default function Upload() {
  const [name, setName] = useState(localStorage.getItem("gallery-name") || "");
  const [identified, setIdentified] = useState(false);
  const [status, setStatus] = useState("");
  const [progress, setProgress] = useState(0);
  const [uploading, setUploading] = useState(false);
  const cameraInput = useRef<HTMLInputElement>(null);
  const galleryInput = useRef<HTMLInputElement>(null);

  const select = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (file) send(file);
    event.target.value = "";
  };

  async function send(file: File) {
    if (!name.trim()) {
      setStatus("Introduce primero tu nombre o Instagram.");
      return;
    }
    localStorage.setItem("gallery-name", name.trim());
    setUploading(true);
    setStatus("Subiendo fotografía…");
    setProgress(0);
    const data = new FormData();
    data.append("image", file);
    try {
      await api.post("/upload", data, {
        params: { user_name: name.trim() },
        onUploadProgress: (event) => setProgress(Math.round((event.loaded * 100) / (event.total || 1))),
      });
      setStatus("¡Recibida! Tu fotografía está pendiente de aprobación.");
    } catch (error: any) {
      setStatus(error.response?.data?.detail || "No se pudo subir la imagen. Inténtalo de nuevo.");
    } finally {
      setUploading(false);
    }
  }

  function identify(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) {
      setStatus("Introduce tu nombre o Instagram para continuar.");
      return;
    }
    localStorage.setItem("gallery-name", name.trim());
    setStatus("");
    setIdentified(true);
  }

  return (
    <main className="upload-page">
      <section className="upload-card">
        <div className="upload-hero">
          <img src={logo} alt="Logo de la Comisión de Celas" />
        </div>
        <header>
          <p className="eyebrow">Comisión de Celas</p>
          <h1>Comparte tua foto</h1>
          {!identified ?(<></>):(
            <p className="upload-description">Sube aquí túas fotos da festa para compartilas con todos.</p>
          )}
        </header>

        {!identified ? (
          <form onSubmit={identify}>
            <label className="name-label">
              <span>Teu nome ou Instagram</span>
              <input className="input upload-name" value={name} onChange={(event) => setName(event.target.value)} placeholder="" maxLength={120} autoFocus />
            </label>
            <button className="btn upload-continue" type="submit">Continuar</button>
          </form>
        ) : (
          <>
            <div className="identity-summary"><span>Nombre: </span><strong>{name.trim()}</strong><button onClick={() => setIdentified(false)}>Editar</button></div>
            <input ref={cameraInput} hidden type="file" accept="image/jpeg,image/png,image/webp,image/heic" capture="environment" onChange={select} />
            <input ref={galleryInput} hidden type="file" accept="image/jpeg,image/png,image/webp,image/heic" onChange={select} />
            <div className="upload-actions">
              <button className="upload-action camera" disabled={uploading} onClick={() => cameraInput.current?.click()}>
                <span className="action-icon">📸</span><span><strong>Facer unha foto</strong><small>Abre a cámara</small></span>
              </button>
              <button className="upload-action gallery" disabled={uploading} onClick={() => galleryInput.current?.click()}>
                <span className="action-icon">🖼️</span><span><strong>Elexir da galería</strong><small>Selecciona unha imaxen</small></span>
              </button>
            </div>
          </>
        )}

        {uploading && <div className="upload-progress"><div><span>Subiendo</span><strong>{progress}%</strong></div><progress value={progress} max="100" /></div>}
        {status && <p className={status.startsWith("¡") ? "upload-status success" : "upload-status"} aria-live="polite">{status}</p>}
      </section>
    </main>
  );
}
