import { describe, expect, it } from "vitest";

import en from "./en.json";
import pl from "./pl.json";

type JsonObject = Record<string, unknown>;

function flattenKeys(obj: JsonObject, prefix = ""): string[] {
  return Object.entries(obj).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    if (value !== null && typeof value === "object" && !Array.isArray(value)) {
      return flattenKeys(value as JsonObject, path);
    }
    return [path];
  });
}

describe("i18n locale parity", () => {
  it("pl and en expose exactly the same translation keys", () => {
    const plKeys = flattenKeys(pl).sort();
    const enKeys = flattenKeys(en).sort();

    expect(plKeys).toEqual(enKeys);
  });
});
