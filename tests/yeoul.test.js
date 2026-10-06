import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import {
  ageOn,
  validateBirth,
  escapeHTML,
  saveLibrary,
  loadLibrary,
  restoreExampleReading,
  PUBLIC_EXAMPLES,
  isPublicExample,
  LIBRARY_KEY,
  readingText,
} from "../frontend/app/domain.js";
const store = () => {
  const data = new Map();
  return {
    getItem: (k) => data.get(k) || null,
    setItem: (k, v) => data.set(k, v),
    removeItem: (k) => data.delete(k),
  };
};
const report = JSON.parse(
  readFileSync(
    new URL("../frontend/app/example.json", import.meta.url),
    "utf8",
  ),
);
test("여울 validates age boundaries and actual calendar dates", () => {
  const now = new Date(2026, 8, 8);
  assert.equal(ageOn("2008-09-08", now), 18);
  assert.equal(ageOn("2008-09-09", now), 17);
  assert.equal(ageOn("1990-02-31", now), -1);
  assert.ok(
    validateBirth(
      {
        name: "별명",
        birth_date: "2019-05-15",
        birth_time_unknown: true,
        gender: "female",
        calendar_type: "solar",
      },
      now,
    ).birth_date,
  );
});
test("여울 persistent library excludes token and raw input and expires after 30 days", () => {
  const storage = store();
  saveLibrary(
    storage,
    {
      id: "one",
      report,
      token: "secret",
      input: { birth_date: "private" },
      favorites: ["career"],
      note: "내 메모",
    },
    1000,
  );
  const raw = storage.getItem(LIBRARY_KEY);
  assert.ok(!raw.includes("secret"));
  assert.ok(!raw.includes("private"));
  assert.equal(loadLibrary(storage, 1001)[0].note, "내 메모");
  assert.equal(loadLibrary(storage, 1000 + 30 * 86400000).length, 0);
  assert.equal(storage.getItem(LIBRARY_KEY), "[]");
});
test("여울 refuses extra library item instead of silently deleting existing readings", () => {
  const storage = store();
  for (let i = 0; i < 12; i++) saveLibrary(storage, { id: String(i), report });
  assert.throws(() => saveLibrary(storage, { id: "overflow", report }), /12/);
  assert.equal(loadLibrary(storage).length, 12);
});
test("여울 reopens the latest public example without losing saved notes or bookmarks", () => {
  const storage = store();
  saveLibrary(storage, {
    id: "example", report, note: "다음 주에 다시 확인할 점", favorites: ["career"],
  }, 1000);
  const latestReport = { ...report, generated_at: "2026-10-01" };
  const reopened = restoreExampleReading(latestReport, null, loadLibrary(storage, 1001));
  assert.equal(reopened.report, latestReport);
  assert.equal(reopened.note, "다음 주에 다시 확인할 점");
  assert.deepEqual(reopened.favorites, ["career"]);

  // Bookmarking another chapter after reopening must preserve the saved note.
  reopened.favorites.push("people");
  saveLibrary(storage, reopened, 1002);
  const restoredAfterReload = restoreExampleReading(latestReport, null, loadLibrary(storage, 1003));
  assert.equal(restoredAfterReload.note, "다음 주에 다시 확인할 점");
  assert.deepEqual(restoredAfterReload.favorites, ["career", "people"]);
});
test("여울 preserves an unsaved example across navigation without copying another reading's notes", () => {
  const draft = { id: "example", report, note: "이번 화면의 메모", favorites: ["career", "removed-chapter"] };
  const reopened = restoreExampleReading(report, draft);
  assert.equal(reopened.note, draft.note);
  assert.deepEqual(reopened.favorites, ["career"]);
  reopened.favorites.push("people");
  assert.deepEqual(draft.favorites, ["career", "removed-chapter"]);

  const fresh = restoreExampleReading(report, { ...draft, id: "private-reading" });
  assert.equal(fresh.note, "");
  assert.deepEqual(fresh.favorites, []);
});
test("여울 uses current saved example metadata when an older view remains in memory", () => {
  const older = { id: "example", report, note: "이전 메모", favorites: ["career"] };
  const saved = { ...older, note: "새로 저장한 메모", favorites: ["people"] };
  const reopened = restoreExampleReading(report, older, [saved]);
  assert.equal(reopened.note, saved.note);
  assert.deepEqual(reopened.favorites, saved.favorites);
  assert.notEqual(reopened.favorites, saved.favorites);
});
test("여울 escapes AI output, titles, questions and notes as plain text", () => {
  assert.equal(
    escapeHTML('<img src=x onerror="run()">'),
    "&lt;img src=x onerror=&quot;run()&quot;&gt;",
  );
  assert.equal(escapeHTML("O'Reilly & friends"), "O&#39;Reilly &amp; friends");
});
test("여울 complete text export includes every paragraph and personal notes", () => {
  const text = readingText({
    report,
    note: "다음 주에 확인할 것",
    favorites: ["career"],
  });
  for (const chapter of report.chapters)
    for (const paragraph of chapter.paragraphs)
      assert.ok(text.includes(paragraph));
  assert.ok(text.includes("다음 주에 확인할 것"));
  assert.ok(text.length > report.character_count);
});
test("여울 example is explicitly synthetic and has eight complete substantial chapters", () => {
  assert.equal(report.generation_mode, "example");
  assert.equal(report.chapters.length, 8);
  for (const c of report.chapters)
    assert.ok(
      c.paragraphs.join("").length >= (c.id === "question" ? 1000 : 700),
    );
});
test("public examples use distinct notes and bookmarks when switching topics", () => {
  const relationship = JSON.parse(readFileSync(new URL("../frontend/app/example-relationship.json", import.meta.url), "utf8"));
  const career = { id: "example", report, note: "진로 메모", favorites: ["career"] };
  const fresh = restoreExampleReading(relationship, career, [career], "example-relationship");
  assert.equal(fresh.note, "");
  assert.deepEqual(fresh.favorites, []);
  const saved = { ...fresh, note: "대화 전에 먼저 묻기", favorites: ["love"] };
  const reopened = restoreExampleReading(relationship, career, [career, saved], "example-relationship");
  assert.equal(reopened.note, saved.note);
  assert.deepEqual(reopened.favorites, ["love"]);
  assert.equal(reopened.id, "example-relationship");
  assert.equal(isPublicExample("example-relationship"), true);
  assert.equal(isPublicExample("toString"), false);
  assert.equal(isPublicExample("private-reading"), false);
});
test("both product excerpts are real reading passages with all eight chapters", () => {
  for (const [id, info] of Object.entries(PUBLIC_EXAMPLES)) {
    const r = JSON.parse(readFileSync(new URL(`../frontend/app/${info.file.slice(2)}`, import.meta.url), "utf8"));
    const question = r.chapters.find(c => c.id === "question");
    assert.ok(question.paragraphs.some(p => p.includes(r.product_excerpt || info.excerpt)), id);
    assert.equal(r.generation_mode, "example");
    assert.equal(new Set(r.chapters.map(c => c.id)).size, 8);
    assert.equal(r.preview_summary.length, 3);
    assert.equal(r.character_count, r.chapters.reduce((n, c) => n + c.paragraphs.join("").length, 0));
    for (const c of r.chapters) {
      assert.ok(c.paragraphs.join("").length >= (c.id === "question" ? 1000 : 700));
      assert.ok(c.reflection && c.practice);
      assert.ok(c.basis.every(id => r.facts.some(f => f.id === id)));
    }
  }
});
import {
  loadAccess,
  rememberAccess,
  ACCESS_KEY,
} from "../frontend/app/domain.js";
test("여울 retains independent session credentials for two readings without persistent tokens", () => {
  const storage = store();
  rememberAccess(storage, { id: "a", token: "a-key", createdAt: 1000 }, 1001);
  rememberAccess(storage, { id: "b", token: "b-key", createdAt: 2000 }, 2001);
  assert.equal(loadAccess(storage, 2002).length, 2);
  assert.equal(loadAccess(storage, 86401500).length, 1);
  assert.equal(loadAccess(storage, 86402500).length, 0);
  assert.equal(storage.getItem(ACCESS_KEY), "[]");
});
