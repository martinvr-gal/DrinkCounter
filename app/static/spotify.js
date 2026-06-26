let player;
let currentDeviceId;
let interval;

window.onSpotifyWebPlaybackSDKReady = async () => {

  const token = await fetch("/token")
    .then(r => r.json());

  player = new Spotify.Player({
    name: "CubataCounter",
    getOAuthToken: cb => cb(token.access_token)
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

  player.addListener('player_state_changed', (state) => {
    if (!state) return;

    const track = state.track_window.current_track;

    document.getElementById("title").textContent = track.name;
    document.getElementById("artist").textContent =
      track.artists.map(a => a.name).join(", ");

    document.getElementById("cover").src =
      track.album.images[0].url;

    document.getElementById("play").textContent =
      state.paused ? "▶" : "⏸";

      if (!state) return;

    const current = state.position;
    const duration = state.duration;

    const progressPercent = (current / duration) * 100;

    document.getElementById("progress-bar").style.width =
    progressPercent + "%";

    // tempos
    document.getElementById("current-time").textContent =
    formatTime(current);

    document.getElementById("total-time").textContent =
    formatTime(duration);

    clearInterval(interval);

    interval = setInterval(() => {

    if (!state || state.paused) return;

    state.position += 1000;

    const progress = (state.position / state.duration) * 100;

    document.getElementById("progress-bar").style.width =
        progress + "%";

    document.getElementById("current-time").textContent =
        formatTime(state.position);

    }, 1000);
  });

  await player.connect();
};

document.getElementById("play").onclick = async () => {

  const res = await fetch("/has-token");
  const data = await res.json();

  if (!data.ok) {
    window.location.href = "/login";
    return;
  }

  await player.togglePlay();
};

document.getElementById("next").onclick = async () => {
  await player.nextTrack();
};

document.getElementById("prev").onclick = async () => {
  await player.previousTrack();
};

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

  document.getElementById("playlist-name").textContent = data.name;

  return data;
}

function formatTime(ms) {
  const sec = Math.floor(ms / 1000);
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${s.toString().padStart(2, "0")}`;
}

