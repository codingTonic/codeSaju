import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createContext, runInContext } from "node:vm";
import * as domain from "../frontend/app/domain.js";

const source = readFileSync(new URL("../frontend/app/main.js", import.meta.url), "utf8");
// Run the application's real route/load/delete functions without its browser bootstrap.
const behavior = [
  source.slice(source.indexOf("async function deleteItem("), source.indexOf("async function renderProductPreviews(")),
  source.slice(source.indexOf("async function route("), source.indexOf('\nform.addEventListener("submit"')),
].join("\n");
const reports = new Map(Object.values(domain.PUBLIC_EXAMPLES).map(({ file }) => [
  file, JSON.parse(readFileSync(new URL(`../frontend/app/${file.slice(2)}`, import.meta.url), "utf8")),
]));
const storage = () => {
  const values = new Map();
  return {
    getItem: key => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
    removeItem: key => values.delete(key),
  };
};

function app() {
  const state = {
    ...domain,
    current: null,
    active: null,
    library: [],
    access: [],
    exampleDrafts: new Map(),
    localStorage: storage(),
    sessionStorage: storage(),
    location: { hash: "#home" },
    view: "home",
    messages: [],
    credential: () => null,
    dialog: async () => true,
    safeMessage: error => error.message,
    document: { getElementById: () => null },
    fetch: async file => ({ ok: true, json: async () => structuredClone(reports.get(file)) }),
  };
  state.$ = () => ({
    classList: { contains: name => name === "hidden" && state.view !== "reader" },
    replaceChildren() {},
  });
  state.show = view => { state.view = view; };
  state.toast = message => state.messages.push(message);
  state.renderLibrary = () => { state.view = "library"; };
  state.renderReader = item => {
    state.current = item;
    state.view = "reader";
    domain.writeJSON(state.sessionStorage, "yeoul.last-reader", item.id);
  };
  const context = createContext(state);
  runInContext(behavior, context, { filename: "yeoul-routing-behavior.js" });
  state.navigate = async hash => {
    state.location.hash = hash;
    await context.route();
  };
  return state;
}

test("deleting a saved example also removes its previous in-tab notes and bookmarks", async () => {
  const a = app();
  await a.navigate("#example-relationship");
  a.current.note = "삭제할 관계 메모";
  a.current.favorites = ["love"];
  domain.saveLibrary(a.localStorage, a.current);
  await a.navigate("#example");
  a.current.note = "남겨둘 진로 메모";
  a.current.favorites = ["career"];
  await a.navigate("#library");
  await a.deleteItem("example-relationship");
  assert.equal(domain.loadLibrary(a.localStorage).length, 0);

  await a.navigate("#example-relationship");
  assert.equal(a.current.note, "");
  assert.equal(a.current.favorites.length, 0);
  await a.navigate("#example");
  assert.equal(a.current.note, "남겨둘 진로 메모");
  assert.deepEqual(Array.from(a.current.favorites), ["career"]);
});

test("an example fetch failure after refreshing a chapter link shows recovery feedback", async () => {
  const a = app();
  domain.writeJSON(a.sessionStorage, "yeoul.last-reader", "example-relationship");
  const normalFetch = a.fetch;
  a.fetch = async () => { throw new Error("예시 연결이 끊겼어요."); };
  await assert.doesNotReject(a.navigate("#chapter-love"));
  assert.equal(a.view, "home");
  assert.deepEqual(a.messages, ["예시 연결이 끊겼어요."]);
  assert.equal(a.current, null);

  a.fetch = normalFetch;
  await a.navigate("#example-relationship");
  assert.equal(a.view, "reader");
  assert.equal(a.current.id, "example-relationship");
});

test("switching between both examples preserves each unsaved note and bookmark independently", async () => {
  const a = app();
  await a.navigate("#example");
  a.current.note = "진로에서 확인할 일";
  a.current.favorites = ["career"];
  await a.navigate("#example-relationship");
  assert.equal(a.current.note, "");
  a.current.note = "대화 전에 먼저 묻기";
  a.current.favorites = ["love", "question"];

  await a.navigate("#example");
  assert.equal(a.current.note, "진로에서 확인할 일");
  assert.deepEqual(Array.from(a.current.favorites), ["career"]);
  await a.navigate("#example-relationship");
  assert.equal(a.current.note, "대화 전에 먼저 묻기");
  assert.deepEqual(Array.from(a.current.favorites), ["love", "question"]);
  assert.equal(domain.loadLibrary(a.localStorage).length, 0);
});
