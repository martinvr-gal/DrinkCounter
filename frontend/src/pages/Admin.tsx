import { useEffect, useRef, useState } from "react"; import { useGesture } from "@use-gesture/react"; import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"; import axios from "axios"; import { adminClips, api, deleteClip, imageUrl, pending, updateStatus, uploadClip } from "../services/api"; import type { Photo, Status } from "../types";
import logo from "../../img/logo.png";

function Login({ done }: { done: () => void }) { const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [error, setError] = useState(""); async function submit(e: React.FormEvent) { e.preventDefault(); try { const r = await api.post("admin/login", { username, password }); localStorage.setItem("gallery-token", r.data.access_token); done() } catch { setError("Credenciales incorrectas"); } } return <main style={{ maxWidth: 400, margin: "12vh auto", padding: "1rem" }}><form className="card" onSubmit={submit}><h1>Administración</h1><input className="input" placeholder="Usuario" value={username} onChange={e => setUsername(e.target.value)} /><input className="input" style={{ marginTop: 10 }} type="password" placeholder="Contraseña" value={password} onChange={e => setPassword(e.target.value)} /><button className="btn" style={{ width: "100%", marginTop: 12 }}>Entrar</button><p>{error}</p></form></main> }
function Review({ photo, action }: { photo: Photo; action: (s: Status) => void }) {
  const [x, setX] = useState(0);
  const [expanded, setExpanded] = useState(false);
  const bind = useGesture({ onDrag: ({ down, movement: [mx], last }) => { setX(down ? mx : 0); if (last && Math.abs(mx) > 100) action(mx > 0 ? "APPROVED" : "REJECTED") } }, { drag: { filterTaps: true } });
  return <><article {...bind()} className="review-card" style={{ touchAction: "none", transform: `translateX(${x}px) rotate(${x / 30}deg)`, transition: x ? "none" : "transform .2s" }}>
    <div className="review-image-wrap" onClick={() => setExpanded(true)} role="button" tabIndex={0} onKeyDown={event => event.key === "Enter" && setExpanded(true)} aria-label="Ampliar fotografía">
      <img draggable={false} src={imageUrl(photo.url)} alt={`Fotografía de ${photo.user_name}`} className="review-image" />
      <span className="expand-icon" aria-hidden="true">⛶</span>
      <span className="review-swipe reject-hint" style={{ opacity: x < 0 ? Math.min(Math.abs(x) / 100, 1) : 0 }}>DESCARTAR</span>
      <span className="review-swipe approve-hint" style={{ opacity: x > 0 ? Math.min(x / 100, 1) : 0 }}>APROBAR</span>
    </div>
    <div className="review-info"><div><p className="review-label">EN REVISIÓN</p><h2>{photo.user_name}</h2></div><p>Desliza para decidir o usa los botones</p></div>
    <div className="review-actions">
      <button type="button" className="review-action reject" onClick={() => action("REJECTED")}><span>×</span>Descartar</button>
      <button type="button" className="review-action approve" onClick={() => action("APPROVED")}>Aprobar<span>✓</span></button>
    </div>
  </article>{expanded && <div className="image-lightbox" role="dialog" aria-modal="true" aria-label="Fotografía ampliada" onClick={() => setExpanded(false)}>
    <button className="lightbox-close" aria-label="Cerrar fotografía" onClick={() => setExpanded(false)}>×</button>
    <img src={imageUrl(photo.url)} alt={`Fotografía de ${photo.user_name}`} onClick={event => event.stopPropagation()} />
  </div>}</>
}
const folders: { key: Status; label: string; className: string }[] = [
  { key: "PENDING", label: "Pendientes", className: "pending" },
  { key: "APPROVED", label: "Aprobadas", className: "approved" },
  { key: "REJECTED", label: "Descartadas", className: "rejected" },
];
function clipMediaType(url: string) { const extension = url.split("?")[0].split(".").pop()?.toLowerCase(); return extension === "mov" ? "video/quicktime" : extension === "webm" ? "video/webm" : extension === "m4v" ? "video/x-m4v" : "video/mp4"; }
function uploadErrorMessage(error: unknown) { if (axios.isAxiosError(error)) { const status = error.response?.status; if (status === 413) return "El clip supera el tamaño máximo de 1 GB."; if (status === 415) return "Formato no compatible. Usa MP4, WebM, MOV o M4V."; if (status === 401 || status === 403) return "Tu sesión ha caducado. Vuelve a iniciar sesión."; } return "No se pudo subir el clip. Comprueba la conexión e inténtalo de nuevo."; }
function Library({ section }: { section: "photos" | "clips" }) {
  const [tab, setTab] = useState<Status>("PENDING");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Photo | null>(null);
  const [clip, setClip] = useState<File | null>(null);
  const clipInput = useRef<HTMLInputElement>(null);
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["gallery", tab, search], queryFn: () => import("../services/api").then(m => m.gallery(tab.toLowerCase(), 1, search)), enabled: section === "photos" });
  const { data: clipUrls = [], isLoading: clipsLoading } = useQuery({ queryKey: ["admin-clips"], queryFn: adminClips, enabled: section === "clips" });
  const move = useMutation({
    mutationFn: ({ photo, status }: { photo: Photo; status: Status }) => updateStatus(photo.id, status, photo.version),
    onSuccess: (_, variables) => { if (selected?.id === variables.photo.id) setSelected(null); qc.invalidateQueries({ queryKey: ["gallery"] }); },
  });
  const clipUpload = useMutation({
    mutationFn: uploadClip,
    onSuccess: () => { setClip(null); if (clipInput.current) clipInput.current.value = ""; qc.invalidateQueries({ queryKey: ["admin-clips"] }); },
  });
  const clipDelete = useMutation({ mutationFn: deleteClip, onSuccess: () => qc.invalidateQueries({ queryKey: ["admin-clips"] }) });
  const changeFolder = (photo: Photo, status: Status) => { if (photo.status !== status) move.mutate({ photo, status }); };
  const submitClip = (event: React.FormEvent<HTMLFormElement>) => { event.preventDefault(); if (clip) clipUpload.mutate(clip); };
  const removeClip = (url: string, label: string) => { const filename = decodeURIComponent(url.split("/").pop() || ""); if (filename && window.confirm(`¿Eliminar ${label}? Esta acción no se puede deshacer.`)) clipDelete.mutate(filename); };
  return <section className="library-page">
    {section === "photos" && <div className="library-title"><div><p className="review-label">GESTIÓN DE ARCHIVO</p><h2>Biblioteca</h2></div><span>{data?.total || 0} fotos</span></div>}
    {section === "photos" ? <>
      <input className="input library-search" value={search} onChange={e => setSearch(e.target.value)} placeholder="Buscar por nombre" />
      <nav className="folder-tabs" aria-label="Carpetas de fotos">{folders.map(folder => <button key={folder.key} className={`folder-tab ${folder.className} ${tab === folder.key ? "active" : ""}`} onClick={() => setTab(folder.key)}>{folder.label}</button>)}</nav>
      <p className="library-tip">Toca una foto para ampliarla y cambiarla de carpeta.</p>
      <div className="library-grid">{data?.items.map(photo => <button key={photo.id} className="library-thumbnail" onClick={() => setSelected(photo)}><img loading="lazy" src={imageUrl(photo.url)} alt={`Foto de ${photo.user_name}`} /><span>{photo.user_name}</span></button>)}</div>
    </> : <section className="clips-library" aria-labelledby="clips-title">
      <div className="library-title"><div><p className="review-label">CONTENIDO DE TV</p><h2 id="clips-title">Clips</h2></div><span>{clipUrls.length} clips</span></div>
      <form className="clip-upload" onSubmit={submitClip}>
        <input ref={clipInput} type="file" accept="video/mp4,video/webm,video/quicktime,video/x-m4v,.mp4,.webm,.mov,.m4v" onChange={event => setClip(event.target.files?.[0] || null)} />
        <button className="admin-nav-button" disabled={!clip || clipUpload.isPending}>{clipUpload.isPending ? "Subiendo…" : "Subir clip"}</button>
      </form>
      {clipUpload.error && <p className="clip-upload-error">{uploadErrorMessage(clipUpload.error)}</p>}
      {clipsLoading && <p className="library-tip">Cargando clips…</p>}
      {!clipsLoading && clipUrls.length === 0 && <p className="library-tip">Todavía no hay clips subidos.</p>}
      <div className="clip-grid">{clipUrls.map((url, index) => { const label = `Clip ${index + 1}`; return <article className="clip-card" key={url}><video controls preload="metadata"><source src={url} type={clipMediaType(url)} />Tu navegador no puede reproducir este clip.</video><div className="clip-card-footer"><span>{label}</span><button type="button" className="clip-delete" disabled={clipDelete.isPending} onClick={() => removeClip(url, label)}>{clipDelete.isPending ? "Eliminando…" : "Eliminar"}</button></div></article> })}</div>
    </section>}
    {selected && <div className="image-lightbox library-lightbox" role="dialog" aria-modal="true" aria-label="Gestionar fotografía" onClick={() => setSelected(null)}>
      <button className="lightbox-close" aria-label="Cerrar fotografía" onClick={() => setSelected(null)}>×</button>
      <div className="library-lightbox-content" onClick={event => event.stopPropagation()}><img src={imageUrl(selected.url)} alt={`Foto de ${selected.user_name}`} /><div className="library-lightbox-footer"><div><p className="review-label">FOTOGRAFÍA DE</p><strong>{selected.user_name}</strong></div><div className="move-actions">{folders.filter(folder => folder.key !== selected.status).map(folder => <button key={folder.key} className={`move-action ${folder.className}`} disabled={move.isPending} onClick={() => changeFolder(selected, folder.key)}>Mover a {folder.label}</button>)}</div></div></div>
    </div>}
  </section>
}
export default function Admin() { const [logged, setLogged] = useState(!!localStorage.getItem("gallery-token")); const requestedView = new URLSearchParams(window.location.search).get("view"); const view: "review" | "library" | "clips" = requestedView === "library" || requestedView === "clips" ? requestedView : "review"; const qc = useQueryClient(); api.interceptors.request.use(c => { const t = localStorage.getItem("gallery-token"); if (t) c.headers.Authorization = `Bearer ${t}`; return c }); const { data, error } = useQuery({ queryKey: ["pending"], queryFn: pending, enabled: logged && view === "review" }); useEffect(() => { if (axios.isAxiosError(error) && error.response?.status === 401) { localStorage.removeItem("gallery-token"); setLogged(false); } }, [error]); const mutation = useMutation({ mutationFn: ({ p, s }: { p: Photo; s: Status }) => updateStatus(p.id, s, p.version), onSuccess: () => qc.invalidateQueries({ queryKey: ["pending"] }), onError: () => qc.invalidateQueries({ queryKey: ["pending"] }) }); if (!logged) return <Login done={() => setLogged(true)} />; return <main className="admin-page"><header className="admin-nav"><div className="admin-brand"><span><img src={logo} alt="Logo de la Comisión de Celas" /></span><div><b>Galería</b><small>Administración</small></div></div><nav className="admin-nav-actions" aria-label="Secciones de administración"><a className={`admin-nav-button ${view === "review" ? "active" : ""}`} href="/admin?view=review">Revisión</a><a className={`admin-nav-button ${view === "library" ? "active" : ""}`} href="/admin?view=library">Biblioteca</a><a className={`admin-nav-button ${view === "clips" ? "active" : ""}`} href="/admin?view=clips">Clips</a><a className="admin-nav-button" href="/spotify">Spotify</a></nav></header>{view === "library" ? <Library section="photos" /> : view === "clips" ? <Library section="clips" /> : data?.items[0] ? <Review photo={data.items[0]} action={s => mutation.mutate({ p: data.items[0], s})} /> : <p style={{ textAlign: "center", marginTop: "20vh" }}>No hay fotografías pendientes.</p>}</main> }
