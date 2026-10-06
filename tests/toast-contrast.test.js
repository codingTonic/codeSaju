import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const css = readFileSync(new URL('../frontend/app/styles.css', import.meta.url), 'utf8');

function declarations(selector) {
  const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const body = css.match(new RegExp(`(?:^|\\n)${escaped}\\s*\\{([^}]+)\\}`))?.[1];
  assert.ok(body, `Missing ${selector} rule`);
  return Object.fromEntries([...body.matchAll(/([\w-]+)\s*:\s*([^;]+);/g)]
    .map(([, property, value]) => [property, value.trim()]));
}

function luminance(value, variables) {
  const substituted = value.replace(/var\((--[\w-]+)\)/g, (_, key) => variables[key]);
  const resolved = substituted === 'white' ? '#fff' : substituted;
  assert.match(resolved, /^#[\da-f]{3}(?:[\da-f]{3})?$/i);
  const hex = resolved.length === 4
    ? [...resolved.slice(1)].map(char => char + char).join('')
    : resolved.slice(1);
  const channels = hex.match(/../g).map(channel => {
    const component = parseInt(channel, 16) / 255;
    return component <= 0.04045 ? component / 12.92 : ((component + 0.055) / 1.055) ** 2.4;
  });
  return channels[0] * 0.2126 + channels[1] * 0.7152 + channels[2] * 0.0722;
}

for (const theme of ['light', 'night']) {
  test(`${theme} toast status text meets 4.5:1 contrast`, () => {
    const variables = { ...declarations(':root'), ...(theme === 'night' ? declarations('.night') : {}) };
    const toast = declarations('.toast');
    const foreground = luminance(toast.color, variables);
    const background = luminance(toast.background, variables);
    const contrast = (Math.max(foreground, background) + 0.05) / (Math.min(foreground, background) + 0.05);
    assert.ok(contrast >= 4.5, `${theme} contrast is ${contrast.toFixed(2)}:1`);
  });
}
