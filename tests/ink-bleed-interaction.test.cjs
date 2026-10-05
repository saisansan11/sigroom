const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/ink_bleed.js', 'utf8');

function makeElement(tag) {
  const el = {
    tagName: tag.toUpperCase(),
    children: [],
    parentNode: null,
    style: {},
    attrs: {},
    className: '',
    setAttribute(key, value) { el.attrs[key] = String(value); },
    getAttribute(key) { return key in el.attrs ? el.attrs[key] : null; },
    appendChild(child) { child.parentNode = el; el.children.push(child); return child; },
    removeChild(child) { el.children = el.children.filter(item => item !== child); child.parentNode = null; },
    remove() { if (el.parentNode) el.parentNode.removeChild(el); },
    closest() { return el.interactive ? el : null; },
    getBoundingClientRect() { return el.rect || { left: 10, top: 20, width: 120, height: 44 }; },
    getContext(type) {
      if (type !== '2d') return null;
      el.draws = 0;
      return {
        setTransform() {}, clearRect() {}, beginPath() {}, fill() {},
        arc() { el.draws += 1; },
        createRadialGradient() { return { addColorStop() {} }; },
      };
    },
  };
  return el;
}

function setup({ ink = null, reducedMotion = false, background = 'rgb(251, 248, 240)' } = {}) {
  const listeners = {};
  const timers = [];
  const frames = [];
  let clock = 1000;
  const body = makeElement('body');
  if (ink !== null) body.setAttribute('data-ink', ink);
  const media = { matches: reducedMotion, addEventListener(_, fn) { media.listener = fn; }, removeEventListener() {} };
  const document = {
    hidden: false,
    readyState: 'complete',
    body,
    createElement: makeElement,
    addEventListener(name, fn) { (listeners[name] = listeners[name] || []).push(fn); },
    removeEventListener(name, fn) { listeners[name] = (listeners[name] || []).filter(item => item !== fn); },
  };
  const window = {
    innerWidth: 1280, innerHeight: 800, devicePixelRatio: 2,
    matchMedia: () => media,
    getComputedStyle: () => ({ backgroundColor: background, borderRadius: '2px' }),
    addEventListener() {}, removeEventListener() {},
  };
  const context = {
    window, document, module: { exports: {} }, Math,
    performance: { now: () => clock },
    setTimeout(fn, ms) { timers.push({ fn, ms }); return timers.length; },
    clearTimeout(id) { if (timers[id - 1]) timers[id - 1].cleared = true; },
    requestAnimationFrame(fn) { frames.push(fn); return frames.length; },
    cancelAnimationFrame() {},
  };
  vm.runInNewContext(source, context);
  const fire = (name, event) => (listeners[name] || []).forEach(fn => fn(event));
  return {
    ink: context.module.exports, body, document, media, timers, frames, fire,
    advance(ms) { clock += ms; },
    move(x, y, pointerType = 'mouse') { fire('pointermove', { clientX: x, clientY: y, pointerType }); },
  };
}

const canvasOf = env => env.body.children.find(child => child.className === 'ink-bleed-canvas');
const soaksOf = env => env.body.children.filter(child => child.className.startsWith('ink-soak'));

test('เปิดทุกหน้าโดยปริยาย และปิดได้ด้วย data-ink="off"', () => {
  assert.ok(canvasOf(setup()));
  assert.ok(canvasOf(setup({ ink: 'on' })));
  const off = setup({ ink: 'off' });
  assert.equal(canvasOf(off), undefined);
  assert.equal(off.ink.getState().isInitialized, false);
});

test('ลากเมาส์แล้วเกิดรอยสีน้ำต่อเนื่องและเปลี่ยนสีตามระยะทาง', () => {
  const env = setup();
  env.move(100, 100);
  assert.equal(env.ink.getState().lobeCount, 0, 'จุดแรกใช้ตั้งต้นเท่านั้น');
  for (let x = 120; x <= 1100; x += 20) env.move(x, 100);
  const state = env.ink.getState();
  assert.ok(state.lobeCount > 30);
  assert.ok(new Set(state.lobeColors).size >= 4, 'ต้องมีหลายสี ไม่ใช่สีเดียว');
  assert.ok(env.frames.length >= 1, 'ต้องเริ่มวาด');
});

test('จำนวนหยดไม่เกินเพดาน และจางหายเองจน canvas ว่าง', () => {
  const env = setup();
  env.move(0, 0);
  for (let i = 1; i <= 400; i += 1) env.move((i * 37) % 1200, (i * 53) % 700);
  assert.ok(env.ink.getState().lobeCount <= env.ink.getState().maxLobes);
  env.advance(5000);
  env.ink.renderLoop(6000);
  assert.equal(env.ink.getState().lobeCount, 0);
});

test('พื้นเข้มใช้ชั้นสีสว่างแยกจากชั้นสีน้ำบนกระดาษ', () => {
  const env = setup({ background: 'rgb(31, 42, 36)' });
  assert.ok(env.body.children.some(child => child.className === 'ink-bleed-canvas ink-bleed-canvas--glow'));
  env.document.elementFromPoint = () => makeElement('section');
  env.move(0, 0);
  env.move(300, 0);
  const state = env.ink.getState();
  assert.ok(state.lobeCount > 0);
  assert.equal(state.darkLobeCount, state.lobeCount);
});

test('นิ้วและปากกาไม่ทำให้เกิดรอยตามเมาส์', () => {
  const env = setup();
  for (let x = 0; x < 600; x += 30) env.move(x, 50, 'touch');
  for (let x = 0; x < 600; x += 30) env.move(x, 50, 'pen');
  assert.equal(env.ink.getState().lobeCount, 0);
});

test('กดปุ่มแล้วหมึก 4 สีซึมเข้าปุ่มโดยไม่ขวางการกด แล้วลบตัวเองออก', () => {
  const env = setup();
  const button = makeElement('button');
  button.interactive = true;
  let prevented = false;
  env.fire('pointerdown', { target: button, clientX: 60, clientY: 40, button: 0, pointerType: 'mouse', preventDefault() { prevented = true; } });
  const [layer] = soaksOf(env);
  assert.ok(layer, 'ต้องมีชั้นหมึกซึม');
  assert.equal(layer.className, 'ink-soak');
  assert.equal(layer.style.width, '120px');
  assert.equal(layer.children.length, 4);
  assert.equal(new Set(layer.children.map(blob => blob.style.background)).size, 4, 'แต่ละหยดคนละสี');
  assert.equal(prevented, false);
  assert.ok(env.ink.getState().lobeCount >= 8, 'มีหมึกกระจายรอบจุดกดด้วย');
  env.timers.forEach(timer => timer.fn());
  assert.equal(soaksOf(env).length, 0);
});

test('ปุ่มพื้นเข้มใช้โหมดสีสว่าง และพื้นที่ใหญ่เกินครึ่งจอไม่ถูกย้อมทั้งแผ่น', () => {
  const dark = setup({ background: 'rgb(31, 42, 36)' });
  const button = makeElement('button');
  button.interactive = true;
  dark.fire('pointerdown', { target: button, clientX: 60, clientY: 40, button: 0 });
  assert.equal(soaksOf(dark)[0].className, 'ink-soak ink-soak--dark');

  const env = setup();
  const huge = makeElement('a');
  huge.interactive = true;
  huge.rect = { left: 0, top: 0, width: 1200, height: 700 };
  env.fire('pointerdown', { target: huge, clientX: 60, clientY: 40, button: 0 });
  assert.equal(soaksOf(env).length, 0);
});

test('กดพื้นที่ว่างหรือคลิกขวาไม่เกิดหมึก', () => {
  const env = setup();
  env.fire('pointerdown', { target: makeElement('div'), clientX: 5, clientY: 5, button: 0 });
  const button = makeElement('button');
  button.interactive = true;
  env.fire('pointerdown', { target: button, clientX: 5, clientY: 5, button: 2 });
  assert.equal(soaksOf(env).length, 0);
  assert.equal(env.ink.getState().lobeCount, 0);
});

test('ตั้งค่าลดการเคลื่อนไหว: ไม่มี canvas ไม่มีรอย ไม่มีหมึกซึม', () => {
  const env = setup({ reducedMotion: true });
  assert.equal(canvasOf(env), undefined);
  env.move(0, 0);
  env.move(300, 300);
  const button = makeElement('button');
  button.interactive = true;
  env.fire('pointerdown', { target: button, clientX: 60, clientY: 40, button: 0 });
  assert.equal(env.ink.getState().lobeCount, 0);
  assert.equal(soaksOf(env).length, 0);
});

test('เปลี่ยนเป็นลดการเคลื่อนไหวระหว่างใช้งาน: ล้างทุกอย่างทันที', () => {
  const env = setup();
  env.move(0, 0);
  env.move(400, 0);
  assert.ok(env.ink.getState().lobeCount > 0);
  env.media.matches = true;
  env.media.listener();
  assert.equal(env.ink.getState().lobeCount, 0);
  assert.equal(canvasOf(env), undefined);
});

test('ความเข้มสูงสุดต่อหยดไม่เกิน 0.3 เพื่อไม่บังตัวหนังสือ', () => {
  assert.ok(setup().ink.getState().peakAlpha <= 0.3);
});
