const SPOTIFY_PLAYLIST_ID = document.querySelector('meta[name="spotify-playlist-id"]')?.content || "";

let player;
let currentDeviceId;
let interval;
let currentCover = null;
let selectedTrackUri = null;
let currentTrackUri = null;
let currentTrackKey = null;

function setText(id, value) {
  const el = document.getElementById(id);

  if (el) {
    el.textContent = value;
  }
}

function setImage(id, value) {
  const el = document.getElementById(id);

  if (el) {
    el.src = value;
  }
}

async function getToken() {

  const res = await fetch("/token");

  if (!res.ok) {
    window.location.href="/login";
    throw new Error();
  }

  return await res.json();
}

async function loadPlaylistName() {
  const token = await fetch("/token").then(r => r.json());

  const data = await fetch(
    `https://api.spotify.com/v1/playlists/${SPOTIFY_PLAYLIST_ID}`,
    {
      headers: {
        Authorization: "Bearer " + token.access_token
      }
    }
  ).then(r => r.json());

  setText("admin-playlist-name", data.name);
  await loadPlaylistTracks();
}

async function startPlaylistPlayback(deviceId) {
  if (!deviceId || !SPOTIFY_PLAYLIST_ID) return;

  const token = await getToken();
  const headers = {
    Authorization: `Bearer ${token.access_token}`,
    "Content-Type": "application/json"
  };

  await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${deviceId}`, {
    method: "PUT",
    headers,
    body: JSON.stringify({
      context_uri: `spotify:playlist:${SPOTIFY_PLAYLIST_ID}`,
      position_ms: 0
    })
  });

  await fetch(`https://api.spotify.com/v1/me/player/shuffle?state=true&device_id=${deviceId}`, {
    method: "PUT",
    headers
  });

  await new Promise((resolve) => setTimeout(resolve, 700));

  await fetch(`https://api.spotify.com/v1/me/player/shuffle?state=true&device_id=${deviceId}`, {
    method: "PUT",
    headers
  });
}

window.onSpotifyWebPlaybackSDKReady = async () => {

  const token = await fetch("/token").then(r => r.json());

  player = new Spotify.Player({
    name: "CubataCounter",
    getOAuthToken: async cb => {

      const token = await getToken();

      cb(token.access_token);

    }
  });

  player.addListener('ready', async ({ device_id }) => {

    currentDeviceId = device_id;

    const token = await fetch("/token").then(r => r.json());

    await loadPlaylistInfo(token.access_token);
    await startPlaylistPlayback(device_id);

  });

  player.addListener("not_ready", () => {

      console.log("Reconectando");

      setTimeout(() => {
        player.connect();
      }, 3000);

    });

  player.addListener("player_state_changed", (state) => {

    if (!state) return;

    const track = state.track_window.current_track;

    // TV
    currentTrackUri = track.uri || "";
    currentTrackKey = normalizeTrackKey(track.id || currentTrackUri);
    setText("title", track.name);
    setText("artist", track.artists.map(a => a.name).join(", "));
    setImage("cover", track.album.images[0].url);

    // ADMIN
    updateAdminPlayer(track, state.paused);

    // progreso TV
    clearInterval(interval);

    const progressBar = document.getElementById("progress-bar");

    if (progressBar) {
      let position = state.position;
      const updateProgress = () => {
        const progress = (position/state.duration) * 100;
        progressBar.style.width = progress + "%";
        setText("current-time", formatTime(position));
        setText("total-time", formatTime(state.duration));
      };

      updateProgress();

      if (!state.paused) {
        interval = setInterval(
          () => {
            position += 1000;

            if (position > state.duration) {
              clearInterval(interval);
              return;
            }
            updateProgress();
          },
          1000
        );
      }
    }

    // fondo
    const nextCover = track.album.images[0].url;

    if (currentCover !== nextCover) {
      currentCover = nextCover;
      updateBackground(nextCover);
    }

    if (!state.shuffle) {
      setShuffle(true).catch(() => {});
    }

    // ecualizador
    const eq = document.getElementById("equalizer");

    if(eq){
      eq.classList.toggle("paused", state.paused);
    }
  });

  await player.connect();
};

document.getElementById("admin-play")?.addEventListener("click", 
  async ()=> {
    await fetch("/api/spotify/play", { method:"POST" });
  }
);

document.getElementById("admin-next")?.addEventListener("click",
  async ()=> {
    await fetch("/api/spotify/next", { method:"POST" });
  }
);


document.getElementById("admin-prev")?.addEventListener("click",
  async ()=> {
    await fetch("/api/spotify/prev", { method:"POST" });
  }
);

async function setShuffle(state) {
  const token = await fetch("/token").then(r => r.json());

  await fetch(`https://api.spotify.com/v1/me/player/shuffle?state=${state}&device_id=${currentDeviceId}`, {
    method: "PUT",
    headers: {
      Authorization: "Bearer " + token.access_token
    }
  });
}

async function loadPlaylistInfo(token) {
  const res = await fetch(`https://api.spotify.com/v1/playlists/${SPOTIFY_PLAYLIST_ID}`, {
    headers: {
      Authorization: "Bearer " + token
    }
  });

  const data = await res.json();

  setText("playlist-name", data.name);

  return data;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function normalizeTrackKey(value) {
  if (!value) return "";
  const text = String(value).trim();
  if (text.startsWith("spotify:track:")) {
    return text.split(":").pop();
  }
  return text;
}

function updateTrackSelection(list, uri) {
  const targetKey = normalizeTrackKey(uri);
  const items = list.querySelectorAll(".track-list-item");
  items.forEach((item) => {
    const itemKey = normalizeTrackKey(item.dataset.id || item.dataset.uri || item.dataset.trackKey);
    const isPlaying = itemKey === currentTrackKey;
    item.classList.toggle("currently-playing", isPlaying);
  });
}

function updateTrackClickSelection(list, uri) {
  const targetKey = normalizeTrackKey(uri);
  const items = list.querySelectorAll(".track-list-item");
  items.forEach((item) => {
    const itemKey = normalizeTrackKey(item.dataset.id || item.dataset.uri || item.dataset.trackKey);
    const isSelected = itemKey === targetKey;
    item.classList.toggle("selected", isSelected);
  });
}

async function loadPlaylistTracks() {
  const list = document.getElementById("track-list");
  if (!list) return;

  list.replaceChildren();
  const loadingMessage = document.createElement("div");
  loadingMessage.className = "track-list-empty";
  loadingMessage.textContent = "Cargando cancións…";
  list.appendChild(loadingMessage);

  try {
    const res = await fetch("/api/spotify/playlist-tracks");
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      throw new Error(data.error || "Non se puideron cargar as cancións da playlist.");
    }

    list.replaceChildren();

    if (!data.tracks?.length) {
      const emptyMessage = document.createElement("div");
      emptyMessage.className = "track-list-empty";
      emptyMessage.textContent = "Non hai cancións dispoñibles nesta playlist.";
      list.appendChild(emptyMessage);
      selectedTrackUri = null;
      return;
    }

    data.tracks.forEach((track) => {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "track-list-item";
      button.dataset.uri = track.uri || "";
      button.dataset.id = normalizeTrackKey(track.uri || track.id || "");
      button.innerHTML = `
        <span class="track-list-title">${escapeHtml(track.name)}</span>
        <span class="track-list-meta">${escapeHtml(track.artists.join(", "))}</span>
      `;

      button.addEventListener("dblclick", async () => {
        selectedTrackUri = track.uri;
        updateTrackClickSelection(list, selectedTrackUri);
        await playSelectedTrack();
      });

      button.addEventListener("click", () => {
        selectedTrackUri = track.uri;
        updateTrackClickSelection(list, selectedTrackUri);
      });

      list.appendChild(button);
    });

    if (currentTrackKey) {
      updateTrackSelection(list, currentTrackKey);
      selectedTrackUri = currentTrackUri || data.tracks[0]?.uri || "";
    } else if (!selectedTrackUri && data.tracks[0]?.uri) {
      selectedTrackUri = data.tracks[0].uri;
      updateTrackSelection(list, selectedTrackUri);
    }

  } catch (error) {
    list.innerHTML = `<div class="track-list-empty">${escapeHtml(error.message || "Non se puideron cargar as cancións.")}</div>`;
    selectedTrackUri = null;
  }
}

async function playSelectedTrack() {
  const list = document.getElementById("track-list");
  const uri = selectedTrackUri || list?.querySelector(".track-list-item.selected")?.dataset.uri;
  if (!uri) return;

  await fetch("/api/spotify/play-track", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ uri }),
  });
}

function formatTime(ms) {
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

async function extractGradientFromCover(url) {
  const img = new Image();
  img.crossOrigin = "anonymous";

  await new Promise((resolve, reject) => {
    img.onload = resolve;
    img.onerror = reject;
    img.src = url;
  });

  const canvas = document.createElement("canvas");
  const ctx = canvas.getContext("2d");

  canvas.width = 1;
  canvas.height = 1;
  ctx.drawImage(img, 0, 0, 1, 1);

  const c = ctx.getImageData(0, 0, 1, 1).data;
  return `radial-gradient(circle, rgba(${c[0]},${c[1]},${c[2]},0.9), #121212)`;
}

function transitionBackground(element, color) {
  element.style.setProperty("--bg-next", color);
  element.classList.add("fade");

  setTimeout(() => {
    element.style.setProperty("--bg-current", color);
    element.classList.remove("fade");
  }, 1500);
}

async function updateBackground(url) {
  const player = document.getElementById("player");
  if (!player) return;

  const color = await extractGradientFromCover(url);
  transitionBackground(player, color);
}

async function updateAdminBackground(url) {
  const spotifyMini = document.querySelector(".spotify-mini");
  if (!spotifyMini) return;

  const color = await extractGradientFromCover(url);
  transitionBackground(spotifyMini, color);
}

let currentAdminCover = null;

function updateAdminPlayer(track, paused) {
  const cover = document.getElementById("admin-cover");

  if (!cover) return;

  currentTrackUri = track.uri || "";
  currentTrackKey = normalizeTrackKey(track.id || currentTrackUri);

  const trackList = document.getElementById("track-list");
  if (trackList) {
    updateTrackSelection(trackList, currentTrackKey);
  }

  cover.src = track.album.images[0].url;
  document.getElementById("admin-title").textContent = track.name;
  document.getElementById("admin-artist").textContent = track.artists.map(a=>a.name).join(", ");
  document.getElementById("admin-play").textContent = paused ? "▶" : "⏸";

  if (track.album && track.album.images && track.album.images[0] && track.album.images[0].url) {
    const nextCover = track.album.images[0].url;
    if (currentAdminCover !== nextCover) {
      currentAdminCover = nextCover;
      updateAdminBackground(nextCover);
    }
  }
}

async function syncSpotify(){

  const res = await fetch("/api/spotify/state");

  if(!res.ok){return;}

  const state = await res.json();

  if(!state) return;

  updateAdminPlayer(state.item, !state.is_playing);

}

setInterval(syncSpotify, 1000);

loadPlaylistName();
