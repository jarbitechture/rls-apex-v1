import { describe, it, expect, vi, beforeEach } from "vitest";

let policyLintLlm;
let RULES;

beforeEach(async () => {
  // Reset module cache and re-import for isolated state per test
  vi.resetModules();
  global.fetch = vi.fn();
  const mod = await import("../../static/core/automation/auto-correct.js");
  RULES = mod.RULES;
  policyLintLlm = RULES.find((r) => r.id === "policy-lint-llm");
});

describe("policy-lint-llm rule", () => {
  it("is registered alongside the existing rules", () => {
    expect(policyLintLlm).toBeTruthy();
    expect(policyLintLlm.id).toBe("policy-lint-llm");
    // 3 prior + 1 new
    expect(RULES.length).toBeGreaterThanOrEqual(4);
  });

  it("returns suggestions when /api/lint/policy returns them", async () => {
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        suggestions: [{
          ruleId: "policy-lint-llm",
          field: "factualBackground",
          citation: "LDC §6.4(a)(2)",
          explanation: "Mentions erecting structure without referencing permit.",
          severity: "info",
        }],
      }),
    });
    const payload = {
      factualBackground: "We plan to erect a new structure.",
      ui: { blurredFields: ["factualBackground"], dismissedSuggestions: [] },
    };
    const out = await policyLintLlm.apply(payload, {});
    expect(out).toHaveLength(1);
    expect(out[0].field).toBe("factualBackground");
  });

  it("gates on blurredFields — returns null when target field not blurred", async () => {
    const payload = {
      factualBackground: "We plan to erect a new structure.",
      ui: { blurredFields: [], dismissedSuggestions: [] },
    };
    const out = await policyLintLlm.apply(payload, {});
    expect(out).toBeNull();
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it("returns null when /api/lint/policy returns non-ok", async () => {
    global.fetch.mockResolvedValueOnce({ ok: false, status: 503 });
    const payload = {
      factualBackground: "x",
      ui: { blurredFields: ["factualBackground"], dismissedSuggestions: [] },
    };
    const out = await policyLintLlm.apply(payload, {});
    expect(out).toBeNull();
  });

  it("respects dismissed suggestion dedup — suppresses chip if value-hash already dismissed", async () => {
    // Suggestion hash = `policy-lint-llm:factualBackground:<value-hash>`
    const valueHash = "deadbeef";
    global.fetch.mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        suggestions: [{
          ruleId: "policy-lint-llm",
          field: "factualBackground",
          citation: "LDC §6.4(a)(2)",
          explanation: "x",
          severity: "info",
        }],
      }),
    });
    const payload = {
      factualBackground: "We plan to erect a new structure.",
      ui: {
        blurredFields: ["factualBackground"],
        dismissedSuggestions: [`policy-lint-llm:factualBackground:${valueHash}`],
      },
    };
    // Post-fetch filtering: fetch is called but matching suggestions are suppressed.
    const out = await policyLintLlm.apply(payload, { computeHash: () => valueHash });
    expect(out).toEqual([]);
  });
});
