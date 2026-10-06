export const TOPICS = {
  self: "나 자신",
  career: "일과 진로",
  love: "연애와 관계",
  money: "돈과 생활",
  flow: "올해의 흐름",
};
export const PILLAR_LABELS = {
  year: "태어난 해 (연주)",
  month: "태어난 달 (월주)",
  day: "태어난 날 (일주)",
  time: "태어난 시간 (시주)",
};
export const ELEMENT_LABELS = {
  목: "나무 (목)", 화: "불 (화)", 토: "흙 (토)", 금: "금속 (금)", 수: "물 (수)",
};
export const POLICY = "2026-09-08";
export const SESSION_KEY = "yeoul.session.v2";
export const LIBRARY_KEY = "yeoul.library.v2";
export const PUBLIC_EXAMPLES = {
  example: { file: "./example.json", label: "진로 고민", excerpt: "내가 당연하게 여겼던 꼼꼼함이나 위기 대처 능력, 혹은 협업을 조율했던 방식이 사실은 다른 낯선 분야에서도 가장 절실하게 요구하는 기초 역량일 수 있습니다." },
  "example-relationship": { file: "./example-relationship.json", label: "관계 고민" },
};
export const isPublicExample = (id) => Object.hasOwn(PUBLIC_EXAMPLES, id);
const DAY = 86400000;
export const escapeHTML = (value = "") =>
  String(value).replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
export function readJSON(storage, key, fallback) {
  try {
    return JSON.parse(storage.getItem(key)) ?? fallback;
  } catch {
    return fallback;
  }
}
export function writeJSON(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}
export function loadLibrary(storage, now = Date.now()) {
  const items = readJSON(storage, LIBRARY_KEY, []);
  if (!Array.isArray(items)) return [];
  const valid = items
    .filter((x) => x && x.id && x.report?.version === 2 && x.expiresAt > now)
    .slice(0, 12);
  writeJSON(storage, LIBRARY_KEY, valid);
  return valid;
}
export function saveLibrary(storage, item, now = Date.now()) {
  const items = loadLibrary(storage, now).filter((x) => x.id !== item.id);
  if (items.length >= 12)
    throw new Error(
      "서랍에는 최대 12개의 풀이를 보관할 수 있어요. 먼저 한 개를 지워주세요.",
    );
  // Bearer tokens and raw form inputs are never put in persistent storage.
  const safe = {
    id: item.id,
    report: item.report,
    note: item.note || "",
    favorites: item.favorites || [],
    savedAt: now,
    expiresAt: now + 30 * DAY,
  };
  if (!writeJSON(storage, LIBRARY_KEY, [safe, ...items]))
    throw new Error(
      "기기 저장 공간을 사용할 수 없어요. 텍스트로 내려받아 보관해주세요.",
    );
  return safe;
}
export function restoreExampleReading(report, current, library = [], id = "example") {
  if (!isPublicExample(id)) throw new Error("알 수 없는 공개 예시예요.");
  const previous =
    library.find((item) => item.id === id) ||
    (current?.id === id ? current : null);
  const chapterIds = new Set(report.chapters.map((chapter) => chapter.id));
  return {
    id,
    report,
    note: typeof previous?.note === "string" ? previous.note : "",
    favorites: Array.isArray(previous?.favorites)
      ? previous.favorites.filter((id) => chapterIds.has(id))
      : [],
  };
}
export function ageOn(birth, today = new Date()) {
  const parts = String(birth).split("-").map(Number),
    [y, m, d] = parts;
  const parsed = new Date(Date.UTC(y, m - 1, d));
  if (
    !y ||
    parsed.getUTCFullYear() !== y ||
    parsed.getUTCMonth() !== m - 1 ||
    parsed.getUTCDate() !== d
  )
    return -1;
  return (
    today.getFullYear() -
    y -
    (today.getMonth() + 1 < m ||
    (today.getMonth() + 1 === m && today.getDate() < d)
      ? 1
      : 0)
  );
}
export function validateBirth(data, today = new Date()) {
  const errors = {};
  if (!data.name?.trim()) errors.name = "불러드릴 이름이나 별명을 적어주세요.";
  const age = ageOn(data.birth_date, today);
  if (age < 18 || Number(data.birth_date?.slice(0, 4)) < 1900)
    errors.birth_date =
      "1900년 이후 출생한 만 18세 이상의 생년월일을 입력해주세요.";
  if (
    !data.birth_time_unknown &&
    !/^([01]\d|2[0-3]):[0-5]\d$/.test(data.birth_time || "")
  )
    errors.birth_time =
      "태어난 시간을 입력하거나 ‘시간을 몰라요’를 선택해주세요.";
  if (!["male", "female"].includes(data.gender))
    errors.gender = "사주에서 긴 기간의 흐름을 계산하는 데 사용할 출생 시 성별을 선택해주세요.";
  if (!["solar", "lunar"].includes(data.calendar_type))
    errors.calendar_type = "양력 또는 음력을 선택해주세요.";
  return errors;
}
export function readingText(item) {
  const r = item.report;
  return [
    `여울 · ${r.name}님의 사주`,
    `${r.generated_at} 기준 · ${TOPICS[r.topic] || "나 자신"}`,
    r.question ? `나의 질문: ${r.question}` : "",
    "사주는 전통 해석을 통한 자기 이해의 참고자료입니다. 미래를 확정하거나 중요한 판단을 대신하지 않습니다.",
    ...r.chapters.flatMap((c) => [
      "",
      c.category,
      c.title,
      c.lead,
      ...c.paragraphs,
      `생각해볼 질문: ${c.reflection}`,
      `작은 시도: ${c.practice}`,
      ...c.basis.map((id) => {
        const f = r.facts.find((f) => f.id === id);
        return f ? `해석 근거 — ${f.label}: ${f.text}` : "";
      }),
    ]),
    ...(r.followups || []).flatMap((a) => [
      "",
      `이어서 묻기: ${a.question}`,
      ...a.paragraphs,
      a.reflection,
    ]),
    "",
    `내가 남긴 메모: ${item.note || "없음"}`,
    "마음에 남긴 문장:",
    ...r.chapters
      .filter((c) => item.favorites?.includes(c.id))
      .map((c) => c.lead),
  ]
    .filter(Boolean)
    .join("\n\n");
}
export const ACCESS_KEY = "yeoul.access.v2";
export function loadAccess(storage, now = Date.now()) {
  const value = readJSON(storage, ACCESS_KEY, []);
  const items = Array.isArray(value)
    ? value
        .filter(
          (x) =>
            typeof x?.id === "string" &&
            typeof x.token === "string" &&
            x.createdAt <= now &&
            x.createdAt + DAY > now,
        )
        .slice(-200)
    : [];
  writeJSON(storage, ACCESS_KEY, items);
  return items;
}
export function rememberAccess(storage, item, now = Date.now()) {
  const items = loadAccess(storage, now).filter((x) => x.id !== item.id);
  return writeJSON(storage, ACCESS_KEY, [
    ...items,
    { id: item.id, token: item.token, createdAt: item.createdAt },
  ]);
}
