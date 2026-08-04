import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { clips, counter, gallery, imageUrl } from "../services/api";
import type { Photo } from "../types";

const wsUrl = (import.meta.env.VITE_WS_URL || "ws://localhost:8000") + "/ws";
const seconds = Number(import.meta.env.VITE_TV_INTERVAL_SECONDS || 10);
const clipStorageKey = "shown-tv-clips";

export default function Tv() {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["tv"], queryFn: () => gallery("approved") });
  const { data: counterData } = useQuery({ queryKey: ["tv-counter"], queryFn: counter, refetchInterval: 2000 });
  const { data: clipUrls = [] } = useQuery({ queryKey: ["tv-clips"], queryFn: clips });
  const [index, setIndex] = useState(0);
  const [currentClip, setCurrentClip] = useState<string | null>(null);
  const lastCounterValue = useRef<number | null>(null);
  const shownClips = useRef(new Set(localStorage.getItem(clipStorageKey)?.split(",").filter(Boolean) || []));
  const video = useRef<HTMLVideoElement>(null);
  const images = data?.items || [];

  useEffect(() => {
    const id = setInterval(() => setIndex(current => images.length ? (current + 1) % images.length : 0), seconds * 1000);
    return () => clearInterval(id);
  }, [images.length]);

  useEffect(() => {
    const ws = new WebSocket(wsUrl);
    ws.onmessage = () => queryClient.invalidateQueries({ queryKey: ["tv"] });
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
    video.current.currentTime = 0;
    video.current.muted = false;
    video.current.play().catch(() => undefined);
  }, [currentClip]);

  const photo: Photo | undefined = images[index];
  return <main className="tv-screen"><section className="tv-gallery">{photo && <><img src={imageUrl(photo.url)} alt={`Fotografía de ${photo.user_name}`} className="tv-photo"/><div className="tv-photo-author">{photo.user_name}</div></>}{!photo && <p className="tv-empty">Esperando fotografías…</p>}</section><aside className="tv-counter" aria-live="polite" aria-label={`Contador: ${counterData?.value || 0}`}><span className="tv-counter-label">Contador</span><strong className="tv-counter-value">{counterData?.value || 0}</strong></aside>{currentClip && <div className="tv-clip-overlay"><video ref={video} src={imageUrl(currentClip)} playsInline onEnded={() => setCurrentClip(null)} /></div>}</main>;
}
