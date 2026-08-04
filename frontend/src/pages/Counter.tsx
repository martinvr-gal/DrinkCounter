import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, counter } from "../services/api";

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem("gallery-token")}` };
}

function Login({ done }: { done: () => void }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    try {
      const response = await api.post("/admin/login", { username, password });
      localStorage.setItem("gallery-token", response.data.access_token);
      done();
    } catch {
      setError("Credenciales incorrectas");
    }
  }

  return <main className="counter-login"><form className="card" onSubmit={submit}><h1>Control del contador</h1><input className="input" placeholder="Usuario" value={username} onChange={event => setUsername(event.target.value)} /><input className="input" type="password" placeholder="Contraseña" value={password} onChange={event => setPassword(event.target.value)} /><button className="btn">Entrar</button><p>{error}</p></form></main>;
}

export default function Counter() {
  const [logged, setLogged] = useState(!!localStorage.getItem("gallery-token"));
  const [error, setError] = useState("");
  const [customAmount, setCustomAmount] = useState("");
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["counter-control"], queryFn: counter, enabled: logged, refetchInterval: 2000 });
  const change = useMutation({
    mutationFn: ({ action, amount }: { action: "increment" | "decrement"; amount: number }) => api.post(`/api/counter/${action}`, { amount }, { headers: authHeaders() }),
    onSuccess: () => { setError(""); queryClient.invalidateQueries({ queryKey: ["counter-control"] }); },
    onError: () => setError("No se pudo actualizar el contador. Inicia sesión de nuevo si ha caducado."),
  });

  function add(amount: number) { change.mutate({ action: "increment", amount }); }
  function addCustom(event: React.FormEvent) {
    event.preventDefault();
    const amount = Number(customAmount);
    if (!Number.isInteger(amount) || amount < 1) { setError("Introduce un número entero mayor que cero."); return; }
    add(amount);
    setCustomAmount("");
  }

  if (!logged) return <Login done={() => setLogged(true)} />;

  return <main className="counter-control"><a className="counter-back" href="/admin">← Administración</a><section className="counter-card"><p>Contador de cubatas</p><strong aria-live="polite">{data?.value ?? 0}</strong><div className="counter-amounts">{Array.from({ length: 10 }, (_, index) => index + 1).map(amount => <button key={amount} className="counter-amount" disabled={change.isPending} onClick={() => add(amount)}>+{amount}</button>)}</div><form className="counter-custom" onSubmit={addCustom}><input className="input" type="number" min="1" step="1" inputMode="numeric" placeholder="Cantidad personalizada" value={customAmount} onChange={event => setCustomAmount(event.target.value)} /><button className="counter-custom-button" disabled={change.isPending}>Sumar</button></form><button className="counter-button subtract" disabled={change.isPending} onClick={() => change.mutate({ action: "decrement", amount: 1 })} aria-label="Restar un cubata">Corregir: restar 1</button>{error && <p className="counter-error">{error}</p>}</section></main>;
}
