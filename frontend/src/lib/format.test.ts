import { describe, expect, it } from "vitest";
import { formatDateTime, formatDateTimeParts, formatNumber, formatRange, localInputToIso, toLocalInputValue } from "./format";

describe("formatNumber", () => {
  it("follows the app language and keeps at least the parameter decimals", () => {
    expect(formatNumber(7.4, 1, "en")).toBe("7.4");
    // Spanish is formatted as es-MX: Mexico writes decimals with a point (7.4) like en-US, unlike Spain (7,4).
    // Typing "7,4" is still accepted by parseDecimal and by the server.
    expect(formatNumber(7.4, 1, "es")).toBe("7.4");
    expect(formatNumber(1500.5, 1, "es")).toBe("1,500.5");
    expect(formatNumber(7, 1, "en")).toBe("7.0");
    expect(formatNumber(1500, 0, "en")).toBe("1,500");
  });
  it("never hides extra precision that affected the status", () => {
    expect(formatNumber(7.85, 1, "en")).toBe("7.85");
    expect(formatNumber(0.123456, 2, "en")).toBe("0.1235");
  });
});

describe("formatRange", () => {
  it("covers two-sided, one-sided and empty rules", () => {
    expect(formatRange(7.2, 7.8, 1, "en")).toBe("7.2 – 7.8");
    expect(formatRange(1, 3, 2, "es", "mg/L")).toBe("1.00 – 3.00 mg/L");
    expect(formatRange(null, 0.2, 2, "en", "mg/L")).toBe("≤ 0.20 mg/L");
    expect(formatRange(650, null, 0, "en")).toBe("≥ 650");
    expect(formatRange(null, null, 1, "en", "mg/L")).toBe("—");
  });
});

describe("dates", () => {
  it("formats an instant in the requested zone and language", () => {
    const iso = "2025-06-01T14:30:00+00:00";
    expect(formatDateTime(iso, "en", "America/Mexico_City")).toBe("Jun 1, 2025, 8:30 AM");
    expect(formatDateTime(iso, "es", "America/Mexico_City")).toMatch(/^1 jun 2025, 8:30/);
  });
  it("splits date and time for two-line cells", () => {
    expect(formatDateTimeParts("2025-06-01T14:30:00Z", "en", "America/Mexico_City")).toEqual({ date: "Jun 1, 2025", time: "8:30 AM" });
    expect(formatDateTimeParts("2025-06-01T14:30:00Z", "es", "UTC").date).toMatch(/^1 jun 2025$/);
  });
  it("round-trips the datetime-local input through the API format", () => {
    const now = new Date(2025, 5, 1, 8, 30, 45);
    const local = toLocalInputValue(now);
    expect(local).toBe("2025-06-01T08:30");
    expect(localInputToIso(local)).toBe(new Date(2025, 5, 1, 8, 30).toISOString());
    expect(localInputToIso("")).toBeUndefined();
    expect(localInputToIso("not a date")).toBeUndefined();
  });
});
