/** Labels for catalog data that the SPA translates by stable code. */

type Translate = (key: string, params?: Record<string, string | number>) => string;

/** ``param.<CODE>`` in the app language, or the catalog ``name`` when the dictionary has no entry for the code. */
export function paramLabel(t: Translate, code: string, fallback: string): string {
  const key = `param.${code}`;
  const label = t(key);
  return label === key ? fallback : label;
}
