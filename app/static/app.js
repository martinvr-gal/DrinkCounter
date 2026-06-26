const counterValue = document.getElementById("counter-value");
const amountInput = document.getElementById("amount");
const decrementValueInput = document.getElementById("decrement-value");
const setValueInput = document.getElementById("set-value");
const message = document.getElementById("message");
const hasControls = Boolean(document.querySelector("[data-action]"));

async function requestJson(url, method, body) {
  const response = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "Request failed");
  }
  return payload;
}

function setMessage(text, isError = false) {
  if (!message) {
    return;
  }

  message.textContent = text;
  message.dataset.state = isError ? "error" : "ok";
}

function handleCounterValue(nextValue) {
  if (Number.isNaN(nextValue)) {
    return;
  }

  if (counterValue) {
    counterValue.textContent = nextValue;
  }
}

async function refreshCounter() {
  const response = await fetch("/api/counter");
  const payload = await response.json();
  const nextValue = Number(payload.value);

  handleCounterValue(nextValue);
  return nextValue;
}

async function incrementBy(amount) {
  await requestJson("/api/counter/increment", "POST", { amount });
  await refreshCounter();
}

async function decrementBy(amount) {
  await requestJson("/api/counter/decrement", "POST", { amount });
  await refreshCounter();
}

async function setCounter(value) {
  await requestJson("/api/counter/set", "POST", { value });
  await refreshCounter();
}

if (hasControls) {
  document.querySelectorAll("button[data-action]").forEach((button) => {
    button.addEventListener("click", async () => {
      const action = button.dataset.action;
      const amount = Number(amountInput?.value);
      const decrementAmount = Number(decrementValueInput?.value);
      const value = Number(setValueInput?.value);
      const fixedAmount = Number(button.dataset.amount);

      try {
        const currentValue = Number(counterValue?.textContent ?? 0);

        if (action === "increment-fixed") {
          await incrementBy(fixedAmount);
          setMessage(`Sumado ${fixedAmount}`);
          return;
        }

        if (action === "increment-custom") {
          await incrementBy(amount);
          setMessage(`Sumado ${amount}`);
          return;
        }

        if (action === "decrement") {
          const futureValue = Math.max(
            0,
            currentValue - decrementAmount
          );

          const confirmed = await showConfirmation(
            currentValue,
            futureValue
          );

          if (!confirmed) return;

          await decrementBy(decrementAmount);
          setMessage(`Restado ${decrementAmount}`);
          return;
        }

        if (action === "set") {
          const confirmed = await showConfirmation(
            currentValue,
            value
          );

          if (!confirmed) return;

          await setCounter(value);
          setMessage(`Seteado a ${value}`);
          return;
        }
      } catch (error) {
        setMessage(error.message, true);
      }
    });
  });
}

refreshCounter().catch((error) => {
  setMessage(error.message, true);
  if (!message) {
    console.error(error);
  }
});

setInterval(() => {
  refreshCounter().catch((error) => {
    setMessage(error.message, true);
    if (!message) {
      console.error(error);
    }
  });
}, 2000);

async function showConfirmation(currentValue, futureValue) {
  const dialog = document.getElementById("confirm-dialog");
  const message = document.getElementById("confirm-message");

  message.textContent =
    `Estás seguro que queres corrixir o valor ${currentValue} polo valor ${futureValue}?`;

  dialog.showModal();

  return new Promise((resolve) => {
    dialog.addEventListener(
      "close",
      () => {
        resolve(dialog.returnValue === "confirm");
      },
      { once: true }
    );
  });
}

window.onSpotifyWebPlaybackSDKReady = () => {

 const player = new Spotify.Player({
   name: "CubataCounter",
   getOAuthToken: cb => {
      fetch("/token")
      .then(r => r.json())
      .then(data => cb(data.access_token))
   }
 });

 player.connect();

}

await fetch(
 'https://api.spotify.com/v1/me/player/play',
 {
   method:'PUT',
   headers:{
      Authorization:'Bearer '+token
   },
   body:JSON.stringify({
      context_uri:
      'spotify:playlist:0F9vXOWHObYhfiC7udX0do'
   })
 }
)
