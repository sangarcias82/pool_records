/** Display helpers that follow the app language (not the browser locale). */
import type { Lang } from "../api/types";

const LOCALES: Record<Lang, string> = { en: "en-US", es: "es-MX" };

/** At least the parameter's ``decimals``, up to 4 so extra precision that affected the status is never hidden. */
export function formatNumber(value: number, decimals: number, lang: Lang): string {
  return new Intl.NumberFormat(LOCALES[lang], {
    minimumFractionDigits: decimals,
    maximumFractionDigits: Math.max(decimals, 4),
  }).format(value);
}

/** ``7.2 – 7.8``, ``≤ 0.2``, ``≥ 650`` or ``—`` (no bounds), with the unit when there is one. */
export function formatRange(min: number | null, max: number | null, decimals: number, lang: Lang, unit?: string | null): string {
  const n = (v: number) => formatNumber(v, decimals, lang);
  const text = min !== null && max !== null ? `${n(min)} – ${n(max)}` : max !== null ? `≤ ${n(max)}` : min !== null ? `≥ ${n(min)}` : "—";
  return unit && text !== "—" ? `${text} ${unit}` : text;
}

/** Local date and time of an ISO 8601 instant in the app language. */
export function formatDateTime(iso: string, lang: Lang, timeZone?: string): string {
  return new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium", timeStyle: "short", timeZone }).format(new Date(iso));
}

/** Date and time as separate strings (two-line table cells). */
export function formatDateTimeParts(iso: string, lang: Lang, timeZone?: string): { date: string; time: string } {
  const when = new Date(iso);
  return {
    date: new Intl.DateTimeFormat(LOCALES[lang], { dateStyle: "medium", timeZone }).format(when),
    time: new Intl.DateTimeFormat(LOCALES[lang], { timeStyle: "short", timeZone }).format(when),
  };
}

const pad = (n: number) => String(n).padStart(2, "0");

/** ``YYYY-MM-DDTHH:MM`` in the browser's zone, the format of ``<input type="datetime-local">``. */
export function toLocalInputValue(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/** Local ``datetime-local`` value -> ISO 8601 UTC (``...Z``) for the API; blank or invalid -> undefined (server uses now). */
export function localInputToIso(value: string): string | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}
