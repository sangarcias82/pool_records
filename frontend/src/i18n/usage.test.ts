/** Every translation key the code uses exists in both dictionaries, and every defined key is used somewhere. */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { en } from "./en";
import { es } from "./es";

const SRC = fileURLToPath(new URL("..", import.meta.url));

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.ts$/.test(name) && !path.includes(join("src", "i18n")) ? [path] : [];
  });
}

const code = sources(SRC).map((path) => readFileSync(path, "utf-8")).join("\n");
const literal = new Set<string>([
  ...[...code.matchAll(/\bt\(\s*"([^"]+)"/g)].map((m) => m[1]),
  ...[...code.matchAll(/backLabel="([^"]+)"/g)].map((m) => m[1]),
  ...[...code.matchAll(/\[\s*"[^"]*",\s*"((?:nav|field)\.[^"]+)"\s*\]/g)].map((m) => m[1]), // NAV, FIELDS tables
]);
// Keys built at runtime: `${prefix}.${value}`; the backend values are checked in tests/test_i18n.py.
const DYNAMIC = ["status.", "direction.", "class.", "env.", "param.", "home.", "err."];

describe("i18n keys used by the code", () => {
  it("finds the usages (sanity)", () => {
    expect(literal.size).toBeGreaterThan(60);
  });
  it("exist in English and Spanish", () => {
    const missing = [...literal].filter((key) => !(key in en) || !(key in es));
    expect(missing).toEqual([]);
  });
  it("leave no dead keys", () => {
    const dead = Object.keys(en).filter((key) => !literal.has(key) && !DYNAMIC.some((prefix) => key.startsWith(prefix)));
    expect(dead).toEqual([]);
  });
  it("keep the same {placeholders} in both languages", () => {
    const names = (text: string) => [...text.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
    const differ = Object.keys(en).filter((key) => names(en[key]).join() !== names(es[key]).join());
    expect(differ).toEqual([]);
  });
  it("has no hard-coded aria-label or title text", () => {
    expect([...code.matchAll(/(aria-label|title)="([^"]+)"/g)].map((m) => m[0])).toEqual([]);
  });
});
