import { en } from "./en";
import { es } from "./es";
import type { Lang } from "../api/types";

export const DICTIONARIES: Record<Lang, Record<string, string>> = { en, es };
export const LANGS: Lang[] = ["en", "es"];
export const LANG_STORAGE_KEY = "aquacontrol_lang";

/** Spanish falls back to English, then to the key itself. */
export function translate(lang: Lang, key: string, params?: Record<string, string | number>): string {
  const text = DICTIONARIES[lang][key] ?? en[key] ?? key;
  if (!params) return text;
  return text.replace(/\{(\w+)\}/g, (match, name: string) => (name in params ? String(params[name]) : match));
}

export function detectLang(stored: string | null, browser: string | undefined): Lang {
  if (stored === "en" || stored === "es") return stored;
  return (browser ?? "").toLowerCase().startsWith("es") ? "es" : "en";
}
