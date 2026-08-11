import { useEffect, useRef, useState, type CSSProperties } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ads, clips, counter, gallery, imageUrl, pauseSpotifyForClip, resumeSpotifyAfterClip, spotifyState } from "../services/api";
import type { Photo } from "../types";
import Odometer from "../components/Odometer";

function websocketUrl() {
  const configuredUrl = import.meta.env.VITE_WS_URL;
  if (configuredUrl) return `${configuredUrl.replace(/\/$/, "").replace(/\/api$/, "")}/api/ws`;
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}/api/ws`;
}
const wsUrl = websocketUrl();
const seconds = Number(import.meta.env.VITE_TV_INTERVAL_SECONDS || 10);
const adEveryPhotos = Math.max(1, Number(import.meta.env.VITE_TV_AD_EVERY_PHOTOS || 10));
const clipStorageKey = "shown-tv-clips";
const photoStorageKey = "last-shown-tv-photo";
const equalizerBars = [42, 58, 31, 66, 38, 54, 72, 27, 62, 34, 55, 30, 48, 39, 64];

function duration(value?: number) {
  const total = Math.max(0, Math.floor((value || 0) / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, "0")}`;
}

export default function Tv() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["tv"], queryFn: () => gallery("approved"), refetchInterval: 15000 });
  const { data: counterData } = useQuery({ queryKey: ["tv-counter"], queryFn: counter, refetchInterval: 2000 });
  const { data: clipUrls = [] } = useQuery({ queryKey: ["tv-clips"], queryFn: clips });
  const { data: adUrls = [] } = useQuery({ queryKey: ["tv-ads"], queryFn: ads });
  const { data: playback } = useQuery({ queryKey: ["tv-spotify"], queryFn: spotifyState, refetchInterval: 2000, retry: false });
  const [index, setIndex] = useState<number | null>(null);
  const [currentClip, setCurrentClip] = useState<string | null>(null);
  const [currentAd, setCurrentAd] = useState<string | null>(null);
  const [photosShownSinceAd, setPhotosShownSinceAd] = useState(0);
  const lastCounterValue = useRef<number | null>(null);
  const restoredPhoto = useRef(false);
  const shownClips = useRef(new Set(localStorage.getItem(clipStorageKey)?.split(",").filter(Boolean) || []));
  const video = useRef<HTMLVideoElement>(null);
  const resumeAfterClip = useRef(false);
  const images = data?.items || [];

  useEffect(() => {
    if (!images.length) {
      setIndex(null);
      return;
    }
    if (restoredPhoto.current) return;

    restoredPhoto.current = true;
    const lastPhotoId = Number(localStorage.getItem(photoStorageKey));
    const lastIndex = images.findIndex(photo => photo.id === lastPhotoId);
    setIndex(lastIndex === -1 ? 0 : (lastIndex + 1) % images.length);
    setPhotosShownSinceAd(1);
  }, [images]);

  useEffect(() => {
    const id = setInterval(() => {
      if (!images.length) return;
      if (currentAd) {
        setCurrentAd(null);
        setIndex(current => ((current ?? -1) + 1) % images.length);
        setPhotosShownSinceAd(1);
        return;
      }
      if (adUrls.length && photosShownSinceAd >= adEveryPhotos) {
        setCurrentAd(current => adUrls[(adUrls.indexOf(current || "") + 1) % adUrls.length]);
        setPhotosShownSinceAd(0);
        return;
      }
      setIndex(current => ((current ?? -1) + 1) % images.length);
      setPhotosShownSinceAd(current => current + 1);
    }, seconds * 1000);
    return () => clearInterval(id);
  }, [adUrls, currentAd, images.length, photosShownSinceAd]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = () => { queryClient.invalidateQueries({ queryKey: ["tv"] }); queryClient.invalidateQueries({ queryKey: ["tv-clips"] }); queryClient.invalidateQueries({ queryKey: ["tv-ads"] }); };
    return () => ws.close();
  }, [queryClient]);

  useEffect(() => {
    const value = counterData?.value;
    if (value === undefined) return;
    const previousValue = lastCounterValue.current;
    lastCounterValue.current = value;
    if (currentClip || previousValue === null || value <= previousValue || Math.floor(value / 100) <= Math.floor(previousValue / 100) || !clipUrls.length) return;

    const available = clipUrls.filter(url => !shownClips.current.has(url));
    const choices = available.length ? available : clipUrls;
    if (!available.length) shownClips.current.clear();
    const clip = choices[Math.floor(Math.random() * choices.length)];
    shownClips.current.add(clip);
    localStorage.setItem(clipStorageKey, [...shownClips.current].join(","));
    setCurrentClip(clip);
  }, [clipUrls, counterData?.value, currentClip]);

  useEffect(() => {
    if (!currentClip || !video.current) return;
    const clip = video.current;
    clip.currentTime = 0;
    clip.muted = false;
    void pauseSpotifyForClip()
      .then(result => { resumeAfterClip.current = result.resume_after_clip; })
      .catch(() => { resumeAfterClip.current = false; })
      .finally(() => { clip.play().catch(() => undefined); });
  }, [currentClip]);

  function finishClip() {
    const shouldResume = resumeAfterClip.current;
    resumeAfterClip.current = false;
    setCurrentClip(null);
    if (shouldResume) void resumeSpotifyAfterClip(true).catch(() => undefined);
  }

  const photo: Photo | undefined = index === null ? undefined : images[index];
  useEffect(() => {
    if (photo) localStorage.setItem(photoStorageKey, String(photo.id));
  }, [photo]);
  const track = playback?.item;
  const progress = Math.min(100, ((playback?.progress_ms || 0) / (track?.duration_ms || 1)) * 100);
  return <main className="tv-screen"><section className="tv-gallery">{currentAd ? <img src={currentAd} alt="Anuncio" className="tv-photo tv-ad" /> : photo ? <><img src={imageUrl(photo.url)} alt={`Fotografía de ${photo.user_name}`} className="tv-photo"/><div className="tv-photo-author">{photo.user_name}</div></> : <p className="tv-empty">Esperando fotografías…</p>}</section><aside className="tv-sidebar"><div className="tv-counter" aria-label={`Contador: ${counterData?.value || 0}`}><div className="tv-counter-panel"><span className="tv-counter-label">Contador</span><Odometer value={counterData?.value || 0} className="tv-counter-value" /></div></div><section className="tv-spotify-player" aria-label="Reproductor de Spotify"><p className="tv-spotify-brand">Nosa Señora 2026 Celas</p><div className="tv-spotify-main">{track?.album?.images?.[0]?.url ? <img src={track.album.images[0].url} alt="Portada del álbum" className="tv-spotify-art" /> : <div className="tv-spotify-art tv-spotify-placeholder">♪</div>}<div className="tv-spotify-copy"><h2>{track?.name || "Spotify preparado"}</h2><p>{track?.artists?.map(artist => artist.name).join(", ") || "Abre Spotify en un dispositivo para reproducir"}</p><div className="tv-spotify-progress" aria-label={`${duration(playback?.progress_ms)} de ${duration(track?.duration_ms)}`}><span style={{ width: `${progress}%` }} /></div><div className="tv-spotify-times"><span>{duration(playback?.progress_ms)}</span><span>{duration(track?.duration_ms)}</span></div></div></div><div className={`tv-equalizer ${playback?.is_playing ? "is-playing" : ""}`} aria-label={playback?.is_playing ? "Reproduciendo" : "En pausa"}>{equalizerBars.map((height, index) => <i key={index} style={{ "--bar-height": `${height}%`, "--bar-delay": `${index * 90}ms` } as CSSProperties} />)}</div></section></aside>{currentClip && <div className="tv-clip-overlay"><video ref={video} src={currentClip} playsInline onEnded={finishClip} onError={finishClip} /></div>}</main>;
}
