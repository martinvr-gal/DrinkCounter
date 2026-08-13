import axios from "axios"; import type { PhotoPage, Status } from "../types";
export const API_URL = import.meta.env.VITE_API_URL || "/api";
export const api = axios.create({ baseURL: API_URL });
export const imageUrl = (path: string) => `${API_URL}${path}`;
export const gallery = (state: string, page = 1, search = "") => api.get<PhotoPage>(`gallery/${state}`, { params: { page, page_size: 50, search } }).then(x => x.data);
export const counter = () => api.get<{ value: number }>("counter").then(x => x.data);
export const clips = () => api.get<string[]>("clips").then(x => x.data);
export const adminClips = () => api.get<string[]>("admin/clips").then(x => x.data);
export const uploadClip = (clip: File) => { const data = new FormData(); data.append("clip", clip); return api.post<{ url: string }>("admin/clips", data, { timeout: 0 }).then(x => x.data); };
export const deleteClip = (filename: string) => api.delete(`admin/clips/${encodeURIComponent(filename)}`);
export const ads = () => api.get<string[]>("ads").then(x => x.data);
export const adminAds = () => api.get<string[]>("admin/ads").then(x => x.data);
export const uploadAd = (ad: File) => { const data = new FormData(); data.append("ad", ad); return api.post<{ url: string }>("admin/ads", data).then(x => x.data); };
export const deleteAd = (filename: string) => api.delete(`admin/ads/${encodeURIComponent(filename)}`);
export const spotifyState = () => api.get<SpotifyPlayback>("spotify/state").then(x => x.data);
export const pauseSpotifyForClip = () => api.post<{ resume_after_clip: boolean }>("spotify/tv/clip-pause").then(x => x.data);
export const resumeSpotifyAfterClip = (resumeAfterClip: boolean) => api.post("spotify/tv/clip-resume", undefined, { params: { resume_after_clip: resumeAfterClip } });
export const pending = () => api.get<PhotoPage>("admin/pending").then(x => x.data);
export const updateStatus = (id: number, status: Status, version: number) => api.post(`admin/status/${id}`, { status, version }).then(x => x.data);

export type SpotifyPlayback = {
  is_playing?: boolean;
  progress_ms?: number;
  item?: { name?: string; duration_ms?: number; artists?: { name: string }[]; album?: { images?: { url: string }[] } };
} | null;

export const spotifyToken = () =>
  api
    .get<{ access_token: string }>("spotify/token")
    .then((x) => x.data);

export const spotifyTransfer = (
  deviceId: string,
  play = true
) =>
  api.post("spotify/transfer", {
    device_id: deviceId,
    play,
  });

export const spotifyStartLast = (
  deviceId: string
) =>
  api.post("spotify/start-last", {
    device_id: deviceId,
  });