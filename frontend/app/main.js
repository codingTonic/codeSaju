import { apiClient } from "../assets/js/api.js";
import { initFreeChart } from "./free-chart.js";
import { initHomeMotion } from "./home-motion.js";
import {
  TOPICS,
  PILLAR_LABELS,
  ELEMENT_LABELS,
  POLICY,
  SESSION_KEY,
  LIBRARY_KEY,
  escapeHTML as e,
  readJSON,
  writeJSON,
  loadLibrary,
  saveLibrary,
  restoreExampleReading,
  PUBLIC_EXAMPLES,
  isPublicExample,
  validateBirth,
  readingText,
  ACCESS_KEY,
  loadAccess,
  rememberAccess,
} from "./domain.js";
const SITE_TITLE = document.title;
const exampleDrafts = new Map();
const VIEW_TITLES = {
  instant: "무료 사주 기본 정보 | 여울",
  start: "개인 풀이 입력 | 여울",
  product: "상품·이용 안내 | 여울",
  privacy: "개인정보 처리 안내 | 여울",
  library: "내 서랍 | 여울",
  loading: "풀이를 만들고 있어요 | 여울",
};
const $ = (s) => document.querySelector(s),
  $$ = (s) => [...document.querySelectorAll(s)];
function browserStorage(kind) {
  try { return window[kind]; } catch {
    return {getItem: () => null, setItem: () => {throw new Error('저장소 접근 불가');}, removeItem: () => {}};
  }
}
const sessionStorage = browserStorage('sessionStorage');
const localStorage = browserStorage('localStorage');
let step = 1,
  topic = "self",
  active = readJSON(sessionStorage, SESSION_KEY, null),
  current = null,
  pollTimer,
  toastTimer,
  starting = false;
if (active && (!active.createdAt || Date.now() - active.createdAt > 86400000)) {
  sessionStorage.removeItem(SESSION_KEY);
  active = null;
}
let library = loadLibrary(localStorage);
let access = loadAccess(sessionStorage);
if (active?.token) {
  rememberAccess(sessionStorage, active);
  access = loadAccess(sessionStorage);
}
function credential(id) {
  const candidate =
    active?.id === id ? active : access.find((x) => x.id === id);
  return candidate?.token && candidate.createdAt + 86400000 > Date.now()
    ? candidate
    : null;
}
const form = $("#reading-form");
const safeMessage = (error) =>
  error?.status === 429
    ? "지금은 요청이 많아요. 잠시 쉬었다가 다시 이용해주세요."
    : error?.status === 404
      ? "풀이가 만료되었거나 이 탭에 조회 권한이 없어요. 보관한 내용은 계속 읽을 수 있어요."
      : error?.status === 0
        ? "연결이 원활하지 않아요. 잠시 후 다시 시도해주세요."
        : error?.getUserMessage?.() ||
          error.message ||
          "작업을 완료하지 못했어요. 다시 시도해주세요.";
function toast(message) {
  clearTimeout(toastTimer);
  $("#toast").textContent = message;
  $("#toast").classList.remove("hidden");
  toastTimer = setTimeout(() => $("#toast").classList.add("hidden"), 5000);
}
function show(view) {
  $$(".view").forEach((v) =>
    v.classList.toggle("hidden", v.id !== view + "-view"),
  );
  document.documentElement.classList.toggle(
    "night",
    view === "reader" && readJSON(sessionStorage, "yeoul.night", false),
  );
  document.title =
    view === "reader"
      ? `여울 · ${current?.report?.name || "나"}님의 흐름`
      : VIEW_TITLES[view] || SITE_TITLE;
  document.body.dataset.view = view;
  document.dispatchEvent(new CustomEvent("yeoul:viewchange", { detail: { view } }));
  window.scrollTo(0, 0);
  $("#main").focus({ preventScroll: true });
}
function dialog(title, description, confirmText) {
  $("#dialog-title").textContent = title;
  $("#dialog-description").textContent = description;
  $("#dialog-confirm").textContent = confirmText;
  const d = $("#action-dialog");
  d.returnValue = "cancel";
  d.showModal();
  return new Promise((resolve) =>
    d.addEventListener("close", () => resolve(d.returnValue === "confirm"), {
      once: true,
    }),
  );
}
function auth(item) {
  return { headers: { Authorization: `Bearer ${item.token}` } };
}
function storeActive() {
  if (active && !writeJSON(sessionStorage, SESSION_KEY, active))
    toast(
      "이 탭에 저장할 수 없어요. 페이지를 닫기 전에 텍스트로 내려받아주세요.",
    );
}
function updateItem(item = current) {
  if (!item) return;
  if (active?.id === item.id) {
    active = {
      ...active,
      report: item.report,
      note: item.note,
      favorites: item.favorites,
    };
    storeActive();
  }
  const saved = library.find((x) => x.id === item.id);
  if (saved) {
    Object.assign(saved, {
      report: item.report,
      note: item.note,
      favorites: item.favorites,
    });
    if (!writeJSON(localStorage, LIBRARY_KEY, library))
      toast(
        "기기 저장 공간이 부족해 변경을 보관하지 못했어요. 텍스트로 내려받아주세요.",
      );
  }
}
function payload() {
  const d = new FormData(form);
  return {
    topic: d.get("topic"),
    name: String(d.get("name") || "").trim(),
    birth_date: d.get("birth_date"),
    birth_time: d.has("birth_time_unknown") ? null : d.get("birth_time"),
    birth_time_unknown: d.has("birth_time_unknown"),
    gender: d.get("gender"),
    calendar_type: d.get("calendar_type"),
    is_leap_month: d.get("calendar_type") === "lunar" && d.has("is_leap_month"),
    relationship_status: d.get("relationship_status"),
    focus_concern: String(d.get("focus_concern") || "").trim() || null,
    processing_consent: d.has("processing_consent"),
    age_confirmed: d.has("age_confirmed"),
    privacy_policy_version: POLICY,
    birth_region: "KR",
  };
}
function selectTopic(value) {
  topic = Object.hasOwn(TOPICS, value) ? value : "self";
  $$("[data-topic]").forEach((b) =>
    b.setAttribute("aria-pressed", String(b.dataset.topic === topic)),
  );
  form.elements.topic.value = topic;
}
function clearErrors() {
  $("#form-errors").classList.add("hidden");
  $$(".field-error").forEach((x) => (x.textContent = ""));
  $$("[aria-invalid]").forEach((x) => x.removeAttribute("aria-invalid"));
}
function errors(messages) {
  const entries = Object.entries(messages);
  $("#form-errors").innerHTML =
    "<strong>아래 내용을 확인해주세요.</strong><ul>" +
    entries.map(([key, value]) => `<li>${e(value)}</li>`).join("") +
    "</ul>";
  $("#form-errors").classList.remove("hidden");
  for (const [key, value] of entries) {
    const field = form.elements.namedItem(key),
      label = document.getElementById(key + "-error");
    if (field?.setAttribute) field.setAttribute("aria-invalid", "true");
    if (label) label.textContent = value;
  }
  $("#form-errors").focus();
}
function setStep(value) {
  step = value;
  $("#start-view").setAttribute(
    "aria-labelledby",
    step === 1 ? "form-title" : `form-title-${step}`,
  );
  clearErrors();
  $$("[data-form-step]").forEach((x) =>
    x.classList.toggle("hidden", Number(x.dataset.formStep) !== step),
  );
  $$("[data-step-label]").forEach((x) => {
    if (Number(x.dataset.stepLabel) === step)
      x.setAttribute("aria-current", "step");
    else x.removeAttribute("aria-current");
  });
  $("#previous-step").classList.toggle("hidden", step === 1);
  $("#next-step").textContent =
    step === 1
      ? "출생 정보 입력하기 ↗"
      : step === 2
        ? "입력 정보 확인하기 ↗"
        : "나의 풀이 만들기";
  if (step === 3) {
    const d = payload();
    $("#review-data").innerHTML = [
      ["관심 주제", TOPICS[d.topic]],
      ["이름", d.name],
      [
        "생년월일",
        `${d.birth_date} · ${d.calendar_type === "lunar" ? "음력" : "양력"}${d.is_leap_month ? " 윤달" : ""}`,
      ],
      [
        "태어난 시간",
        d.birth_time_unknown ? "시간 모름 · 시간에 해당하는 글자 제외" : d.birth_time,
      ],
      ["출생 시 성별", d.gender === "female" ? "여성" : "남성"],
      ["기준", "대한민국 표준시"],
    ]
      .map(([k, v]) => `<dt>${e(k)}</dt><dd>${e(v)}</dd>`)
      .join("");
    $("#review-question").textContent = d.focus_concern
      ? `“${d.focus_concern}”`
      : "구체적인 질문 없이, 고른 주제를 중심으로 읽어요.";
  }
  window.scrollTo(0, 0);
  const title = $(
    `[data-form-step="${step}"] h1,[data-form-step="${step}"] h2`,
  );
  title.tabIndex = -1;
  title.focus({ preventScroll: true });
}
async function startReading() {
  if (starting) return;
  if (active?.token && !active.report && active.status !== "failed") {
    if (
      await dialog(
        "쓰고 있는 풀이가 있어요",
        "기존 풀이의 진행 상황으로 돌아갈까요?",
        "기존 풀이 보기",
      )
    )
      location.hash = "loading";
    return;
  }
  starting = true;
  $("#next-step").disabled = true;
  clearErrors();
  try {
    const created = await apiClient.post("/api/v2/readings", payload(), {
      timeoutMs: 30000,
    });
    active = {
      id: created.task_id,
      token: created.access_token,
      createdAt: Date.now(),
      status: "queued",
      report: null,
      note: "",
      favorites: [],
    };
    if (!writeJSON(sessionStorage, SESSION_KEY, active)) {
      await apiClient.request(
        `/api/v1/tasks/${encodeURIComponent(active.id)}`,
        { method: "DELETE", ...auth(active) },
      );
      active = null;
      throw new Error(
        "브라우저가 탭 저장을 막고 있어요. 사이트 저장을 허용한 뒤 다시 시도해주세요.",
      );
    }
    rememberAccess(sessionStorage, active);
    access = loadAccess(sessionStorage);
    location.hash = "loading";
    poll();
  } catch (error) {
    errors({ service: safeMessage(error) });
  } finally {
    starting = false;
    $("#next-step").disabled = false;
  }
}
function loading(focus = true) {
  if (focus) show("loading");
  const failed = active?.status === "failed";
  $("#generation-error").classList.toggle("hidden", !failed);
  $("#retry-reading").classList.toggle("hidden", !failed);
  $("#cancel-reading").classList.toggle("hidden", !active?.token);
  if (failed)
    $("#generation-error").textContent =
      active.error ||
      "풀이를 완성하지 못했어요. 입력을 확인하고 다시 시도해주세요.";
  $("#reading-progress").value = active?.percent || 0;
  $("#progress-label").textContent = failed
    ? "생성이 중단되었어요."
    : active?.percent >= 95
      ? "8개 장의 분량과 근거를 최종 확인하고 있어요."
      : active?.percent > 10
        ? `${Math.min(8, Math.round(((active.percent - 10) / 85) * 8))}개 장 작성 완료 · 다음 이야기를 쓰고 있어요.`
        : "사주 표를 계산하고 해설을 준비하고 있어요.";
}
async function poll() {
  clearTimeout(pollTimer);
  if (!active?.token || active.report || active.status === "failed") return;
  const id = active.id;
  try {
    const data = await apiClient.get(
      "/api/v1/progress",
      { task_id: id },
      auth(active),
    );
    if (active?.id !== id) return;
    Object.assign(active, {
      status: data.status,
      percent: data.percent_overall,
      error: data.error,
    });
    if (data.status === "completed" && data.analysis_result?.version === 2) {
      active.report = data.analysis_result;
      storeActive();
      if (location.hash === "#loading") {
        location.hash = "read";
      } else toast("풀이가 완성됐어요. 내 서랍에서 열어보세요.");
      return;
    }
    storeActive();
    if (location.hash === "#loading") loadingUpdate();
    if (data.status === "failed") return;
  } catch (error) {
    if (active?.id !== id) return;
    if (error.status === 404) {
      active.status = "failed";
      active.error =
        "서버에서 풀이를 찾지 못했어요. 서버 재시작이나 보관 시간 만료 후에는 새로 시작해주세요.";
      storeActive();
      if (location.hash === "#loading") loading();
      return;
    }
    if (location.hash === "#loading")
      $("#progress-label").textContent =
        "연결을 다시 확인하고 있어요. 생성된 내용은 서버에서 계속 준비될 수 있어요.";
  }
  pollTimer = setTimeout(poll, 3500);
}
function loadingUpdate() {
  loading(false);
}
function basisHTML(ids, report) {
  return `<details class="basis"><summary>풀이에 참고한 사주 정보</summary><dl>${ids
    .map((id) => {
      const f = report.facts.find((x) => x.id === id);
      return f ? `<dt>${e(f.label)}</dt><dd>${e(friendlyFact(f))}</dd>` : "";
    })
    .join(
      "",
    )}</dl><p>위 정보는 계산값이며, 본문의 성향과 조언은 전통적인 해석이에요.</p></details>`;
}
function friendlyFact(f) {
  if (!f.text.startsWith("{")) return f.text;
  try {
    const d = JSON.parse(f.text);
    return [
      d.gan_zhi_ko || d.gan_zhi,
      d.stem_ten_god ? `윗글자의 관계: ${d.stem_ten_god}` : "",
      d.branch_main_ten_god ? `아랫글자 중심의 관계: ${d.branch_main_ten_god}` : "",
      d.boundary_label || "",
      d.transition_date ? `${d.transition_date}부터 ${d.end_date}까지` : "",
    ]
      .filter(Boolean)
      .join(" · ");
  } catch {
    return f.text;
  }
}
function orderChapters(report) {
  const preferred = {
    self: "nature",
    career: "career",
    love: "love",
    money: "money",
    flow: "year",
  }[report.topic];
  const order = ["question", preferred, ...report.chapters.map((x) => x.id)];
  return [...new Set(order)]
    .map((id) => report.chapters.find((c) => c.id === id))
    .filter(Boolean);
}
function renderReader(item) {
  current = item;
  writeJSON(sessionStorage, 'yeoul.last-reader', item.id);
  const r = item.report,
    chapters = orderChapters(r),
    example = isPublicExample(item.id),
    saved = library.some((x) => x.id === item.id),
    canChat = !example && Boolean(credential(item.id)),
    preview = example && Array.isArray(r.preview_summary) ? r.preview_summary : [];
  const summary = preview.length ? `<section id="reading-summary" class="reading-summary" aria-labelledby="reading-summary-heading" tabindex="-1"><div><p class="small-label">먼저 짧게 읽기</p><h2 id="reading-summary-heading">세 줄로 보는 핵심</h2><p class="reading-summary-question">질문: ${e(r.question)}</p><dl>${preview.map(point => `<div><dt>${e(point.label)}</dt><dd>${e(point.text)}</dd></div>`).join("")}</dl><p class="reading-summary-note">공개 풀이를 짧게 정리했어요. 아래에서 해석의 근거와 생활 속 예시를 이어 읽을 수 있어요.</p><a class="button primary" href="#chapter-question">자세한 풀이 이어 읽기</a><p class="reading-summary-duration">전체 ${chapters.length}개 장 · 천천히 읽으면 약 ${Math.ceil(r.character_count / 450)}분</p></div></section>` : "";
  const body = chapters
    .map(
      (c) =>
        `<article id="chapter-${e(c.id)}" class="chapter category-${e(c.id)}"><p class="chapter-category">${e(c.category)}</p><h2>${e(c.title)}</h2><p class="chapter-lead">${e(c.lead)}</p><div class="chapter-body">${c.paragraphs.map((p) => `<p>${e(p)}</p>`).join("")}</div><div class="reflection"><span>나에게 비춰보기</span><p>${e(c.reflection)}</p></div><div class="practice"><strong>일상에서 해볼 작은 시도</strong><p>${e(c.practice)}</p></div>${basisHTML(c.basis, r)}<button class="bookmark" data-bookmark="${e(c.id)}" aria-pressed="${item.favorites?.includes(c.id) || false}">${item.favorites?.includes(c.id) ? "✓ 마음에 남긴 문장" : "♡ 이 장의 한 문장 남기기"}</button></article>`,
    )
    .join("");
  const pillars = r.profile.pillars,
    missing = !r.profile.time_known;
  $("#reader-view").innerHTML =
    `${example ? '<div class="example-notice">공개 예시 · 가상 인물 ‘하루’의 사주 정보에 고민을 더해 구성한 설명용 풀이예요. 개인 풀이·추가 질문은 준비 중이에요. <a href="#start">내 사주 기본 정보 보기 ↗</a></div>' : ""}${example ? `<nav class="example-switcher" aria-label="공개 예시 선택">${Object.entries(PUBLIC_EXAMPLES).map(([id, info]) => `<a href="#${id}" ${id === item.id ? 'aria-current="page"' : ""}>${e(info.label)} · 8장 예시</a>`).join("")}<a href="#product">상품·제공 기준 보기</a></nav>` : ""}<div class="reader-heading${preview.length ? " reader-heading-brief" : ""}"><p class="small-label">${e(TOPICS[r.topic])}에서 시작한 이야기</p><h1>${preview.length ? `${e(r.name)}님의 고민, 핵심부터 읽어보세요.` : `${e(r.name)}님의 삶에 흐르는<br>고유한 결을 읽어요.`}</h1><div class="reader-meta">${preview.length ? "<span>짧은 요약 → 상세 풀이</span>" : `<span>${e(r.generated_at)} 기준</span><span>8개의 장</span><span>본문 ${Number(r.character_count).toLocaleString()}자</span><span>천천히, 약 ${Math.ceil(r.character_count / 450)}분</span>`}</div></div>${summary}<div class="reader-layout"><aside class="reader-sidebar"><details class="toc" ${innerWidth > 700 ? "open" : ""}><summary>나의 풀이 목차</summary><nav aria-label="풀이 목차">${preview.length ? '<a href="#reading-summary">세 줄 핵심 요약</a>' : ""}${chapters.map((c) => `<a href="#chapter-${e(c.id)}">${e(c.category)}</a>`).join("")}<a href="#my-chart">나의 사주 표 살펴보기</a><a href="#conversation">${example ? "추가 질문 안내" : "이어서 물어보기"}</a><a href="#my-notes">마음에 남긴 것들</a></nav></details><div class="reader-tools" aria-label="읽기 설정"><button data-font="-1" aria-label="본문 글자 작게">가 −</button><button data-font="1" aria-label="본문 글자 크게">가 +</button><button id="night-toggle" aria-pressed="${document.documentElement.classList.contains("night")}">야간 읽기</button></div><div class="reader-actions"><button id="save-reading" class="button primary">${saved ? "기기에 보관 중" : "이 기기에 30일 보관"}</button><button id="download-reading" class="button secondary">전체 텍스트 내려받기</button><button id="print-reading" class="button secondary">인쇄 / PDF 저장</button>${!example ? '<button id="delete-reading" class="quiet-button">이 풀이 삭제</button>' : ""}</div><p class="storage-note">${saved ? "이 브라우저에서만 볼 수 있어요. 보관 기한은 내 서랍에서 확인해주세요." : example ? "예시도 기기에 보관할 수 있어요." : "현재 탭에서만 볼 수 있어요. 다시 읽고 싶다면 직접 보관해주세요."}</p></aside><div class="reader-content">${body}<section id="my-chart" class="chart-section"><p class="small-label">해석의 출발점</p><h2>나의 사주 표 살펴보기</h2><p>태어난 해·달·날·시간을 글자로 나타낸 표예요. 이 표를 ‘원국’ 또는 ‘명식’이라고 해요. 각 세로 칸의 윗글자는 ‘천간’, 아랫글자는 ‘지지’라고 불러요.</p><div class="pillar-grid">${[
      "year",
      "month",
      "day",
      "time",
    ]
      .map((key) => {
        const p = pillars.find((x) => x.key === key);
        return p
          ? `<div class="pillar"><span>${e(PILLAR_LABELS[key] || p.label)}</span><b>${e(p.gan_zhi_ko)}</b><small>${e(p.gan_zhi)}</small></div>`
          : '<div class="pillar"><span>태어난 시간 (시주)</span><b>?</b><small>시간 미상</small></div>';
      })
      .join(
        "",
      )}</div><p>${e(r.profile.day_master.label)}은 태어난 날의 윗글자예요. 사주에서 나를 나타내는 기준으로 쓰며 ‘일간’이라고 불러요. ${e(r.profile.day_master.archetype)}</p><div class="element-row">${Object.entries(
      r.profile.element_counts,
    )
      .map(([k, v]) => `<span>${e(ELEMENT_LABELS[k] || k)} ${Number(v)}자</span>`)
      .join(
        "",
      )}</div><p>나무·불·흙·금속·물, 다섯 요소를 ‘오행’이라고 해요. 위 숫자는 사주 표에서 각 요소에 해당하는 글자 수예요. 능력의 점수나 부족한 성격, 운의 좋고 나쁨을 뜻하지 않아요.</p><details class="basis"><summary>어떻게 계산했나요?</summary>${r.profile.calculation_basis.map((s) => `<p>${e(s)}</p>`).join("")}<p>${e(r.profile.interpretation_limits)}</p></details>${missing ? "<p>태어난 시간을 몰라 시간에 해당하는 글자를 제외했어요. 10년 단위의 흐름(대운)이 시작되는 때는 예상한 값이에요.</p>" : ""}</section><section id="conversation" class="conversation"><p class="small-label">${example ? "준비 중 · 개인 풀이 기능" : "이야기는 여기서 이어져요"}</p><h2>${example ? "추가 질문은 준비 중이에요." : "읽고 나니, 더 궁금한가요?"}</h2><p class="muted">${example ? "내 질문을 반영한 개인 풀이와 이어서 묻는 기능을 준비하고 있어요. 공개 예시에서는 새 질문을 보낼 수 없어요." : "지금 읽은 사주 표와 풀이를 바탕으로 함께 생각해요.<br>한 풀이에서 최대 5번, 생성 요청 후 최대 24시간 안에 물어볼 수 있어요."}</p><div id="chat-history"></div>${canChat ? `<div class="suggested-questions"><button data-followup="제 강점을 일상에서 확인하려면 어떤 장면을 살펴보면 좋을까요?">내 강점은 어디서 드러날까요?</button><button data-followup="지금 질문과 관련해서 이번 주에 할 수 있는 작은 실험을 더 구체적으로 알려주세요.">이번 주엔 무엇부터 해볼까요?</button></div><form id="question-form"><label class="field-label" for="followup-question">이어서 묻고 싶은 이야기</label><textarea id="followup-question" minlength="5" maxlength="600" rows="3" placeholder="지금 읽은 내용 중 더 알고 싶은 부분을 적어주세요." required></textarea><p class="field-help">연락처·신분 정보·다른 사람의 개인정보는 적지 말아주세요.</p><button class="button primary" type="submit">이어서 물어보기 · ${5 - (r.followups?.length || 0)}회 남음</button><p id="chat-status" class="chat-status" role="status"></p></form>` : `<div class="loading-note"><p>${example ? "지금은 무료 사주 기본 정보와 가상 인물의 공개 예시 읽기를 이용할 수 있어요." : "이 탭에는 대화 조회 권한이 없거나 24시간이 지났어요. 보관한 풀이와 지난 대화는 계속 읽을 수 있어요."}</p><a class="text-link" href="#start">내 사주 기본 정보 보기 ↗</a></div>`}</section><section id="my-notes" class="notes-section"><p class="small-label">나의 말로 다시 적어두기</p><h2>마음에 남긴 것들</h2><p class="muted">맞는 이야기, 다른 이야기, 해보고 싶은 일.<br>내가 겪는 실제 삶을 기준으로 적어보세요.</p><div id="favorite-list"></div><label class="field-label" for="reading-note">나만의 메모</label><textarea id="reading-note" maxlength="3000" rows="5" placeholder="다음에 이 풀이를 펼칠 나에게 남기는 말">${e(item.note || "")}</textarea><p class="print-note">${e(item.note || "남긴 메모가 없어요.")}</p><p class="notes-status" id="note-status">${saved ? "메모는 이 기기에 자동 저장돼요." : example ? "예시 메모는 이 화면에서만 유지돼요." : "메모는 현재 탭에만 저장돼요."}</p></section><p class="reader-endnote">여울은 전통적인 사주 해석을 자기 이해의 실마리로 제공해요. 미래의 사건이나 상대의 마음을 확정할 수 없으며, 건강·법률·투자 등 중요한 결정은 실제 정보와 전문가의 조언을 참고해주세요.</p></div></div>`;
  renderChat();
  renderFavorites();
  show("reader");
  $("#night-toggle").setAttribute(
    "aria-pressed",
    String(document.documentElement.classList.contains("night")),
  );
}
function renderFavorites() {
  if (!current) return;
  const selected = current.report.chapters.filter((c) =>
    current.favorites?.includes(c.id),
  );
  $("#favorite-list").innerHTML = selected.length
    ? `<ul>${selected.map((c) => `<li>${e(c.lead)}</li>`).join("")}</ul>`
    : '<p class="field-help">각 장에서 ‘한 문장 남기기’를 누르면 여기에 모여요.</p>';
}
function renderChat() {
  if (!current) return;
  $("#chat-history").innerHTML = (current.report.followups || [])
    .map(
      (a) =>
        `<div class="chat-turn"><p class="chat-question">${e(a.question)}</p><div class="chat-answer">${a.paragraphs.map((p) => `<p>${e(p)}</p>`).join("")}<p class="chat-reflection">${e(a.reflection)}</p></div>${basisHTML(a.basis, current.report)}</div>`,
    )
    .join("");
  const b = $("#question-form button[type=submit]");
  if (b) {
    const n = 5 - (current.report.followups?.length || 0);
    b.textContent =
      n > 0 ? `이어서 물어보기 · ${n}회 남음` : "5번의 대화를 모두 나누었어요";
    b.disabled = n <= 0;
  }
}
async function askQuestion(formEl) {
  const item = current,
    credentials = item && credential(item.id);
  if (!item || !credentials) return;
  const q = $("#followup-question").value.trim();
  if (q.length < 5) {
    $("#chat-status").textContent = "궁금한 내용을 5자 이상 적어주세요.";
    $("#followup-question").focus();
    return;
  }
  const button = formEl.querySelector("button[type=submit]");
  button.disabled = true;
  $("#chat-status").textContent =
    "앞서 나눈 이야기를 읽고 답하고 있어요. 잠시 기다려주세요.";
  try {
    const result = await apiClient.post(
      `/api/v2/readings/${encodeURIComponent(item.id)}/questions`,
      { question: q },
      { ...auth(credentials), timeoutMs: 250000 },
    );
    item.report.followups.push(result.answer);
    updateItem(item);
    if (current?.id !== item.id) {
      return;
    }
    renderChat();
    $("#followup-question").value = "";
    $("#chat-status").textContent = "답변이 도착했어요.";
    $("#chat-history").lastElementChild?.scrollIntoView({
      behavior: "smooth",
      block: "start",
    });
  } catch (error) {
    if (current?.id === item.id)
      $("#chat-status").textContent = safeMessage(error);
  } finally {
    if (current?.id === item.id) {
      button.disabled = (item.report.followups?.length || 0) >= 5;
    }
  }
}
function renderLibrary() {
  library = loadLibrary(localStorage);
  const items = [...library];
  if (active?.report && !items.some((x) => x.id === active.id))
    items.unshift(active);
  const pending =
    active?.token && !active.report
      ? '<div class="library-item"><div><h2>현재 탭의 풀이</h2><p>생성 상태를 확인하고 이어서 읽을 수 있어요.</p></div><a href="#loading" class="button secondary">진행 상황 보기</a></div>'
      : "";
  $("#library-list").innerHTML =
    pending +
    (items.length
      ? items
          .map((item) => {
            const r = item.report,
              isSaved = library.some((x) => x.id === item.id);
            return `<article class="library-item"><div class="library-symbol" aria-hidden="true">${e(r.profile.day_master.label.slice(0, 1))}</div><div><h2>${e(r.name)}님의 흐름</h2><p>${e(TOPICS[r.topic])} · ${e(r.generated_at)} · ${isSaved ? new Date(item.expiresAt).toLocaleDateString("ko-KR") + "까지 기기 보관" : "현재 탭에만 보관"}</p>${r.question ? `<p class="library-question">${e(r.question)}</p>` : ""}</div><div class="library-item-actions"><a href="#saved/${encodeURIComponent(item.id)}" class="button secondary">다시 읽기</a><button class="quiet-button" data-delete-id="${e(item.id)}">삭제</button></div></article>`;
          })
          .join("")
      : pending
        ? ""
        : `<div class="library-empty"><img src="./mark.svg" width="45" height="45" alt=""><h2>아직 접어둔 이야기가 없어요.</h2><p>풀이에서 ‘이 기기에 30일 보관’을 누르면<br>문장과 메모를 함께 다시 볼 수 있어요.</p><a href="#start" class="button primary">내 사주 기본 정보 보기</a><br><a href="#example" class="text-link">먼저 예시 읽어보기 ↗</a></div>`);
  show("library");
}
async function deleteItem(id) {
  const item = active?.id === id ? active : library.find((x) => x.id === id);
  if (!item) return;
  if (
    !(await dialog(
      "이 풀이를 지울까요?",
      credential(id)
        ? "현재 탭과 기기에 보관한 풀이·메모, 서버의 입력과 결과를 삭제해요. 삭제 후에는 되돌릴 수 없어요."
        : "이 기기에 보관한 풀이와 메모를 삭제해요. 서버 사본이 있다면 생성 요청 후 최대 24시간 안에 만료돼요.",
      "풀이 삭제",
    ))
  )
    return;
  try {
    if (credential(id)) {
      try {
        await apiClient.request(`/api/v1/tasks/${encodeURIComponent(id)}`, {
          method: "DELETE",
          ...auth(credential(id)),
        });
      } catch (error) {
        if (error.status !== 404) throw error;
      }
    }
    library = library.filter((x) => x.id !== id);
    if (!writeJSON(localStorage, LIBRARY_KEY, library))
      throw new Error(
        "이 기기의 저장소에 접근할 수 없어 삭제를 완료하지 못했어요. 브라우저 설정에서 사이트 데이터를 삭제해주세요.",
      );
    exampleDrafts.delete(id);
    if (active?.id === id) {
      active = null;
      clearTimeout(pollTimer);
      sessionStorage.removeItem(SESSION_KEY);
      form.reset();
      step = 1;
      selectTopic('self');
      $('#birth-time').disabled = false;
      $('#leap-label').classList.add('hidden');
      $('#concern-count').textContent = '0 / 600';
      $('#review-data').replaceChildren();
      $('#review-question').textContent = '';
    }
    access = access.filter((x) => x.id !== id);
    writeJSON(sessionStorage, ACCESS_KEY, access);
    if (current?.id === id) {
      current = null;
      $('#reader-view').replaceChildren();
      sessionStorage.removeItem('yeoul.last-reader');
    }
    toast("풀이와 메모를 삭제했어요.");
    if (location.hash === "#library") renderLibrary();
    else location.hash = "library";
  } catch (error) {
    toast("삭제를 완료하지 못했어요. " + safeMessage(error));
  }
}
async function fetchExampleReport(id = "example") {
  if (!isPublicExample(id)) throw new Error("알 수 없는 공개 예시예요.");
  const response = await fetch(PUBLIC_EXAMPLES[id].file, {
    cache: "no-store",
    credentials: "omit",
    referrerPolicy: "no-referrer",
  });
  if (!response.ok)
    throw new Error("예시 파일을 불러오지 못했어요. 잠시 후 다시 열어주세요.");
  return response.json();
}
async function loadExampleReading(id = "example") {
  if (current && isPublicExample(current.id)) exampleDrafts.set(current.id, current);
  const report = await fetchExampleReport(id);
  library = loadLibrary(localStorage);
  return restoreExampleReading(report, exampleDrafts.get(id), library, id);
}
async function renderProductPreviews() {
  await Promise.all(Object.entries(PUBLIC_EXAMPLES).map(async ([id, info]) => {
    const container = document.querySelector(`[data-product-example="${id}"]`);
    try {
      const report = await fetchExampleReport(id);
      const chapter = report.chapters.find(c => c.id === "question");
      const excerpt = report.product_excerpt || info.excerpt;
      if (!chapter || !excerpt || !chapter.paragraphs.some(p => p.includes(excerpt)))
        throw new Error("예시 내용을 확인하고 있어요.");
      container.innerHTML = `<p class="small-label">${e(info.label)} · 가상 인물 하루</p><h3>${id === "example" ? "다음 일로 옮기기 전에" : "도움이 되고 싶은 마음, 전하는 순서"}</h3><dl class="product-preview-steps"><div><dt>내 질문</dt><dd>${e(report.question)}</dd></div><div><dt>풀이 일부</dt><dd><blockquote>${e(excerpt)}</blockquote></dd></div><div><dt>작은 실천</dt><dd>${e(chapter.practice)}</dd></div></dl><a class="button secondary" href="#${id}">${e(info.label)} 8장 전체 읽기 <span aria-hidden="true">↗</span></a><p class="field-help">공개 예시 본문에서 발췌했어요. 실제 고객 후기가 아니에요.</p>`;
    } catch {
      container.innerHTML = `<h3>${e(info.label)} 예시</h3><p>미리보기를 불러오지 못했어요. 전체 예시를 다시 열어주세요.</p><a class="button secondary" href="#${id}">${e(info.label)} 8장 전체 읽기</a>`;
    }
  }));
}
async function route() {
  const hash = location.hash.slice(1) || "home";
  if (hash === 'main') { $('#main').focus(); return; }
  if (
    hash.startsWith("chapter-") ||
    ["reading-summary", "my-chart", "conversation", "my-notes"].includes(hash)
  ) {
    if (!current || $('#reader-view').classList.contains('hidden')) {
      const lastId = current?.id || readJSON(sessionStorage, 'yeoul.last-reader', active?.id);
      if (isPublicExample(lastId)) {
        try {
          const item = await loadExampleReading(lastId);
          if (location.hash.slice(1) !== hash) return;
          renderReader(item);
        } catch (error) {
          if (location.hash.slice(1) !== hash) return;
          show("home");
          toast(safeMessage(error));
          return;
        }
      } else {
        const item = current || (active?.id === lastId && active.report ? active : library.find(x=>x.id === lastId));
        if (item) renderReader(item);
        else {location.hash = 'home'; return;}
      }
    }
    const section = document.getElementById(hash);
    if (section) {
      section.tabIndex = -1;
      section.focus({ preventScroll: true });
      section.scrollIntoView();
    }
    return;
  }
  if (hash === "home") show("home");
  else if (hash === "start") {
    show("instant");
  } else if (hash === "compose") {
    const config = await apiClient.get("/api/v2/commerce/config").catch(() => null);
    if (location.hash.slice(1) !== hash) return;
    if (!config?.development_readings_enabled) { location.hash = "start"; return; }
    show("start");
    setStep(step);
  } else if (hash === "product") {
    show("product");
    await renderProductPreviews();
  }
  else if (hash === "privacy") show("privacy");
  else if (hash === "library") renderLibrary();
  else if (hash === "loading") {
    if (active?.report) {
      location.hash = "read";
      return;
    }
    if (!active) {
      location.hash = "start";
      return;
    }
    loading();
    poll();
  } else if (hash === "read") {
    if (active?.report) renderReader(active);
    else location.hash = active ? "loading" : "start";
  } else if (hash.startsWith("saved/")) {
    const id = decodeURIComponent(hash.slice(6));
    const item =
      active?.id === id && active.report
        ? active
        : library.find((x) => x.id === id);
    if (item) renderReader(item);
    else {
      toast("보관 기간이 지났거나 삭제된 풀이예요.");
      location.hash = "library";
    }
  } else if (isPublicExample(hash)) {
    try {
      const item = await loadExampleReading(hash);
      if (location.hash.slice(1) === hash)
        renderReader(item);
    } catch (error) {
      if (location.hash.slice(1) !== hash) return;
      show("home");
      toast(safeMessage(error));
    }
  } else location.hash = "home";
}
form.addEventListener("submit", (event) => {
  event.preventDefault();
  clearErrors();
  if (step === 1) {
    setStep(2);
    return;
  }
  const d = payload(),
    issues = validateBirth(d);
  if (Object.keys(issues).length) {
    if (step !== 2) setStep(2);
    errors(issues);
    return;
  }
  if (step === 2) {
    setStep(3);
    return;
  }
  if (!d.processing_consent || !d.age_confirmed) {
    errors({
      consent: "개인정보 처리 동의와 만 18세 이상 여부를 확인해주세요.",
    });
    return;
  }
  startReading();
});
$("#previous-step").addEventListener("click", () =>
  setStep(Math.max(1, step - 1)),
);
$("#concern").addEventListener(
  "input",
  () =>
    ($("#concern-count").textContent = `${$("#concern").value.length} / 600`),
);
$("#calendar").addEventListener("change", () => {
  const lunar = $("#calendar").value === "lunar";
  $("#leap-label").classList.toggle("hidden", !lunar);
  if (!lunar) form.elements.is_leap_month.checked = false;
});
$("#unknown-time").addEventListener("change", () => {
  $("#birth-time").disabled = $("#unknown-time").checked;
  if ($("#unknown-time").checked) $("#birth-time").value = "";
});
$("#cancel-reading").addEventListener(
  "click",
  () => active && deleteItem(active.id),
);
$("#retry-reading").addEventListener("click", () => {
  step = 2;
  location.hash = "compose";
});
document.addEventListener("submit", (event) => {
  if (event.target.id === "question-form") {
    event.preventDefault();
    askQuestion(event.target);
  }
});
document.addEventListener("input", (event) => {
  if (event.target.id === "reading-note" && current) {
    current.note = event.target.value;
    $(".print-note").textContent = current.note || "남긴 메모가 없어요.";
    updateItem();
    $("#note-status").textContent =
      library.some((x) => x.id === current.id)
        ? "이 기기에 메모를 저장했어요."
        : isPublicExample(current.id)
          ? "예시 메모는 이 화면에서만 유지돼요."
          : "현재 탭에 메모를 저장했어요.";
  }
});
document.addEventListener("click", async (event) => {
  const target = event.target.closest("button");
  if (!target) return;
  if (target.dataset.topic) {
    selectTopic(target.dataset.topic);
    return;
  }
  if (target.dataset.prompt) {
    selectTopic(target.dataset.promptTopic);
    $("#concern").value = target.dataset.prompt;
    $("#concern").dispatchEvent(new Event("input"));
    step = 1;
    location.hash = "start";
    return;
  }
  if (target.dataset.deleteId) {
    deleteItem(target.dataset.deleteId);
    return;
  }
  if (!current) return;
  if (target.dataset.bookmark) {
    const id = target.dataset.bookmark;
    current.favorites ??= [];
    current.favorites = current.favorites.includes(id)
      ? current.favorites.filter((x) => x !== id)
      : [...current.favorites, id];
    updateItem();
    target.setAttribute("aria-pressed", String(current.favorites.includes(id)));
    target.textContent = current.favorites.includes(id)
      ? "✓ 마음에 남긴 문장"
      : "♡ 이 장의 한 문장 남기기";
    renderFavorites();
    return;
  }
  if (target.dataset.followup) {
    $("#followup-question").value = target.dataset.followup;
    $("#followup-question").focus();
    return;
  }
  if (target.dataset.font) {
    const size =
      parseInt(
        getComputedStyle(document.documentElement).getPropertyValue(
          "--body-size",
        ),
      ) || 18;
    const next = Math.max(16, Math.min(22, size + Number(target.dataset.font)));
    document.documentElement.style.setProperty("--body-size", next + "px");
    writeJSON(sessionStorage, "yeoul.font", next);
    toast(`본문 글자 크기 ${next}px`);
    return;
  }
  if (target.id === "night-toggle") {
    const night = document.documentElement.classList.toggle("night");
    writeJSON(sessionStorage, "yeoul.night", night);
    target.setAttribute("aria-pressed", String(night));
    return;
  }
  if (target.id === "save-reading") {
    if (
      !(await dialog(
        "이 기기에 보관할까요?",
        "풀이에는 출생 정보와 개인적인 질문이 담겨 있어요. 이 브라우저에 30일 동안 저장하며, 공용 기기에서는 보관하지 않는 편이 좋아요.",
        "30일 보관하기",
      ))
    )
      return;
    try {
      saveLibrary(localStorage, current);
      library = loadLibrary(localStorage);
      target.textContent = "기기에 보관 중";
      $(".storage-note").textContent =
        "이 브라우저에 30일 동안 보관해요. 메모도 함께 저장돼요.";
      $("#note-status").textContent = "메모는 이 기기에 자동 저장돼요.";
      toast("이 기기에 풀이를 보관했어요.");
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  if (target.id === "delete-reading") {
    deleteItem(current.id);
    return;
  }
  if (target.id === "download-reading") {
    const blob = new Blob([readingText(current)], {
        type: "text/plain;charset=utf-8",
      }),
      url = URL.createObjectURL(blob),
      a = document.createElement("a");
    a.href = url;
    a.download = `여울-나의풀이-${current.report.generated_at}.txt`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    toast("개인적인 질문이 담긴 파일이에요. 안전한 곳에 보관해주세요.");
    return;
  }
  if (target.id === "print-reading") {
    window.print();
  }
});
const savedSize = readJSON(sessionStorage, "yeoul.font", 18);
document.documentElement.style.setProperty(
  "--body-size",
  Math.max(16, Math.min(22, Number(savedSize) || 18)) + "px",
);
const today = new Date();
$("#birth-date").max =
  `${today.getFullYear() - 18}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;
window.addEventListener("hashchange", () =>
  route().catch(() =>
    toast("화면을 열지 못했어요. 새로고침 후 다시 시도해주세요."),
  ),
);
window.addEventListener("storage", (event) => {
  if (event.key === LIBRARY_KEY) {
    library = loadLibrary(localStorage);
    if (location.hash === "#library") renderLibrary();
  }
});
initHomeMotion();
initFreeChart();
route();
if (
  active?.token &&
  !active.report &&
  active.status !== "failed" &&
  location.hash !== "#loading"
)
  poll();
