import type { CSSProperties } from "react";

export default function Odometer({ value, className = "" }: { value: number; className?: string }) {
  const digits = String(value).split("");
  return <output className={`odometer-value ${className}`} aria-live="polite" aria-label={`Valor actual: ${value}`} style={{ "--digits": digits.length } as CSSProperties}>
    {digits.map((digit, index) => <span className="odometer-digit" key={index} aria-hidden="true"><span className="odometer-track" style={{ "--digit": Number(digit) } as CSSProperties}>{Array.from({ length: 10 }, (_, numeral) => <span key={numeral}>{numeral}</span>)}</span></span>)}
  </output>;
}
