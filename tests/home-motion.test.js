import test from "node:test";
import assert from "node:assert/strict";
import {
  canAutoplayHomeScene,
  initHomeMotion,
} from "../frontend/app/home-motion.js";

class Element extends EventTarget {
  constructor() {
    super();
    this.attributes = new Map();
    const classes = new Set();
    this.classList = {
      contains: (name) => classes.has(name),
      toggle: (name, on) => (on ? classes.add(name) : classes.delete(name)),
    };
    this.dataset = {};
    this.hidden = false;
    this.textContent = "";
  }
  setAttribute(key, value) {
    this.attributes.set(key, String(value));
  }
  getAttribute(key) {
    return this.attributes.get(key) ?? null;
  }
  emit(type) {
    this.dispatchEvent(new Event(type));
  }
  getBoundingClientRect() {
    return { top: 100, bottom: 600 };
  }
}

function fixture({
  width = 1200,
  reduce = false,
  saveData = false,
  type = "4g",
  unknown = false,
} = {}) {
  const scene = new Element();
  const video = new Element();
  const button = new Element();
  const label = new Element();
  const home = new Element();
  const doc = new Element();
  const win = new Element();
  const media = new Element();
  const connection = new Element();
  Object.assign(media, { matches: reduce });
  Object.assign(connection, { saveData, effectiveType: type });
  Object.assign(win, {
    innerWidth: width,
    innerHeight: 800,
    navigator: { connection: unknown ? undefined : connection },
    matchMedia: () => media,
  });
  doc.visibilityState = "visible";
  const nodes = {
    "#hero-scene": scene,
    "#hero-video": video,
    "#hero-play": button,
    "#home-view": home,
  };
  doc.querySelector = (selector) => nodes[selector];
  button.querySelector = () => label;
  video.dataset.src = "./assets/higgsfield/hero-loop.mp4";
  Object.defineProperty(video, "src", {
    set: (value) => video.setAttribute("src", value),
    get: () => video.getAttribute("src"),
  });
  video.playCalls = 0;
  video.loadCalls = 0;
  video.playBehavior = () => Promise.resolve();
  video.play = () => {
    video.playCalls++;
    return video.playBehavior();
  };
  video.pause = () => video.emit("pause");
  video.load = () => {
    video.loadCalls++;
    video.error = null;
  };
  const f = { scene, video, button, label, home, doc, win, media, connection };
  f.init = (extras = {}) =>
    initHomeMotion({ document: doc, window: win, ...extras });
  return f;
}

const settle = async () => {
  await Promise.resolve();
  await Promise.resolve();
};

test("automatic hero motion requires desktop and honors explicit motion/data limits", () => {
  assert.equal(canAutoplayHomeScene({ viewportWidth: 900 }), true);
  assert.equal(canAutoplayHomeScene({ viewportWidth: 899 }), false);
  assert.equal(canAutoplayHomeScene({ viewportWidth: NaN }), false);
  for (const condition of [
    { reducedMotion: true },
    { saveData: true },
    ...["slow-2g", "2g", "3g"].map((effectiveType) => ({ effectiveType })),
  ])
    assert.equal(
      canAutoplayHomeScene({ viewportWidth: 1400, ...condition }),
      false,
    );
  assert.equal(
    canAutoplayHomeScene({ viewportWidth: 1400, effectiveType: "4g" }),
    true,
  );
});

test("poster policies do not assign a video source before explicit playback", () => {
  for (const options of [
    { width: 390 },
    { reduce: true },
    { saveData: true },
    { type: "3g" },
  ]) {
    const f = fixture(options);
    const cleanup = f.init();
    assert.equal(f.video.src, null);
    assert.equal(f.video.playCalls, 0);
    assert.equal(f.button.getAttribute("aria-pressed"), "false");
    f.button.emit("click");
    assert.equal(f.video.src, f.video.dataset.src);
    assert.equal(f.video.playCalls, 1);
    assert.equal(f.scene.classList.contains("is-video-playing"), false);
    f.video.emit("playing");
    assert.equal(f.scene.classList.contains("is-video-playing"), true);
    assert.equal(f.label.textContent, "풍경 일시정지");
    cleanup();
  }
});

test("desktop with unknown connectivity keeps its poster until playback actually starts", async () => {
  const f = fixture({ unknown: true });
  const cleanup = f.init();
  await settle();
  assert.equal(f.video.playCalls, 1);
  assert.equal(f.scene.classList.contains("is-video-playing"), false);
  f.video.emit("playing");
  assert.equal(f.button.getAttribute("aria-pressed"), "true");
  cleanup();
});

test("view and document visibility pause motion, but returning respects a user pause", () => {
  const f = fixture();
  const cleanup = f.init();
  f.video.emit("playing");
  f.home.classList.toggle("hidden", true);
  f.doc.emit("yeoul:viewchange");
  assert.equal(f.scene.classList.contains("is-video-playing"), false);
  f.home.classList.toggle("hidden", false);
  f.doc.emit("yeoul:viewchange");
  assert.equal(f.video.playCalls, 2);
  f.video.emit("playing");
  f.doc.hidden = true;
  f.doc.emit("visibilitychange");
  assert.equal(f.button.getAttribute("aria-pressed"), "false");
  f.doc.hidden = false;
  f.doc.emit("visibilitychange");
  f.video.emit("playing");
  f.button.emit("click");
  const calls = f.video.playCalls;
  f.home.classList.toggle("hidden", true);
  f.doc.emit("yeoul:viewchange");
  f.home.classList.toggle("hidden", false);
  f.doc.emit("yeoul:viewchange");
  f.win.emit("resize");
  assert.equal(f.video.playCalls, calls);
  cleanup();
});

test("offscreen hero loads no video and intersection controls pause and resume", () => {
  const f = fixture();
  let notify;
  let disconnected = false;
  class Observer {
    constructor(callback) {
      notify = callback;
    }
    observe() {}
    disconnect() {
      disconnected = true;
    }
  }
  const cleanup = f.init({ IntersectionObserver: Observer });
  assert.equal(f.video.src, null);
  notify([{ target: f.scene, isIntersecting: true }]);
  f.video.emit("playing");
  notify([{ target: f.scene, isIntersecting: false }]);
  assert.equal(f.scene.classList.contains("is-video-playing"), false);
  notify([{ target: f.scene, isIntersecting: true }]);
  assert.equal(f.video.playCalls, 2);
  cleanup();
  assert.equal(disconnected, true);
});

test("autoplay policy changes stop initial motion and explicit play remains available", () => {
  const f = fixture();
  const cleanup = f.init();
  f.video.emit("playing");
  f.media.matches = true;
  f.media.emit("change");
  assert.equal(f.scene.classList.contains("is-video-playing"), false);
  f.button.emit("click");
  f.video.emit("playing");
  assert.equal(f.scene.classList.contains("is-video-playing"), true);
  cleanup();

  const small = fixture();
  const cleanupSmall = small.init();
  small.video.emit("playing");
  small.win.innerWidth = 390;
  small.win.emit("resize");
  assert.equal(small.scene.classList.contains("is-video-playing"), false);
  cleanupSmall();
});

test("play rejection keeps the poster without automatic retries; deliberate retry can recover", async () => {
  const f = fixture();
  f.video.playBehavior = () => Promise.reject(new Error("play was blocked"));
  const cleanup = f.init();
  await settle();
  assert.equal(f.label.textContent, "영상 다시 재생");
  assert.equal(f.button.getAttribute("aria-pressed"), "false");
  assert.equal(f.scene.classList.contains("is-video-playing"), false);
  f.win.emit("resize");
  f.doc.emit("visibilitychange");
  assert.equal(f.video.playCalls, 1);
  f.video.playBehavior = () => Promise.resolve();
  f.button.emit("click");
  f.video.emit("playing");
  assert.equal(f.label.textContent, "풍경 일시정지");
  f.video.error = new Error("network interrupted");
  f.video.emit("error");
  assert.equal(f.label.textContent, "영상 다시 재생");
  f.button.emit("click");
  assert.equal(f.video.loadCalls, 1);
  f.video.emit("playing");
  assert.equal(f.scene.classList.contains("is-video-playing"), true);
  cleanup();
});

test("aborted pending playback is not reported as an error and teardown removes listeners", async () => {
  const f = fixture();
  let reject;
  f.video.playBehavior = () =>
    new Promise((resolve, rejected) => {
      reject = rejected;
    });
  const cleanup = f.init();
  f.button.emit("click");
  reject(new Error("AbortError"));
  await settle();
  assert.equal(f.label.textContent, "풍경 재생");
  const calls = f.video.playCalls;
  cleanup();
  f.button.emit("click");
  f.video.emit("playing");
  f.win.emit("resize");
  f.media.emit("change");
  assert.equal(f.video.playCalls, calls);
  assert.equal(f.scene.classList.contains("is-video-playing"), false);
});
