/** Unknown connection information is allowed on desktop; explicit data-saving
 * and slow connections always keep the poster until the visitor presses play. */
export function canAutoplayHomeScene({
  viewportWidth = 0,
  reducedMotion = false,
  saveData = false,
  effectiveType = "",
} = {}) {
  return (
    Number.isFinite(viewportWidth) &&
    viewportWidth >= 900 &&
    !reducedMotion &&
    !saveData &&
    !["slow-2g", "2g", "3g"].includes(String(effectiveType).toLowerCase())
  );
}

/** Enhance the existing picture with optional motion. The picture remains the
 * fallback throughout loading, pauses, playback errors and teardown. */
export function initHomeMotion({
  document: doc = globalThis.document,
  window: win = globalThis.window,
  IntersectionObserver: Observer = win?.IntersectionObserver,
} = {}) {
  const scene = doc?.querySelector("#hero-scene");
  const video = doc?.querySelector("#hero-video");
  const button = doc?.querySelector("#hero-play");
  const home = doc?.querySelector("#home-view");
  const label = button?.querySelector("[data-play-label]");
  if (!scene || !video || !button || !home || !win) return () => {};

  const reduced = win.matchMedia?.("(prefers-reduced-motion: reduce)");
  const connection = win.navigator?.connection;
  const removers = [];
  let intent = "auto";
  let playing = false;
  let pending = false;
  let destroyed = false;
  let requestId = 0;
  let observer;
  let inViewport = !Observer && intersectsViewport();

  function listen(target, type, listener, options) {
    target?.addEventListener?.(type, listener, options);
    removers.push(() => target?.removeEventListener?.(type, listener, options));
  }

  function intersectsViewport() {
    const rect = scene.getBoundingClientRect();
    return rect.bottom > 0 && rect.top < win.innerHeight;
  }

  function automaticPlaybackAllowed() {
    return canAutoplayHomeScene({
      viewportWidth: win.innerWidth,
      reducedMotion: Boolean(reduced?.matches),
      saveData: Boolean(connection?.saveData),
      effectiveType: connection?.effectiveType,
    });
  }

  function shouldPlay() {
    return (
      !destroyed &&
      !doc.hidden &&
      doc.visibilityState !== "hidden" &&
      !home.hidden &&
      !home.classList.contains("hidden") &&
      home.getAttribute("aria-hidden") !== "true" &&
      inViewport &&
      (intent === "manual" || (intent === "auto" && automaticPlaybackAllowed()))
    );
  }

  function renderState() {
    scene.classList.toggle("is-video-playing", playing);
    button.setAttribute("aria-pressed", String(playing));
    button.setAttribute("aria-busy", String(pending));
    const text = playing
      ? "풍경 일시정지"
      : intent === "error"
        ? "영상 다시 재생"
        : "풍경 재생";
    if (label) label.textContent = text;
    button.setAttribute("aria-label", text);
  }

  function pause() {
    // A visibility change can abort a pending play(). Its eventual rejection is
    // an intentional interruption, not a failure requiring a retry message.
    requestId += 1;
    pending = false;
    playing = false;
    video.pause();
    renderState();
  }

  function fail() {
    if (destroyed) return;
    intent = "error";
    pause();
  }

  function reconcile() {
    if (destroyed) return;
    if (!shouldPlay()) {
      pause();
      return;
    }
    if (playing || pending) return;
    if (!video.getAttribute("src")) {
      const source = video.dataset.src;
      if (!source) {
        fail();
        return;
      }
      video.src = source;
    }
    const id = ++requestId;
    pending = true;
    renderState();
    try {
      Promise.resolve(video.play()).then(
        () => {
          if (destroyed || id !== requestId) return;
          pending = false;
          if (!shouldPlay()) pause();
          else renderState();
        },
        () => {
          if (!destroyed && id === requestId) fail();
        },
      );
    } catch {
      if (id === requestId) fail();
    }
  }

  listen(button, "click", () => {
    if (playing || pending) {
      intent = "paused";
      pause();
      return;
    }
    // Explicit play is allowed even when the automatic-motion policy is off.
    // Reload after a media error so a previously failed source can recover.
    if (intent === "error" && video.error) video.load();
    intent = "manual";
    reconcile();
  });
  listen(video, "playing", () => {
    if (!shouldPlay()) {
      pause();
      return;
    }
    playing = true;
    pending = false;
    renderState();
  });
  listen(video, "pause", () => {
    playing = false;
    renderState();
  });
  listen(video, "error", fail);
  listen(doc, "visibilitychange", reconcile);
  listen(doc, "yeoul:viewchange", reconcile);
  listen(win, "resize", () => {
    if (!Observer) inViewport = intersectsViewport();
    reconcile();
  });
  listen(connection, "change", reconcile);
  if (reduced?.addEventListener) listen(reduced, "change", reconcile);
  else if (reduced?.addListener) {
    reduced.addListener(reconcile);
    removers.push(() => reduced.removeListener(reconcile));
  }

  if (Observer) {
    observer = new Observer((entries) => {
      const entry = entries.find((item) => item.target === scene);
      if (!entry) return;
      inViewport = entry.isIntersecting;
      reconcile();
    });
    observer.observe(scene);
  } else {
    listen(
      win,
      "scroll",
      () => {
        inViewport = intersectsViewport();
        reconcile();
      },
      { passive: true },
    );
  }

  renderState();
  reconcile();
  return () => {
    destroyed = true;
    observer?.disconnect();
    for (const remove of removers) remove();
    intent = "paused";
    pause();
  };
}
