import { describe, expect, it } from "vitest";

import { cn } from "./utils";

describe("cn", () => {
  it("merges conflicting Tailwind classes and keeps unrelated classes", () => {
    expect(cn("px-2 py-1", "px-4", "text-sm")).toBe("py-1 px-4 text-sm");
  });

  it("joins conditional class values", () => {
    expect(cn("button", false && "disabled", ["active", null])).toBe("button active");
  });
});
