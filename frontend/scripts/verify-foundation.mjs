// Frontend-only Chromium checks. No E2E launcher, backend, Redis, Docker or live API.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { createServer } from "node:net";
import { chromium, expect } from "@playwright/test";

const output = await mkdtemp(join(tmpdir(), "reconcile-foundation-"));
const probe = createServer();
await new Promise((done, fail) => { probe.once("error", fail); probe.listen(0, "127.0.0.1", done); });
const port = probe.address().port;
await new Promise(done => probe.close(done));
const origin = `http://127.0.0.1:${port}`;
const server = spawn(process.execPath, ["node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", String(port), "--strictPort"], {
  cwd: resolve(import.meta.dirname, ".."), stdio: ["ignore", "pipe", "pipe"],
});
let serverLog = "";
server.stdout.on("data", data => { serverLog += data; });
server.stderr.on("data", data => { serverLog += data; });
let browser;
const previewCsv = ["tuple_id,src,flight,sched_dep_time,act_dep_time,sched_arr_time,act_arr_time",
  ...Array.from({ length: 7 }, (_, i) => `observation-${i},source-${i % 2},ZZ-1-AAA-BBB,9:22 a.m.,,Contact Airline,14:40`)].join("\r\n");
const investigationEvidence = JSON.parse(await readFile(new URL("./fixtures/investigation.json", import.meta.url), "utf8"));
let fixtureAIState = "not_requested";
let fixtureAIReads = 0;
let fixtureAIPosts = 0;
let fixtureDecision = null;
const fixtureEvents = [];
const fixtureExports = [];
const artifactBodies = {reviewed: "job_id,export_id,flight,sched_dep_time,sched_dep_time_status\n7,synthetic,ZZ-1-AAA-BBB,14:40,overridden\n", exceptions: "job_id,flight,field,review_status\n7,ZZ-1-AAA-BBB,act_dep_time,unreviewed\n", provenance: JSON.stringify({synthetic_fixture: true, resolution_policy: "Only human-approved values are exported"})};
function snapshotRecord() {return {job_id: 7, snapshot_digest: "sha256:" + "b".repeat(64), field_count: 4, ungroupable_observation_count: 0};}
function investigationRecord() {
  const e = investigationEvidence;
  return {id: "synthetic-investigation", request_id: "synthetic-request", job_id: 7, discrepancy_id: e.discrepancy_id,
    evidence_digest: e.evidence_digest, status: fixtureAIState, stored_status: fixtureAIState, current: fixtureAIState !== "stale", authoritative: false,
    recommendation: fixtureAIState === "proposed" ? {recommendation: "propose", candidate_id: e.candidates[0].candidate_id, supporting_claim_ids: ["claim-1"], contradicting_claim_ids: ["claim-2"], explanation: "This synthetic proposal cites observed claims; it does not establish truth.", uncertainty: "Sources may repeat the same upstream error."} : fixtureAIState === "abstained" ? {recommendation: "abstain", candidate_id: null, supporting_claim_ids: [], contradicting_claim_ids: [], explanation: "The supplied claims do not establish which candidate to trust.", uncertainty: "Reporting sources are not proven independent."} : null,
    claim_references: [{claim_id: "claim-1", observation_id: "synthetic-0", source_id: "source-0"}, {claim_id: "claim-2", observation_id: "synthetic-2", source_id: "source-2"}],
    provider: "synthetic-provider", model: "synthetic-model", resolved_model: null, usage: {total_tokens: 80}, error_code: fixtureAIState === "unavailable" ? "unconfigured" : null,
    policy_version: "flight_investigation_v1", prompt_version: "flight_investigation_prompt_v1", schema_version: "flight_recommendation_v1", created_at: "2026-01-01", completed_at: null};
}
function reviewRecord() {
  return {job_id: 7, discrepancy_id: investigationEvidence.discrepancy_id, evidence_digest: investigationEvidence.evidence_digest,
    state: fixtureDecision ? {accept: "accepted", override: "overridden", reject: "rejected", unresolved: "unresolved"}[fixtureDecision.action] : "unreviewed", stale: false, revision: fixtureDecision?.revision ?? 0,
    decision: fixtureDecision, resolution: fixtureDecision?.resolution ?? null, reviewer_identity_verified: false};
}

const failures = [];
const checked = [];
const jobs = ["original.csv", "other.csv"].map((name, index) => ({ id: index + 1, filename_original: name,
  status: "completed", created_at: "2026-04-01T12:00:00", total_rows: 1, valid_rows: 0, invalid_rows: 1,
  file_size: 100, duration_ms: 1, error_breakdown: { Email: 1 }, analysis: null, ai_report: null, records_available: true }));
async function isolate(context, synthetic) {
  let statusChecks = 0;
  await context.route("**/*", async route => {
    const url = new URL(route.request().url());
    if (url.origin === origin) return route.continue();
    if (url.pathname.startsWith("/api/v1/")) {
      if (url.pathname.startsWith("/api/v1/flights/")) {
        const historyJob = {id: 7, job_kind: "raha_flights_v1", contract_version: 1, status: "completed", filename_original: "synthetic-flights.csv", created_at: "2026-01-01T12:00:00", processed_at: "2026-01-01T12:00:01", observation_count: 26, file_size: Buffer.byteLength(previewCsv), error_message: null};
        if (url.pathname === "/api/v1/flights/jobs") return route.fulfill({json: {jobs: [historyJob], total: 1, page: Number(url.searchParams.get("page")), page_size: 15}});
        if (url.pathname.includes("/exports")) {
          if (url.pathname.endsWith("/snapshot")) return route.fulfill({json: snapshotRecord()});
          if (url.pathname.includes("/download/")) {
            const key = url.pathname.split("/").at(-1); assert(key in artifactBodies);
            return route.fulfill({body: artifactBodies[key], contentType: key === "provenance" ? "application/json" : "text/csv"});
          }
          if (route.request().method() === "POST") {
            const body = route.request().postDataJSON(); assert.equal(body.expected_snapshot_digest, snapshotRecord().snapshot_digest);
            const item = {id: "c".repeat(32), request_id: body.request_id, job_id: 7, snapshot_digest: body.expected_snapshot_digest, input_sha256: "a".repeat(64), policy_version: "flight_reviewed_export_v1", created_at: "2026-01-01T12:00:02", artifacts: Object.fromEntries(Object.entries(artifactBodies).map(([key, value]) => [key, {sha256: createHash("sha256").update(value).digest("hex"), bytes: Buffer.byteLength(value)}]))};
            fixtureExports.unshift(item); return route.fulfill({json: item});
          }
          return route.fulfill({json: {exports: fixtureExports, total: fixtureExports.length, page: Number(url.searchParams.get("page")), page_size: 5}});
        }

        if (url.pathname.includes("/discrepancies")) {
          const e = investigationEvidence;
          if (url.pathname.endsWith("/review/history")) return route.fulfill({json: {events: fixtureEvents, total: fixtureEvents.length, page: 1, page_size: 5}});
          if (url.pathname.endsWith("/review")) {
            if (route.request().method() === "POST") {
              const body = route.request().postDataJSON();
              assert.equal(body.expected_evidence_digest, e.evidence_digest);
              assert.equal(body.expected_revision, fixtureDecision?.revision ?? 0);
              const c = e.candidates.find(c => c.candidate_id === body.candidate_id) ?? e.candidates[0];
              fixtureDecision = {id: `synthetic-decision-${fixtureEvents.length + 1}`, ...body, job_id: 7, discrepancy_id: e.discrepancy_id, evidence_digest: e.evidence_digest, flight: e.flight, field: e.field,
                revision: fixtureEvents.length + 1, candidate_id: body.manual_value ? null : body.candidate_id ?? null, investigation_id: body.investigation_id ?? null, manual_value: body.manual_value ?? null, created_at: "2026-01-01",
                resolution: body.action === "accept" || body.action === "override" ? {origin: body.manual_value ? "human_assertion" : "observed_candidate", canonical_clock: body.manual_value ? "14:40" : c.canonical_clock, precision: "minute", qualifiers: [], supporting_observation_ids: body.manual_value ? [] : c.supporting_observation_ids, supporting_source_ids: body.manual_value ? [] : c.supporting_source_ids} : null};
              fixtureEvents.push(fixtureDecision); return route.fulfill({json: fixtureDecision});
            }
            return route.fulfill({json: reviewRecord()});
          }
          if (url.pathname.endsWith("/investigations")) {
            if (route.request().method() === "POST") { const body = route.request().postDataJSON(); assert.equal(body.expected_evidence_digest, e.evidence_digest); fixtureAIPosts++; fixtureAIState = "running"; fixtureAIReads = 0; return route.fulfill({status: 202, json: investigationRecord()}); }
            return route.fulfill({json: {status: fixtureAIState, investigation: fixtureAIState === "not_requested" ? null : investigationRecord()}});
          }
          if (url.pathname.includes("/investigations/")) {if (++fixtureAIReads >= 2) fixtureAIState = "proposed"; return route.fulfill({json: investigationRecord()});}
          if (url.pathname.endsWith("/discrepancies")) return route.fulfill({json: {job_id: 7, discrepancies: [{...e, candidate_count: e.candidates.length}], total: url.searchParams.get("page_size") === "1" && url.searchParams.get("kind") === "all" ? 4 : 1, page: Number(url.searchParams.get("page")), page_size: Number(url.searchParams.get("page_size")), ungroupable_observation_count: 0, raw_observations_url: "/api/v1/flights/jobs/7/observations"}});
          return route.fulfill({json: e});
        }

        const record = { tuple_id: "observation-0", src: "source-0", flight: "ZZ-1-AAA-BBB", row_number: 2, sched_dep_time: "9:22 a.m.", act_dep_time: "", sched_arr_time: "Contact Airline", act_arr_time: "14:40", issues: [] };
        if (url.pathname.endsWith("/uploads")) { statusChecks = 0; return route.fulfill({ status: 202, json: { job_id: 7, status: "queued", status_url: "/api/v1/flights/jobs/7", message: "Accepted" } }); }
        if (url.pathname.endsWith("/observations")) return route.fulfill({ json: { job_id: 7, total: 26, page: Number(url.searchParams.get("page")), page_size: 25, observations: [{ ...record, tuple_id: `observation-page-${url.searchParams.get("page")}` }] } });
        const complete = ++statusChecks > 2 || new URL(route.request().headers()["referer"] ?? origin).pathname === "/investigate" || new URL(route.request().headers()["referer"] ?? origin).pathname === "/history";
        return route.fulfill({ json: { id: 7, job_kind: "raha_flights_v1", contract_version: 1, status: complete ? "completed" : "queued", filename_original: "synthetic-flights.csv", filename_input_saved: "owned.csv", input_sha256: "a".repeat(64), file_size: Buffer.byteLength(previewCsv), created_at: "2026-01-01", processed_at: null, attempts: 1, duration_ms: 15, observation_count: complete ? 26 : 0, observations_available: complete, issues: [], error_message: null } });
      }
      if (!synthetic) return route.fulfill({ status: 503, json: { detail: "Backend is not connected in this isolated frontend preview." } });
      let data;
      if (url.pathname.endsWith("/templates")) data = [];
      else if (url.pathname.endsWith("/records")) data = { records: [{ row_number: 3, status: "rejected", values: { email: "bad" }, normalized: {}, issues: [{ fields: ["email"], category: "Email", message: "email must be valid" }] }], total: 1, page: 1, page_size: 25, fields: ["email"] };
      else if (url.pathname.endsWith("/corrections/validate")) data = { valid: true, rows: [{ row_number: 3, issues: [] }], message: "Field checks only" };
      else if (url.pathname === "/api/v1/jobs") data = { jobs, total: 2, page: 1, page_size: 10 };
      else data = jobs.find(job => url.pathname === `/api/v1/jobs/${job.id}`);
      return route.fulfill({ json: data ?? {} });
    }
    return route.abort();
  });
}
try {
  for (let attempt = 0; attempt < 80; attempt++) {
    try { if ((await fetch(origin)).ok) break; } catch {}
    if (server.exitCode !== null) throw new Error("Frontend preview exited");
    await new Promise(done => setTimeout(done, 100));
  }
  browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH } : {}) });
  const context = await browser.newContext();
  await isolate(context, false);
  const page = await context.newPage();
  page.on("pageerror", error => failures.push(error.message));
  for (const width of [1440, 1024, 768, 720, 390, 320]) {
    await page.setViewportSize({ width, height: 900 });
    for (const path of ["/", "/datasets", "/investigate", "/history", "/legacy/transactions", "/not-a-page"]) {
      await page.goto(origin + path);
      await expect(page.locator("main h1")).toBeVisible();
      if (path === "/") await page.evaluate(async () => {
        await Promise.all([...document.querySelectorAll(".hero-enter")].flatMap(element => element.getAnimations()).map(animation => animation.finished.catch(() => {})));
      });
      assert.equal(await page.evaluate(() => getComputedStyle(document.body).backgroundColor), "rgb(20, 40, 35)");
      assert.equal(await page.locator("header").first().evaluate(element => getComputedStyle(element).backgroundColor), "rgb(20, 40, 35)");
      if (path === "/datasets") {
        await page.getByLabel("Flights observation CSV").setInputFiles({ name: "synthetic-flights.csv", mimeType: "text/csv", buffer: Buffer.from(previewCsv) });
        await expect(page.getByRole("region", { name: "Local CSV preview" })).toBeVisible();
        assert.equal(await page.locator(".working-surface").first().evaluate(element => getComputedStyle(element).backgroundColor), "rgb(227, 234, 225)");
      }
      const fits = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
      if (!fits) {
        await page.screenshot({ path: join(output, "overflow.png"), fullPage: true, animations: "disabled" });
        await writeFile(join(output, "overflow.json"), JSON.stringify(await page.evaluate(() => [...document.querySelectorAll("body *")].filter(element => element.getBoundingClientRect().right > innerWidth + 1).map(element => ({ tag: element.tagName, class: element.className, right: element.getBoundingClientRect().right }))), null, 2));
      }
      assert(fits, `${width}: ${path} document overflow; artifacts: ${output}`);
      const active = page.getByRole("navigation", { name: "Primary", exact: true }).locator('[aria-current="page"]');
      if (width >= 768 && !["/not-a-page", "/legacy/transactions"].includes(path)) await expect(active).toHaveCount(1);
      assert.equal(await page.locator("header").first().evaluate(e => getComputedStyle(e).position), "sticky");
      await expect(page.getByText("Local workspace", {exact: true})).toHaveCount(0);
      await expect(page.locator('a[href^="/legacy/transactions"]')).toHaveCount(0);
      await expect(page.locator(".nav-pill")).toHaveCount(0);
      assert(await page.locator(".brand-symbol").evaluate(img => img.complete && img.naturalWidth > 0));
      if (width >= 768 && !["/not-a-page", "/legacy/transactions"].includes(path)) {
        assert.equal(await active.evaluate(e => getComputedStyle(e).backgroundColor), "rgba(0, 0, 0, 0)");
        assert.equal(await active.evaluate(e => getComputedStyle(e).color), "rgb(216, 250, 119)");
      }
      if (width < 768) {
        const trigger = page.getByRole("button", { name: "Open navigation" });
        await trigger.click();
        const menu = page.getByRole("dialog", { name: "Navigation" });
        await expect(menu).toBeVisible();
        if (width === 390 && path === "/") await page.screenshot({path: join(output, "390-navigation.png"), animations: "disabled"});
        await expect(menu.getByRole("button", { name: "Close navigation" })).toBeFocused();
        await page.keyboard.press("Shift+Tab");
        await expect(menu.getByRole("link", { name: "History" })).toBeFocused();
        await page.keyboard.press("Tab");
        await expect(menu.getByRole("button", { name: "Close navigation" })).toBeFocused();
        await page.keyboard.press("Escape");
        await expect(trigger).toBeFocused();
      }
      if ([1440, 1024, 768, 390, 320].includes(width) && path !== "/not-a-page") {
        await page.getByRole("main").focus();
        await page.evaluate(() => window.scrollTo(0, 0));
        await page.screenshot({ path: join(output, `${width}-${path === "/" ? "home" : path.slice(1).replaceAll("/", "-")}.png`), fullPage: true, animations: "disabled" });
      }
      checked.push({ width, height: 900, path, overflow: false });
    }
  }
  await page.setViewportSize({ width: 390, height: 900 });
  await page.goto(origin + "/investigate");
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.getByRole("dialog").getByRole("link", { name: "History" }).click();
  await expect(page.getByRole("heading", { name: "History", exact: true })).toBeVisible();
  await expect(page.getByRole("main")).toBeFocused();
  await page.getByRole("button", { name: "Open navigation" }).click();
  await page.setViewportSize({ width: 1024, height: 900 });
  await expect(page.getByRole("dialog")).toHaveCount(0);
  await expect(page.getByRole("navigation", { name: "Primary", exact: true }).getByRole("link", { name: "History" })).toBeFocused();
  await page.emulateMedia({ reducedMotion: "reduce" });
  await page.goto(origin + "/");
  assert.equal(await page.getByRole("link", { name: /Open workspace/ }).evaluate(element => getComputedStyle(element).transitionDuration), "0s");
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.getByRole("main")).toBeFocused();
  assert.equal(new URL(page.url()).hash, "");
  await page.getByRole("link", {name: /Open workspace/}).click();
  await page.getByLabel("Flights observation CSV").setInputFiles({ name: "synthetic-flights.csv", mimeType: "text/csv", buffer: Buffer.from(previewCsv) });
  await page.getByRole("button", { name: "Import observations", exact: true }).click();
  await expect(page).toHaveURL(/\/datasets\?dataset=7$/);
  await expect(page.getByText("queued", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Raw observations" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Persisted observations table" }).getByText("observation-page-1")).toBeVisible();
  await page.getByRole("button", { name: "Next observations" }).click();
  await expect(page.getByRole("region", { name: "Persisted observations table" }).getByText("observation-page-2")).toBeVisible();
  await expect(page.getByRole("button", { name: "Next observations" })).toBeDisabled();
  // Explicitly synthetic Investigate workflow: intercepted APIs, never a live provider.
  await page.setViewportSize({width: 1440, height: 900});
  await page.getByRole("link", {name: /Investigate evidence/}).click();
  await expect(page.getByRole("heading", {name: "Flights dataset", exact: true})).toBeVisible();
  await expect(page.getByText("4 cases across four time fields. Flags describe findings, not review progress.")).toBeVisible();
  await page.getByRole("link", {name: "Review cases", exact: true}).click();
  await expect(page.getByRole("heading", {name: "Cases", exact: true})).toBeVisible();
  await expect(page.getByRole("table", {name: "Cases", exact: true}).getByRole("link")).toHaveCount(1);
  await page.screenshot({path: join(output, "1440-investigate-queue.png"), fullPage: true, animations: "disabled"});
  assert.equal(fixtureAIPosts, 0);
  await page.getByRole("table", {name: "Cases", exact: true}).getByRole("link").click();
  await expect(page).toHaveURL(new RegExp(`discrepancy=${investigationEvidence.discrepancy_id}`));
  await page.getByText("Record a review", {exact: true}).click();
  await expect(page.getByRole("button", {name: "Save review"})).toBeEnabled();
  await page.getByRole("button", {name: "Close details"}).click();
  await page.getByRole("button", {name: /View source records/}).click();
  await expect(page.getByRole("region", {name: "Source evidence table"})).toBeVisible();
  await expect(page.getByRole("region", {name: "Source evidence table"}).locator("img")).toHaveCount(0);
  // Real wheel and pointer input inside the modal, with synthetic evidence only.
  await page.setViewportSize({width: 1440, height: 500});
  await page.waitForTimeout(500);
  const panelBody = page.locator(".case-window-body");
  const pageBeforeWheel = await page.evaluate(() => scrollY);
  const tableBox = await page.locator(".source-evidence tbody tr").first().boundingBox();
  await page.mouse.move(tableBox.x + tableBox.width / 2, tableBox.y + 25);
  await page.mouse.wheel(0, 450);
  await expect.poll(() => panelBody.evaluate(e => e.scrollTop)).toBeGreaterThan(0);
  assert.equal(await page.evaluate(() => scrollY), pageBeforeWheel, "Modal wheel keeps background stationary");
  const resizeHandle = page.getByRole("separator", {name: "Resize source panel"});
  const edge = await resizeHandle.boundingBox();
  await page.mouse.move(edge.x + 6, 250); await page.mouse.down();
  await page.mouse.move(edge.x - 150, 250, {steps: 8}); await page.mouse.up();
  await expect(resizeHandle).toHaveAttribute("aria-valuenow", "1216");
  await resizeHandle.focus(); await page.keyboard.press("Home");
  await expect(resizeHandle).toHaveAttribute("aria-valuenow", "680");
  await page.keyboard.press("End"); await expect(resizeHandle).toHaveAttribute("aria-valuenow", "1280");
  await page.setViewportSize({width: 1440, height: 900});

  await page.getByRole("button", {name: "Close details"}).click();
  assert.equal(fixtureAIPosts, 0);
  await page.screenshot({path: join(output, "1440-investigate-evidence.png"), fullPage: true, animations: "disabled"});
  await page.getByRole("button", {name: "Investigate with AI"}).click();
  await expect(page.getByRole("button", {name: "Investigate with AI"})).toBeDisabled();
  await page.getByRole("button", {name: "View AI assessment", exact: true}).click();
  await expect(page.getByText(/This synthetic proposal cites/)).toBeVisible({timeout: 10000});
  assert.equal(fixtureAIPosts, 1);
  await expect(page.getByRole("heading", {name: "Cited observations and provider"})).toBeVisible();
  await page.getByRole("button", {name: "Close details"}).click();
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height: 900});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}: populated investigation overflow`);
    assert.equal(await page.locator(".focused-case").evaluate(e => getComputedStyle(e).backgroundColor), "rgb(227, 234, 225)");
    await page.evaluate(() => window.scrollTo(0, 600));
    assert(Math.abs(await page.locator("header").first().evaluate(e => e.getBoundingClientRect().top)) < 1, "Header stays visible while scrolling");
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: join(output, `${width}-investigate-proposal.png`), fullPage: true, animations: "disabled"});
    checked.push({width, height: 900, path: "/investigate?dataset=7&discrepancy=synthetic", overflow: false});
    if (width === 320) {await page.getByRole("heading", {name: "Your review"}).scrollIntoViewIfNeeded(); await page.screenshot({path: join(output, "320-review-controls.png")});}
  }
  await page.getByRole("button", {name: "Record a review", exact: true}).click();
  await page.getByLabel("Review action").selectOption("override");
  await page.getByLabel("Replacement origin").selectOption("manual");
  await page.getByLabel("Manual clock", {exact: true}).fill("2:40 p.m.");
  await page.getByLabel(/Reviewer name or label/).fill("Synthetic local reviewer");
  await page.getByLabel(/Rationale/).fill("Synthetic human assertion for browser verification.");
  await page.getByRole("button", {name: "Save review"}).click();
  await expect(page.getByText(/Review saved/)).toBeVisible();
  await page.getByRole("button", {name: "Close details"}).click();
  await expect(page.getByText(/Reviewed value: 14:40/)).toBeVisible();
  await page.getByRole("button", {name: "View review details", exact: true}).click();
  await expect(page.getByText(/Server revision 1/)).toBeVisible();
  await page.getByRole("button", {name: "Close details"}).click();
  assert.equal(fixtureEvents.length, 1);
  await page.setViewportSize({width: 1440, height: 900});
  await page.screenshot({path: join(output, "1440-investigate-reviewed.png"), fullPage: true, animations: "disabled"});
  fixtureAIState = "abstained";
  await page.reload();
  await page.getByRole("button", {name: "View AI assessment", exact: true}).click();
  await expect(page.getByText(/The model declined/)).toBeVisible();
  await page.screenshot({path: join(output, "1440-investigate-abstention.png"), fullPage: true, animations: "disabled"});
  fixtureAIState = "unavailable";
  await page.setViewportSize({width: 390, height: 900});
  await page.reload();
  await page.getByRole("button", {name: "View AI assessment", exact: true}).click();
  await expect(page.getByText("Reason: unconfigured")).toBeVisible();
  await page.screenshot({path: join(output, "390-investigate-unavailable.png"), fullPage: true, animations: "disabled"});
  assert.equal(fixtureAIPosts, 1, "Selecting/reloading/refreshing must not request AI automatically");
  await page.route("**/api/v1/flights/jobs/7/discrepancies/*", async route => {
    if (route.request().url().endsWith(investigationEvidence.discrepancy_id)) {await new Promise(done => setTimeout(done, 700)); return route.fallback();}
    return route.fallback();
  });
  await page.reload();
  await expect(page.getByText("Refreshing authoritative evidence and review…")).toBeVisible();
  await page.screenshot({path: join(output, "390-investigate-loading.png"), fullPage: true, animations: "disabled"});
  await page.getByText("Record a review", {exact: true}).click();
  await expect(page.getByRole("button", {name: "Save review"})).toBeEnabled();
  await page.getByRole("button", {name: "Close details"}).click();
  await page.unroute("**/api/v1/flights/jobs/7/discrepancies/*");

  await page.setViewportSize({width: 1440, height: 900});
  await page.getByRole("navigation", {name: "Primary", exact: true}).getByRole("link", {name: "History"}).click();
  await expect(page).toHaveURL(url => url.pathname === "/history" && url.searchParams.get("dataset") === "7" && url.searchParams.get("discrepancy") === investigationEvidence.discrepancy_id);
  await expect(page.getByText(/Current snapshot: 4 fields/)).toBeVisible();
  await expect(page.getByText("Current event", {exact: true})).toBeVisible();
  assert.equal(fixtureExports.length, 0);
  await expect(page.getByRole("button", {name: "Create frozen export"})).toBeDisabled();
  await page.getByRole("checkbox", {name: /I understand/}).check();
  await page.getByRole("button", {name: "Create frozen export"}).click();
  await expect(page.getByText("1 frozen exports · Page 1")).toBeVisible();
  assert.equal(fixtureExports.length, 1);
  for (const label of ["Reviewed CSV", "Exceptions CSV", "Provenance JSON"]) {
    const downloaded = page.waitForEvent("download");
    await page.getByRole("button", {name: label, exact: true}).click();
    const result = await downloaded;
    await result.saveAs(join(output, result.suggestedFilename()));
    assert.equal(fixtureExports.length, 1, "Downloading must not generate another snapshot");
  }
  await page.getByText("Inspect export 1 metadata").click();
  for (const width of [1440, 1024, 768, 390, 320]) {
    await page.setViewportSize({width, height: 900});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `${width}: populated History overflow`);
    await page.getByRole("button", {name: "Create frozen export"}).screenshot({path: join(output, `${width}-export-control.png`)});
    // Control screenshots may scroll; settle at the document top for full-page review.
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: join(output, `${width}-history-populated.png`), fullPage: true, animations: "disabled"});
    checked.push({width, height: 900, path: "/history?dataset=7", overflow: false});
  }
  await page.reload();
  await expect(page.getByText("1 frozen exports · Page 1")).toBeVisible();
  assert.equal(fixtureAIPosts, 1);

  // Long untrusted identifiers must wrap inside evidence, never widen the document.
  const originalSource = investigationEvidence.claims[0].src;
  const originalSupport = investigationEvidence.candidates[0].supporting_source_ids;
  const longSource = "synthetic-source-" + "very-long-identifier-".repeat(20);
  investigationEvidence.claims[0].src = longSource;
  investigationEvidence.candidates[0].supporting_source_ids = [longSource];
  await page.setViewportSize({width: 320, height: 900});
  await page.goto(origin + `/investigate?dataset=7&discrepancy=${investigationEvidence.discrepancy_id}`);
  await page.getByRole("button", {name: /View source records/}).click();
  await expect(page.getByRole("region", {name: "Source evidence table"}).getByText(longSource, {exact: true})).toBeVisible();
  await page.getByRole("button", {name: "Close details"}).click();
  await page.getByRole("button", {name: /View supporting reports/}).first().click();
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), "Long source identifiers stay contained");
  await page.evaluate(() => window.scrollTo(0, 0));
  await page.screenshot({path: join(output, "320-long-identifiers.png"), fullPage: true, animations: "disabled"});
  investigationEvidence.claims[0].src = originalSource;
  investigationEvidence.candidates[0].supporting_source_ids = originalSupport;

  await context.close();
  const editing = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  await isolate(editing, true);
  const workspace = await editing.newPage();
  workspace.on("pageerror", error => failures.push(error.message));
  await workspace.goto(origin + "/?job=1&keep=yes");
  await expect(workspace).toHaveURL(/\/legacy\/transactions\?job=1&keep=yes$/);
  await expect(workspace.getByRole("heading", { name: "original.csv" })).toBeVisible();
  await workspace.getByRole("navigation", { name: "Primary", exact: true }).getByRole("link", { name: "Investigate" }).click();
  // Legacy URLs remain bookmarkable but are intentionally not advertised.
  await workspace.goBack();
  await workspace.getByRole("button", { name: "#2 · other.csv", exact: true }).click();
  await expect(workspace.getByRole("heading", {name: "other.csv"})).toBeVisible();
  await workspace.getByRole("button", { name: "#1 · original.csv", exact: true }).click();
  await expect(workspace.getByRole("heading", {name: "original.csv"})).toBeVisible();
  await workspace.getByRole("button", { name: "Correct record 3" }).click();
  await workspace.getByLabel("Record 3 email").fill("edited@example.com");
  await workspace.getByRole("button", { name: "Validate corrections" }).click();
  await expect(workspace.getByText("Field validation passed.")).toBeVisible();
  await workspace.getByRole("navigation", { name: "Primary", exact: true }).getByRole("link", { name: "Home", exact: true }).click();
  await workspace.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(workspace.getByLabel("Record 3 email")).toHaveValue("edited@example.com");
  await workspace.goBack();
  await expect(workspace.getByRole("dialog", { name: "Discard unsaved corrections?" })).toBeVisible();
  await workspace.screenshot({path: join(output, "1440-draft-dialog.png"), animations: "disabled"});
  await workspace.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(workspace).toHaveURL(/\/legacy\/transactions\?job=1&keep=yes$/);
  await expect(workspace.getByText("Field validation passed.")).toBeVisible();
  await workspace.goBack();
  await workspace.getByRole("button", { name: "Discard and continue" }).click();
  await expect(workspace).toHaveURL(/job=2/);
  await expect(workspace.getByRole("heading", {name: "other.csv"})).toBeVisible();
  await workspace.goForward();
  await expect(workspace.getByRole("heading", { name: "original.csv" })).toBeVisible();
  for (const width of [320, 390, 768, 1440]) {
    await workspace.setViewportSize({ width, height: 900 });
    assert(await workspace.evaluate(() => document.documentElement.scrollWidth <= innerWidth), `Populated legacy workspace overflow at ${width}`);
  }
  await workspace.setViewportSize({ width: 390, height: 900 });
  await workspace.getByRole("button", { name: "Correct record 3" }).click();
  await workspace.getByLabel("Record 3 email").fill("mobile@example.com");
  await workspace.getByRole("button", { name: "Open navigation" }).click();
  await workspace.getByRole("dialog").getByRole("link", { name: "History" }).click();
  await expect(workspace.getByRole("dialog", { name: "Discard unsaved corrections?" })).toBeVisible();
  await expect(workspace.getByRole("button", { name: "Cancel", exact: true })).toBeFocused();
  await workspace.getByRole("button", { name: "Cancel", exact: true }).click();
  await expect(workspace.getByLabel("Record 3 email")).toHaveValue("mobile@example.com");
  await expect(workspace.getByRole("button", { name: "Open navigation" })).toBeFocused();
  await editing.close();
  assert.deepEqual(failures, []);
  await writeFile(join(output, "checks.json"), JSON.stringify({ checked, browserVersion: browser.version(), liveBackend: false, syntheticCorrectionFixtures: true, syntheticInvestigationFixtures: true, failures }, null, 2));
  console.log(JSON.stringify({ passed: true, checks: checked.length, screenshots: output, browserVersion: browser.version() }));
} finally {
  if (browser) await browser.close();
  server.kill("SIGTERM");
  await writeFile(join(output, "vite.log"), serverLog);
}
