import test from 'node:test';
import assert from 'node:assert/strict';
import { initFreeChart } from '../frontend/app/free-chart.js';
import { apiClient } from '../frontend/assets/js/api.js';

// A small DOM/event fixture follows home-motion.test.js; no browser or API dependency.
class Element {
  constructor(doc, tagName = 'div') {
    this.doc = doc;
    this.tagName = tagName;
    this.attributes = new Map();
    this.dataset = {};
    this.children = [];
    this.listeners = new Map();
    this.value = '';
    this.checked = false;
    this.disabled = false;
    this.text = '';
    const classes = new Set();
    this.classList = {
      add: name => classes.add(name),
      remove: name => classes.delete(name),
      contains: name => classes.has(name),
    };
  }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.get(key) ?? null; }
  removeAttribute(key) { this.attributes.delete(key); }
  append(...nodes) {
    for (const node of nodes) {
      node.parentElement = this;
      this.children.push(node);
    }
  }
  replaceChildren(...nodes) {
    for (const child of this.children) child.parentElement = null;
    this.children = [];
    this.text = '';
    this.append(...nodes);
  }
  set textContent(value) { this.replaceChildren(); this.text = value; }
  get textContent() { return this.text + this.children.map(node => node.textContent).join(''); }
  after(node) {
    const parent = this.parentElement;
    node.parentElement = parent;
    parent.children.splice(parent.children.indexOf(this) + 1, 0, node);
  }
  remove() {
    const parent = this.parentElement;
    if (parent) parent.children.splice(parent.children.indexOf(this), 1);
    this.parentElement = null;
  }
  closest(selector) {
    if (selector === '.check-label' && this.classList.contains('check-label')) return this;
    return this.parentElement?.closest(selector) || null;
  }
  querySelectorAll(selector) {
    const data = selector.match(/^\[data-([\w-]+)(?:="([^"]+)")?\]$/);
    const key = data?.[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
    const matches = node => data
      ? Object.hasOwn(node.dataset, key) && (data[2] === undefined || node.dataset[key] === data[2])
      : node.tagName === selector;
    return this.children.flatMap(node => [
      ...(matches(node) ? [node] : []), ...node.querySelectorAll(selector),
    ]);
  }
  querySelector(selector) { return this.querySelectorAll(selector)[0] || null; }
  addEventListener(type, listener) {
    const listeners = this.listeners.get(type) || [];
    listeners.push(listener);
    this.listeners.set(type, listeners);
  }
  async emit(type, target = this) {
    const event = { target, preventDefault() { this.defaultPrevented = true; } };
    await Promise.all((this.listeners.get(type) || []).map(listener => listener(event)));
    return event;
  }
  focus() { this.doc.activeElement = this; }
  scrollIntoView() {}
}

async function formFixture(t) {
  const previousDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
  const previousFormData = globalThis.FormData;
  const doc = { activeElement: null };
  doc.createElement = tag => new Element(doc, tag);
  const nodes = Object.fromEntries([
    'instant-form', 'instant-error', 'instant-result', 'instant-submit',
    'instant-success', 'instant-leap-label', 'development-reading-link', 'instant-result-title',
  ].map(id => {
    const node = doc.createElement(id === 'instant-form' ? 'form' : 'div');
    node.id = id;
    return [id, node];
  }));
  doc.querySelector = selector => nodes[selector.slice(1)] || null;
  const form = nodes['instant-form'];
  const error = nodes['instant-error'];
  error.classList.add('hidden');
  nodes['instant-result'].classList.add('hidden');
  form.append(error);
  form.elements = {};
  const fields = [
    ['birth_date', 'instant-birth', 'text', 'instant-date-help'],
    ['calendar_type', 'instant-calendar', 'select'],
    ['is_leap_month', '', 'checkbox'],
    ['birth_time', 'instant-time', 'time', 'instant-time-help'],
    ['birth_time_unknown', '', 'checkbox'],
    ['processing_consent', 'instant-processing-consent', 'checkbox'],
    ['age_confirmed', 'instant-age-confirmed', 'checkbox'],
  ];
  for (const [name, id, type, help] of fields) {
    const field = doc.createElement(type === 'select' ? 'select' : 'input');
    Object.assign(field, { name, id, type });
    if (help) field.setAttribute('aria-describedby', help);
    form.elements[name] = field;
    if (type === 'checkbox') {
      const label = doc.createElement('label');
      label.classList.add('check-label');
      label.append(field);
      form.append(label);
    } else form.append(field);
  }
  form.elements.calendar_type.value = 'solar';
  globalThis.document = doc;
  globalThis.FormData = class {
    constructor(formElement) {
      this.values = new Map(Object.values(formElement.elements)
        .filter(field => !field.disabled && (field.type !== 'checkbox' || field.checked))
        .map(field => [field.name, field.value || (field.type === 'checkbox' ? 'on' : '')]));
    }
    get(name) { return this.values.get(name) ?? null; }
    has(name) { return this.values.has(name); }
  };
  t.after(() => {
    if (previousDocument) Object.defineProperty(globalThis, 'document', previousDocument);
    else delete globalThis.document;
    globalThis.FormData = previousFormData;
  });
  t.mock.method(apiClient, 'get', async () => ({ development_readings_enabled: false }));
  const requests = [];
  t.mock.method(apiClient, 'post', (url, data) => new Promise((resolve, reject) => {
    requests.push({ url, data, resolve, reject });
  }));
  await initFreeChart().config;
  return {
    doc, form, error, nodes, requests,
    errors: () => form.querySelectorAll('[data-chart-error]').map(node => node.dataset.chartError),
    summaries: () => error.querySelectorAll('a').map(link =>
      Object.values(form.elements).find(field => `#${field.id}` === link.href)?.name),
    submit: () => form.emit('submit'),
    async edit(name, value) {
      const field = form.elements[name];
      field.focus();
      if (field.type === 'checkbox') field.checked = value;
      else field.value = value;
      // Browser checkbox input bubbles before its change event.
      await form.emit('input', field);
      if (field.type === 'checkbox' || field.type === 'select') await field.emit('change');
    },
  };
}

const missingFields = ['birth_date', 'birth_time', 'processing_consent', 'age_confirmed'];

test('blank submit shows four linked errors, and a partial date edit keeps all errors and focus', async t => {
  const f = await formFixture(t);
  await f.submit();
  assert.deepEqual(f.errors(), missingFields);
  assert.deepEqual(f.summaries(), missingFields);
  assert.equal(f.doc.activeElement, f.error);
  const originalHints = f.form.querySelectorAll('[data-chart-error]');

  await f.edit('birth_date', '199');
  assert.deepEqual(f.errors(), missingFields);
  assert.deepEqual(f.summaries(), missingFields);
  assert.deepEqual(f.form.querySelectorAll('[data-chart-error]'), originalHints);
  assert.equal(f.form.elements.birth_date.getAttribute('aria-invalid'), 'true');
  assert.equal(f.form.elements.birth_date.getAttribute('aria-describedby'), 'instant-date-help instant-birth-error');
  assert.equal(f.doc.activeElement, f.form.elements.birth_date);
  assert.equal(f.requests.length, 0);
});

test('a corrected date clears only its error, preserves help and other errors, and keeps summary links usable', async t => {
  const f = await formFixture(t);
  await f.submit();
  const timeHint = f.form.querySelector('[data-chart-error="birth_time"]');
  await f.edit('birth_date', '19900515');
  assert.deepEqual(f.errors(), missingFields.slice(1));
  assert.deepEqual(f.summaries(), missingFields.slice(1));
  assert.equal(f.form.querySelector('[data-chart-error="birth_time"]'), timeHint);
  assert.equal(f.error.classList.contains('hidden'), false);
  assert.equal(f.form.elements.birth_date.getAttribute('aria-invalid'), null);
  assert.equal(f.form.elements.birth_date.getAttribute('aria-describedby'), 'instant-date-help');
  assert.equal(f.form.elements.birth_time.getAttribute('aria-describedby'), 'instant-time-help instant-time-error');
  assert.equal(f.doc.activeElement, f.form.elements.birth_date);
  const link = f.error.querySelectorAll('a').find(node => node.href === '#instant-time');
  const click = await link.emit('click');
  assert.equal(click.defaultPrevented, true);
  assert.equal(f.doc.activeElement, f.form.elements.birth_time);
});

test('unknown time resolves its dependent error and correcting the remaining fields hides the summary', async t => {
  const f = await formFixture(t);
  await f.submit();
  await f.edit('birth_time_unknown', true);
  assert.deepEqual(f.errors(), ['birth_date', 'processing_consent', 'age_confirmed']);
  assert.deepEqual(f.summaries(), f.errors());
  assert.equal(f.form.elements.birth_time.disabled, true);
  assert.equal(f.form.elements.birth_time.getAttribute('aria-invalid'), null);
  assert.equal(f.form.elements.birth_time.getAttribute('aria-describedby'), 'instant-time-help');
  assert.equal(f.doc.activeElement, f.form.elements.birth_time_unknown);
  await f.edit('birth_date', '1990-05-15');
  await f.edit('processing_consent', true);
  await f.edit('age_confirmed', true);
  assert.deepEqual(f.errors(), []);
  assert.deepEqual(f.summaries(), []);
  assert.equal(f.error.classList.contains('hidden'), true);
  assert.equal(f.error.textContent, '');
  assert.equal(f.doc.activeElement, f.form.elements.age_confirmed);
  assert.equal(f.form.elements.age_confirmed.getAttribute('aria-describedby'), null);
});

test('resubmission revalidates corrected fields and an unchecked unknown-time option', async t => {
  const f = await formFixture(t);
  await f.submit();
  await f.edit('birth_date', '1990-05-15');
  await f.edit('birth_time_unknown', true);
  await f.edit('birth_date', '199');
  await f.edit('birth_time_unknown', false);
  await f.submit();
  assert.deepEqual(f.errors(), missingFields);
  assert.deepEqual(f.summaries(), missingFields);
  assert.equal(f.form.elements.birth_time.disabled, false);
  assert.equal(f.form.elements.birth_date.getAttribute('aria-describedby'), 'instant-date-help instant-birth-error');
  assert.equal(f.doc.activeElement, f.error);
  assert.equal(f.requests.length, 0);
});

for (const outcome of ['resolve', 'reject']) {
  test(`an edited pending request cannot display a stale ${outcome === 'resolve' ? 'result' : 'error'}`, async t => {
    const f = await formFixture(t);
    await f.edit('birth_date', '1990-05-15');
    await f.edit('birth_time_unknown', true);
    await f.edit('processing_consent', true);
    await f.edit('age_confirmed', true);
    const pendingSubmit = f.submit();
    assert.equal(f.requests.length, 1);
    assert.equal(f.nodes['instant-submit'].disabled, true);
    assert.equal(f.nodes['instant-result'].getAttribute('aria-busy'), 'true');
    await f.edit('birth_date', '1991-05-15');
    if (outcome === 'resolve') f.requests[0].resolve({}); // Must be ignored before rendering.
    else f.requests[0].reject(new Error('이전 요청의 오류'));
    await pendingSubmit;
    assert.equal(f.nodes['instant-result'].classList.contains('hidden'), true);
    assert.equal(f.nodes['instant-success'].textContent, '');
    assert.equal(f.error.classList.contains('hidden'), true);
    assert.equal(f.nodes['instant-submit'].disabled, false);
    assert.equal(f.nodes['instant-result'].getAttribute('aria-busy'), null);
    assert.equal(f.doc.activeElement, f.form.elements.birth_date);
  });
}
