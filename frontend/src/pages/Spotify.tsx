import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import axios from "axios";
import { api } from "../services/api";
import logo from "../../img/logo.png";

type Track = { name: string; uri: string; artists: string[]; album?: string; image?: string };
type Playback = { is_playing?: boolean; item?: { name?: string; artists?: { name: string }[]; album?: { name?: string; images?: { url: string }[] } } } | null;
const headers = () => ({ Authorization: `Bearer ${localStorage.getItem("gallery-token")}` });

function Login({ done }: { done: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try { const response = await api.post("admin/login", { username, password }); localStorage.setItem("gallery-token", response.data.access_token); done(); }
    catch { setError("Credenciales incorrectas"); }
  }
  return <main className="counter-login"><form className="card spotify-login" onSubmit={submit}><img src={logo} alt="Logo de la Comisión de Celas" /><h1>Spotify</h1><p>Acceso de administración</p><input className="input" placeholder="Usuario" value={username} onChange={event => setUsername(event.target.value)} /><input className="input" type="password" placeholder="Contraseña" value={password} onChange={event => setPassword(event.target.value)} /><button className="btn">Entrar</button>{error && <p className="counter-error">{error}</p>}</form></main>;
}

export default function Spotify() {
  const [logged, setLogged] = useState(!!localStorage.getItem("gallery-token"));
  const [playlistOpen, setPlaylistOpen] = useState(false);
  const queryClient = useQueryClient();
  const connection = useQuery({ queryKey: ["spotify-connection"], queryFn: () => api.get<{ ok: boolean }>("spotify/has-token", { headers: headers() }).then(response => response.data), enabled: logged, retry: false });
  const playback = useQuery({ queryKey: ["spotify-playback"], queryFn: () => api.get<Playback>("spotify/state", { headers: headers() }).then(response => response.data), enabled: !!connection.data?.ok, refetchInterval: 4000, retry: false });
  const tracks = useQuery({ queryKey: ["spotify-tracks"], queryFn: () => api.get<{ tracks: Track[] }>("spotify/playlist-tracks", { headers: headers() }).then(response => response.data.tracks), enabled: !!connection.data?.ok && playlistOpen, retry: false });
  const action = useMutation({ mutationFn: (name: "prev" | "next" | "pause" | "resume") => api.post(`spotify/${name}`, undefined, { headers: headers() }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["spotify-playback"] }) });
  const chooseTrack = useMutation({ mutationFn: (uri: string) => api.post("spotify/play-track", { uri }, { headers: headers() }), onSuccess: () => { setPlaylistOpen(false); queryClient.invalidateQueries({ queryKey: ["spotify-playback"] }); } });

  if (connection.error && axios.isAxiosError(connection.error) && connection.error.response?.status === 401) { localStorage.removeItem("gallery-token"); return <Login done={() => setLogged(true)} />; }
  if (!logged) return <Login done={() => setLogged(true)} />;

  const item = playback.data?.item;
  const title = item?.name || "Sin reproducción activa";
  const artist = item?.artists?.map(person => person.name).join(", ") || "Conecta Spotify para empezar";
  const image = item?.album?.images?.[0]?.url;
  const isPlaying = !!playback.data?.is_playing;
  const message = connection.error ? "No se pudo conectar con Spotify." : !connection.data?.ok ? "Conecta una cuenta de Spotify para usar el reproductor." : "";

  async function connectSpotify() {
    try { const response = await api.get<{ url: string }>("admin/spotify/authorize-url", { headers: headers() }); window.location.assign(response.data.url); }
    catch { queryClient.invalidateQueries({ queryKey: ["spotify-connection"] }); }
  }

  return <main className="spotify-page"><header className="admin-nav spotify-nav"><div className="admin-brand"><span><img src={logo} alt="Logo de la Comisión de Celas" /></span><div><b>Galería</b><small>Administración</small></div></div><nav className="admin-nav-actions" aria-label="Secciones de administración"><a className="admin-nav-button" href="/admin?view=review">Revisión</a><a className="admin-nav-button" href="/admin?view=library">Biblioteca</a><a className="admin-nav-button" href="/admin?view=clips">Clips</a><a className="admin-nav-button active" href="/spotify" aria-current="page">Spotify</a></nav></header><section className="spotify-player" aria-label="Control de Spotify"><header><div><p className="spotify-eyebrow">COMISIÓN DE CELAS</p><h1>Nosa Señora 2026 CELAS</h1></div></header><div className={`spotify-artwork ${image ? "has-image" : ""}`}>{image ? <img src={image} alt={`Portada de ${item?.album?.name || title}`} /> : <img src={logo} alt="Logo de la Comisión de Celas" />}</div><div className="spotify-song"><h2>{title}</h2><p>{artist}</p></div>{connection.data?.ok && <div className="spotify-controls"><button aria-label="Canción anterior" disabled={action.isPending} onClick={() => action.mutate("prev")}>⏮</button><button className="spotify-play" aria-label={isPlaying ? "Pausar" : "Reproducir"} disabled={action.isPending} onClick={() => action.mutate(isPlaying ? "pause" : "resume")}>{isPlaying ? "❚❚" : "▶"}</button><button aria-label="Canción siguiente" disabled={action.isPending} onClick={() => action.mutate("next")}>⏭</button></div>}{connection.data?.ok && <button className="btn spotify-connect" onClick={connectSpotify}>Reconectar Spotify</button>}{!connection.data?.ok && <button className="btn spotify-connect" onClick={connectSpotify}>Conectar Spotify</button>}{message && <p className="spotify-message">{message}</p>}<section className="spotify-playlist"><button className="spotify-playlist-toggle" onClick={() => setPlaylistOpen(open => !open)} aria-expanded={playlistOpen}>ESCOGER CANCIÓN DE PLAYLIST <span>{playlistOpen ? "⌃" : "⌄"}</span></button>{playlistOpen && <div className="spotify-track-list">{tracks.isLoading && <p>Cargando canciones…</p>}{tracks.error && <p>No se pudieron cargar las canciones.</p>}{tracks.data?.length === 0 && <p>No hay canciones disponibles en esta playlist.</p>}{tracks.data?.map(track => <button key={track.uri} disabled={chooseTrack.isPending} onClick={() => chooseTrack.mutate(track.uri)}>{track.image && <img src={track.image} alt="" />}<span><strong>{track.name}</strong><small>{track.artists.join(", ")}</small></span></button>)}</div>}</section></section></main>;
}
