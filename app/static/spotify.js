let player;
let currentDeviceId;
let interval;
let currentCover = null;

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
    "https://api.spotify.com/v1/playlists/0F9vXOWHObYhfiC7udX0do",
    {
      headers: {
        Authorization: "Bearer " + token.access_token
      }
    }
  ).then(r => r.json());

  setText("admin-playlist-name", data.name);
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
    isReady = true;

    const token = await fetch("/token").then(r => r.json());

    await loadPlaylistInfo(token.access_token);

    await fetch(`https://api.spotify.com/v1/me/player/play?device_id=${device_id}`, {
      method: "PUT",
      headers: {
        Authorization: "Bearer " + token.access_token,
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        context_uri: "spotify:playlist:0F9vXOWHObYhfiC7udX0do"
      })
    });

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
  const playlistId = "0F9vXOWHObYhfiC7udX0do";

  const res = await fetch(`https://api.spotify.com/v1/playlists/${playlistId}`, {
    headers: {
      Authorization: "Bearer " + token
    }
  });

  const data = await res.json();

  setText("playlist-name", data.name);

  return data;
}

function formatTime(ms) {
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

function updateBackground(url) {
  const img = new Image();

  img.crossOrigin = "anonymous";

  img.src = url;

  img.onload = () => {
    const canvas = document.createElement("canvas");
    const ctx = canvas.getContext("2d");

    canvas.width = 1;
    canvas.height = 1;
    ctx.drawImage(img, 0, 0, 1, 1);

    const c = ctx.getImageData(0, 0, 1, 1).data;
    const color = `radial-gradient(circle, rgba(${c[0]},${c[1]},${c[2]},0.9), #121212)`;
    const player = document.getElementById("player");

    if(!player) return;

    player.style.setProperty("--bg-next", color);
    player.classList.add("fade");

    setTimeout(() => {
      player.style.setProperty("--bg-current", color);
      player.classList.remove("fade");
    }, 1500);
  };
}

function updateAdminPlayer(track, paused) {
  const cover = document.getElementById("admin-cover");

  if (!cover) return;

  cover.src = track.album.images[0].url;
  document.getElementById("admin-title").textContent = track.name;
  document.getElementById("admin-artist").textContent = track.artists.map(a=>a.name).join(", ");
  document.getElementById("admin-play").textContent = paused ? "▶" : "⏸";
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
