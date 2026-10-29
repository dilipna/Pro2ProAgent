import test from "node:test";
import assert from "node:assert/strict";
import {
  backendConnected,
  browserModeResponse,
} from "../src/lib/backend-mode.ts";
test("only an explicit connected mode enables upstream access", () => {
  const previous = process.env.PROTOPRO_BACKEND_MODE;
  try {
    for (const value of [
      undefined,
      "",
      "browser",
      "CONNECTED",
      "true",
      " connected",
    ]) {
      if (value === undefined) delete process.env.PROTOPRO_BACKEND_MODE;
      else process.env.PROTOPRO_BACKEND_MODE = value;
      assert.equal(backendConnected(), false);
    }
    process.env.PROTOPRO_BACKEND_MODE = "connected";
    assert.equal(backendConnected(), true);
  } finally {
    if (previous === undefined) delete process.env.PROTOPRO_BACKEND_MODE;
    else process.env.PROTOPRO_BACKEND_MODE = previous;
  }
});
test("browser mode returns actionable uncached JSON without implying a queued action", async () => {
  const response = browserModeResponse();
  assert.equal(response.status, 503);
  assert.equal(response.headers.get("cache-control"), "no-store");
  const body = await response.json();
  assert.equal(body.mode, "browser");
  assert.match(body.detail, /local setup/);
  assert.equal(body.run_id, undefined);
});
