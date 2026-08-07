import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, counter } from "../services/api";
import Odometer from "../components/Odometer";

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
      const response = await api.post("admin/login", { username, password });
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
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [subtractAmount, setSubtractAmount] = useState("1");
  const [setAmount, setSetAmount] = useState("");
  const [correction, setCorrection] = useState<{ action: "decrement" | "set"; amount: number; nextValue: number } | null>(null);
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["counter-control"], queryFn: counter, enabled: logged, refetchInterval: 2000 });
  const change = useMutation({
    mutationFn: async ({ action, amount }: { action: "increment" | "decrement" | "set"; amount: number }) => {
      if (action === "set") await api.post("/counter/set", { value: amount }, { headers: authHeaders() });
      else await api.post(`/counter/${action}`, { amount }, { headers: authHeaders() });
    },
    onSuccess: () => { setError(""); setCorrection(null); queryClient.invalidateQueries({ queryKey: ["counter-control"] }); },
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

  function requestCorrection(action: "decrement" | "set") {
    const amount = Number(action === "decrement" ? subtractAmount : setAmount);
    const valid = action === "decrement" ? Number.isInteger(amount) && amount >= 1 : Number.isInteger(amount) && amount >= 0;
    if (!valid) { setError(action === "decrement" ? "Introduce un número entero mayor que cero." : "Introduce un número entero igual o mayor que cero."); return; }
    setError("");
    setCorrection({ action, amount, nextValue: action === "decrement" ? Math.max(0, (data?.value ?? 0) - amount) : amount });
  }

  function confirmCorrection() {
    if (correction) change.mutate({ action: correction.action, amount: correction.amount });
  }

  if (!logged) return <Login done={() => setLogged(true)} />;

  const currentValue = data?.value ?? 0;
  return <main className="counter-control"><section className="counter-card"><p>Contador de cubatas</p><Odometer value={currentValue} /><div className="counter-amounts">{Array.from({ length: 10 }, (_, index) => index + 1).map(amount => <button key={amount} className="counter-amount" disabled={change.isPending} onClick={() => add(amount)}>+{amount}</button>)}</div><form className="counter-custom" onSubmit={addCustom}><input className="input" type="number" min="1" step="1" inputMode="numeric" placeholder="Cantidade personalizada" value={customAmount} onChange={event => setCustomAmount(event.target.value)} /><button className="counter-custom-button" disabled={change.isPending}>Sumar</button></form><section className="counter-advanced"><button className="counter-advanced-toggle" type="button" onClick={() => setAdvancedOpen(open => !open)} aria-expanded={advancedOpen}>▾ Opcións avanzadas</button>{advancedOpen && <div className="counter-corrections"><label>Cantidade a restar<input className="input" type="number" min="1" step="1" inputMode="numeric" value={subtractAmount} onChange={event => setSubtractAmount(event.target.value)} /></label><label>Valor a establecer<input className="input" type="number" min="0" step="1" inputMode="numeric" placeholder="Ej. 200" value={setAmount} onChange={event => setSetAmount(event.target.value)} /></label><button className="counter-button subtract" disabled={change.isPending} onClick={() => requestCorrection("decrement")}>Restar</button><button className="counter-button set" disabled={change.isPending} onClick={() => requestCorrection("set")}>Establecer</button></div>}</section>{error && <p className="counter-error">{error}</p>}</section>{correction && <div className="counter-modal-backdrop" role="presentation"><section className="counter-modal" role="dialog" aria-modal="true" aria-labelledby="correction-title"><h2 id="correction-title">Confirmar corrección</h2><p>¿Estás seguro de que queres corrixir o valor {currentValue} polo valor {correction.nextValue}?</p><div><button className="counter-modal-cancel" type="button" disabled={change.isPending} onClick={() => setCorrection(null)}>Cancelar</button><button className="counter-modal-confirm" type="button" disabled={change.isPending} onClick={confirmCorrection}>Confirmar</button></div></section></div>}</main>;
}
