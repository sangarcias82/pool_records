import { afterEach, describe, expect, it, vi } from "vitest";
import { translate } from "../i18n/translate";
import { ApiError, errorMessage, request } from "./client";

const es = (key: string, params?: Record<string, string | number>) => translate("es", key, params);

afterEach(() => vi.unstubAllGlobals());

describe("request errors", () => {
  it("unreachable server -> local err.network, translated in the UI language", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    const error = await request("GET", "/api/x").catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(errorMessage(error, es)).toBe(es("err.network"));
    expect(errorMessage(error, es)).not.toContain("Failed to fetch");
  });

  it("error without a JSON body (proxy page) -> local err.http with the status", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("<html>Bad gateway</html>", { status: 502 })));
    const error = await request("GET", "/api/x").catch((e: unknown) => e);
    expect(errorMessage(error, es)).toBe("El servidor respondió con un error (HTTP 502).");
  });

  it("server errors keep the server's (already translated) message and key", async () => {
    const body = JSON.stringify({ detail: "Elige una alberca.", key: "err.pool" });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(body, { status: 422 })));
    const error = (await request("POST", "/api/measurements", {}).catch((e: unknown) => e)) as ApiError;
    expect([error.status, error.key, errorMessage(error, es)]).toEqual([422, "err.pool", "Elige una alberca."]);
  });

  it("plain errors and non-errors still become text", () => {
    expect(errorMessage(new Error("boom"))).toBe("boom");
    expect(errorMessage("text")).toBe("text");
    expect(errorMessage(new ApiError(0, "Network error", "err.network", true))).toBe("Network error"); // no t given
  });
});
