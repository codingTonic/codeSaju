import { apiClient } from "../assets/js/api.js";
import { escapeHTML as e, POLICY, PILLAR_LABELS, ELEMENT_LABELS } from "./domain.js";

export function chartPayload(form) {
  const data = new FormData(form);
  const rawDate = String(data.get("birth_date") || "").trim();
  return {
    birth_date: /^\d{8}$/.test(rawDate)
      ? `${rawDate.slice(0, 4)}-${rawDate.slice(4, 6)}-${rawDate.slice(6)}` : rawDate,
    calendar_type: data.get("calendar_type"),
    is_leap_month: data.get("calendar_type") === "lunar" && data.has("is_leap_month"),
    birth_time: data.has("birth_time_unknown") ? null : data.get("birth_time"),
    birth_time_unknown: data.has("birth_time_unknown"),
    processing_consent: data.has("processing_consent"),
    age_confirmed: data.has("age_confirmed"),
    privacy_policy_version: POLICY,
  };
}

export function chartIssues(data) {
  const issues = [];
  if (!/^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$/.test(data.birth_date))
    issues.push({ field: "birth_date", message: "생년월일을 1990-05-15 또는 19900515 형식으로 입력해주세요." });
  if (!data.birth_time_unknown && !/^([01]\d|2[0-3]):[0-5]\d$/.test(data.birth_time || ""))
    issues.push({ field: "birth_time", message: "태어난 시간을 입력하거나 ‘시간을 몰라요’를 선택해주세요." });
  if (!data.processing_consent)
    issues.push({ field: "processing_consent", message: "사주 기본 정보 계산을 위한 출생 정보 처리에 동의해주세요." });
  if (!data.age_confirmed)
    issues.push({ field: "age_confirmed", message: "만 18세 이상 여부를 확인해주세요." });
  // Exact lunar dates (including February 30), leap months and age are validated by the server.
  return issues;
}

export function validateChart(data) {
  return chartIssues(data)[0]?.message || "";
}

export function chartHTML(data) {
  const p = data.profile;
  const pillars = ["year", "month", "day", "time"].map(key => p.pillars.find(x => x.key === key));
  const values = (field) => pillars.map(x => `<td>${x ? e(x[field] || "—") : "미상"}</td>`).join("");
  const hidden = pillars.map(x => `<td>${x ? (x.hidden_stems || []).map(h => e(`${h.stem || h.gan || ""} ${h.ten_god || ""}`)).join("<br>") : "미상"}</td>`).join("");
  return `<div class="instant-result-heading"><p class="small-label">내 사주의 출발점</p><h2 id="instant-result-title" tabindex="-1">나의 사주 기본 정보</h2><p>태어난 해·달·날·시간을 글자로 나타낸 사주 표예요. 이 표를 ‘원국’ 또는 ‘명식’이라고 해요.</p></div>
    <div class="pillar-grid">${pillars.map((x, i) => `<div class="pillar"><span>${Object.values(PILLAR_LABELS)[i]}${x?.estimated ? " · 추정" : ""}</span><b>${x ? e(x.gan_zhi_ko) : "?"}</b><small>${x ? e(x.gan_zhi) : "시간 미상"}</small></div>`).join("")}</div>
    ${p.uncertain_pillars?.length ? '<p class="error-summary">계절의 기준이 바뀌는 날(절기)에 태어났고 시간을 몰라, 표시한 해·달의 글자는 낮 12시를 기준으로 예상한 값이에요. 다섯 요소의 개수와 글자 사이의 관계도 태어난 시간에 따라 달라질 수 있어요.</p>' : ""}
    <p>나를 나타내는 기준 글자: <strong>${e(p.day_master.label)}</strong>. 태어난 날의 윗글자를 ‘일간’이라고 해요.</p><p>${e(p.day_master.archetype || "")}</p>
    <h3>사주를 이루는 다섯 요소</h3><p>나무·불·흙·금속·물을 ‘오행’이라고 해요. 사주 표의 글자가 각 요소에 몇 개씩 해당하는지 보여드려요.</p><div class="instant-elements">${Object.entries(p.element_counts).map(([key, count]) => `<div><span>${e(ELEMENT_LABELS[key] || key)}</span><meter min="0" max="${p.element_count_total}" value="${Number(count)}" aria-label="${e(ELEMENT_LABELS[key] || key)} ${Number(count)}자"></meter><b>${Number(count)}자</b></div>`).join("")}</div>
    <p class="field-help">표에 보이는 글자만 세었어요. 숨은 글자는 더하지 않으며, 개수가 적다고 성격이나 능력이 부족하다는 뜻은 아니에요.</p>
    <details class="basis"><summary>글자 사이의 관계 자세히 보기 (십성)</summary><p>나를 나타내는 글자를 기준으로 다른 글자와의 관계를 열 가지로 나눈 이름이 ‘십성’이에요. 비견·정관 같은 이름은 관계를 구분하는 말이며, 좋고 나쁨의 점수가 아니에요.</p><p>윗글자는 ‘천간’, 아랫글자는 ‘지지’라고 해요. 아래 표는 각 위치의 관계 이름을 보여줘요.</p><div class="instant-table-wrap"><table class="instant-table"><caption class="sr-only">태어난 해·달·날·시간별 글자 사이의 관계 이름</caption><thead><tr><th scope="col">구분</th>${["태어난 해", "태어난 달", "태어난 날", "태어난 시간"].map(x => `<th scope="col">${x}</th>`).join("")}</tr></thead><tbody><tr><th scope="row">윗글자<br>(천간)</th>${values("stem_ten_god")}</tr><tr><th scope="row">아랫글자의 중심<br>(지지 본기)</th>${values("branch_main_ten_god")}</tr><tr><th scope="row">아랫글자에 담긴 글자<br>(지장간)</th>${hidden}</tr></tbody></table></div></details>
    <details class="basis"><summary>어떻게 계산했나요?</summary><p>아래는 계산 방법과 더 자세한 확인이 필요한 부분이에요.</p><p>${e(data.method.engine)} ${e(data.method.engine_version || "")} · ${e(data.method.timezone)}</p><p>${e(data.method.day_boundary)}</p><p>${e(p.element_note)}</p>${(data.method.limitations || []).map(x => `<p>${e(x)}</p>`).join("")}<p>균형을 살피는 요소(용신): ${e(data.yongshin.reason)}</p><p>특정 글자 조합에 붙이는 해석(신살): ${e(data.shinsal.reason)}</p></details>
    <p class="field-help">사주는 전통적인 해석의 참고자료예요. 글자 수로 성격이나 미래를 확정할 수는 없어요.</p>`;
}

export function initFreeChart() {
  const form = document.querySelector("#instant-form");
  if (!form) return;
  const error = document.querySelector("#instant-error");
  const result = document.querySelector("#instant-result");
  const submit = document.querySelector("#instant-submit");
  let revision = 0;
  let busy = false;
  const config = apiClient.get("/api/v2/commerce/config").then(data => {
    document.querySelector("#development-reading-link").hidden = !data.development_readings_enabled;
    return data;
  }).catch(() => null);
  form.addEventListener("input", () => {
    revision += 1;
    result.classList.add("hidden");
    result.replaceChildren();
    document.querySelector("#instant-success").textContent = "";
    const invalidFields = new Set(chartIssues(chartPayload(form)).map(issue => issue.field));
    clearErrors(invalidFields);
  });
  form.elements.calendar_type.addEventListener("change", () => {
    const lunar = form.elements.calendar_type.value === "lunar";
    document.querySelector("#instant-leap-label").hidden = !lunar;
    if (!lunar) form.elements.is_leap_month.checked = false;
  });
  form.elements.birth_time_unknown.addEventListener("change", () => {
    form.elements.birth_time.disabled = form.elements.birth_time_unknown.checked;
    if (form.elements.birth_time_unknown.checked) form.elements.birth_time.value = "";
  });
  function clearErrors(preserveFields = new Set()) {
    for (const message of form.querySelectorAll("[data-chart-error]")) {
      if (preserveFields.has(message.dataset.chartError)) continue;
      const field = form.elements[message.dataset.chartError];
      const describedBy = (field.getAttribute("aria-describedby") || "").split(/\s+/).filter(id => id && id !== message.id);
      if (describedBy.length) field.setAttribute("aria-describedby", describedBy.join(" "));
      else field.removeAttribute("aria-describedby");
      field.removeAttribute("aria-invalid");
      error.querySelector(`[data-chart-error-summary="${message.dataset.chartError}"]`)?.remove();
      message.remove();
    }
    if (form.querySelector("[data-chart-error]")) return;
    error.classList.add("hidden");
    error.replaceChildren();
  }
  function showError(message, issues = []) {
    clearErrors();
    error.textContent = message;
    if (issues.length) {
      const list = document.createElement("ul");
      for (const issue of issues) {
        const field = form.elements[issue.field];
        const hint = document.createElement("p");
        hint.id = `${field.id}-error`;
        hint.dataset.chartError = issue.field;
        hint.className = "instant-field-error";
        hint.textContent = issue.message;
        (field.closest(".check-label") || field).after(hint);
        field.setAttribute("aria-invalid", "true");
        field.setAttribute("aria-describedby", [field.getAttribute("aria-describedby"), hint.id].filter(Boolean).join(" "));
        const link = document.createElement("a");
        link.href = `#${field.id}`;
        link.textContent = issue.message;
        link.addEventListener("click", event => { event.preventDefault(); field.focus(); });
        const item = document.createElement("li");
        item.dataset.chartErrorSummary = issue.field;
        item.append(link);
        list.append(item);
      }
      error.append(list);
    }
    error.classList.remove("hidden");
    error.focus();
  }
  form.addEventListener("submit", async event => {
    event.preventDefault();
    if (busy) return;
    const data = chartPayload(form), issues = chartIssues(data);
    if (issues.length) { showError("입력 내용을 확인해주세요.", issues); return; }
    clearErrors();
    busy = true;
    const submittedRevision = revision;
    submit.disabled = true;
    submit.textContent = "사주 기본 정보를 계산하고 있어요…";
    result.setAttribute("aria-busy", "true");
    try {
      const response = await apiClient.post("/api/v2/chart", data, { timeoutMs: 15000 });
      if (submittedRevision !== revision) return;
      result.innerHTML = chartHTML(response);
      result.classList.remove("hidden");
      document.querySelector("#instant-success").textContent = "사주 기본 정보를 확인했어요.";
      document.querySelector("#instant-result-title").focus();
      result.scrollIntoView({ behavior: "instant", block: "start" });
    } catch (err) {
      if (submittedRevision === revision) showError(err.getUserMessage?.() || err.message || "계산을 마치지 못했어요. 입력 정보와 연결 상태를 확인해주세요.");
    } finally {
      busy = false;
      submit.disabled = false;
      submit.textContent = "내 사주 기본 정보 보기";
      result.removeAttribute("aria-busy");
    }
  });
  return { config };
}
