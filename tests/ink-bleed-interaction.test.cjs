const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

const source = fs.readFileSync('static/js/ink_bleed.js', 'utf8');

function createMockElement(tag, doc) {
  const listeners = {};
  const children = [];
  const attrs = {};
  const classes = new Set();
  let _className = '';

  function syncClassesFromClassName(v) {
    _className = String(v ?? '');
    classes.clear();
    _className.split(/\s+/).filter(Boolean).forEach(c => classes.add(c));
  }

  function syncClassNameFromClasses() {
    _className = Array.from(classes).join(' ');
  }

  const el = {
    tagName: tag.toUpperCase(),
    listeners,
    children,
    attrs,
    dataset: {},
    style: {},
    parentNode: null,
    get className() {
      return _className;
    },
    set className(v) {
      syncClassesFromClassName(v);
    },
    setAttribute(k, v) {
      attrs[k] = String(v);
      if (k === 'class') {
        syncClassesFromClassName(v);
      }
      if (k === 'data-ink') {
        el.dataset.ink = String(v);
      }
    },
    getAttribute(k) {
      if (k === 'class') return _className;
      if (k === 'data-ink') return el.dataset.ink ?? attrs['data-ink'] ?? null;
      return attrs[k] ?? null;
    },
    removeAttribute(k) {
      delete attrs[k];
      if (k === 'class') {
        syncClassesFromClassName('');
      }
      if (k === 'data-ink') delete el.dataset.ink;
    },
    classList: {
      add(c) {
        classes.add(c);
        syncClassNameFromClasses();
      },
      remove(c) {
        classes.delete(c);
        syncClassNameFromClasses();
      },
      contains(c) {
        return classes.has(c);
      }
    },
    appendChild(child) {
      child.parentNode = el;
      children.push(child);
      return child;
    },
    removeChild(child) {
      const idx = children.indexOf(child);
      if (idx !== -1) {
        children.splice(idx, 1);
        child.parentNode = null;
      }
      return child;
    },
    remove() {
      if (el.parentNode) {
        el.parentNode.removeChild(el);
      }
    },
    querySelector(selector) {
      return children.find(c => matchSelector(c, selector)) || null;
    },
    querySelectorAll(selector) {
      const found = [];
      function recurse(node) {
        for (const child of node.children) {
          if (matchSelector(child, selector)) found.push(child);
          recurse(child);
        }
      }
      recurse(el);
      return found;
    },
    closest(selector) {
      let cur = el;
      while (cur) {
        if (matchSelector(cur, selector)) return cur;
        cur = cur.parentNode;
      }
      return null;
    },
    getBoundingClientRect() {
      return { left: 10, top: 20, width: 100, height: 40, right: 110, bottom: 60 };
    },
    addEventListener(event, fn) {
      listeners[event] = listeners[event] || [];
      listeners[event].push(fn);
    },
    removeEventListener(event, fn) {
      if (!listeners[event]) return;
      listeners[event] = listeners[event].filter(cb => cb !== fn);
    },
    fire(event, data = {}) {
      const e = {
        type: event,
        target: el,
        currentTarget: el,
        preventDefaultCalled: false,
        stopPropagationCalled: false,
        preventDefault() { this.preventDefaultCalled = true; },
        stopPropagation() { this.stopPropagationCalled = true; },
        ...data
      };
      const list = listeners[event] || [];
      for (const fn of list) {
        fn(e);
      }
      return e;
    },
    getContext(type) {
      if (type !== '2d') return null;
      return {
        scale() {},
        setTransform() {},
        clearRect() {},
        beginPath() {},
        arc() {},
        fill() {},
        createRadialGradient() {
          return { addColorStop() {} };
        }
      };
    }
  };

  return el;
}

function matchSelector(el, selectorList) {
  if (!el || !el.tagName) return false;
  const selectors = selectorList.split(',').map(s => s.trim());
  const tag = el.tagName.toLowerCase();

  for (const s of selectors) {
    if (s.startsWith('.')) {
      const cls = s.slice(1);
      if (el.classList && typeof el.classList.contains === 'function' && el.classList.contains(cls)) return true;
      if (typeof el.className === 'string') {
        const classNames = el.className.split(/\s+/).filter(Boolean);
        if (classNames.includes(cls)) return true;
      }
    } else if (s.startsWith('[') && s.endsWith(']')) {
      const inner = s.slice(1, -1);
      if (inner.includes('=')) {
        const [k, v] = inner.split('=').map(x => x.replace(/["']/g, '').trim());
        if (el.getAttribute(k) === v) return true;
      } else {
        if (el.getAttribute(inner) !== null) return true;
      }
    } else if (s === tag) {
      return true;
    }
  }
  return false;
}

function setupEnvironment({ inkEnabled = true, reducedMotion = false, dpr = 1.0 } = {}) {
  const docListeners = {};
  const winListeners = {};
  const mediaListeners = [];
  const timeouts = new Map();
  const rafCallbacks = new Map();
  let nextTimeout = 0;
  let nextRaf = 0;
  let activeMql = null;

  let doc = {
    hidden: false,
    readyState: 'complete',
    addEventListener(evt, fn) {
      docListeners[evt] = docListeners[evt] || [];
      docListeners[evt].push(fn);
    },
    removeEventListener(evt, fn) {
      if (!docListeners[evt]) return;
      docListeners[evt] = docListeners[evt].filter(cb => cb !== fn);
    },
    createElement(tag) {
      return createMockElement(tag, doc);
    },
    querySelector(selector) {
      return doc.body.querySelector(selector);
    },
    querySelectorAll(selector) {
      return doc.body.querySelectorAll(selector);
    },
    fire(event, data = {}) {
      const e = {
        type: event,
        preventDefaultCalled: false,
        stopPropagationCalled: false,
        preventDefault() { this.preventDefaultCalled = true; },
        stopPropagation() { this.stopPropagationCalled = true; },
        ...data
      };
      const list = docListeners[event] || [];
      for (const fn of list) {
        fn(e);
      }
      return e;
    }
  };

  doc.body = createMockElement('body', doc);
  if (inkEnabled) {
    doc.body.dataset.ink = 'on';
  }

  const win = {
    devicePixelRatio: dpr,
    innerWidth: 1024,
    innerHeight: 768,
    addEventListener(evt, fn) {
      winListeners[evt] = winListeners[evt] || [];
      winListeners[evt].push(fn);
    },
    removeEventListener(evt, fn) {
      if (!winListeners[evt]) return;
      winListeners[evt] = winListeners[evt].filter(cb => cb !== fn);
    },
    matchMedia(q) {
      let isReduced = reducedMotion;
      const mql = {
        matches: isReduced,
        addEventListener(type, fn) {
          if (type === 'change') {
            mediaListeners.push(fn);
          }
        },
        removeEventListener(type, fn) {
          if (type === 'change') {
            const idx = mediaListeners.indexOf(fn);
            if (idx !== -1) mediaListeners.splice(idx, 1);
          }
        },
        addListener(fn) {
          mediaListeners.push(fn);
        },
        removeListener(fn) {
          const idx = mediaListeners.indexOf(fn);
          if (idx !== -1) mediaListeners.splice(idx, 1);
        }
      };
      activeMql = mql;
      return mql;
    },
    requestAnimationFrame(cb) {
      const id = ++nextRaf;
      rafCallbacks.set(id, cb);
      return id;
    },
    cancelAnimationFrame(id) {
      rafCallbacks.delete(id);
    },
    setTimeout(fn, delay) {
      const id = ++nextTimeout;
      timeouts.set(id, { fn, delay });
      return id;
    },
    clearTimeout(id) {
      timeouts.delete(id);
    }
  };

  let simulatedNow = 1000;
  const perf = {
    now() {
      return simulatedNow;
    }
  };

  const sandbox = {
    window: win,
    document: doc,
    performance: perf,
    requestAnimationFrame: win.requestAnimationFrame.bind(win),
    cancelAnimationFrame: win.cancelAnimationFrame.bind(win),
    setTimeout: win.setTimeout.bind(win),
    clearTimeout: win.clearTimeout.bind(win),
    Date: { now: () => simulatedNow },
    Math
  };

  vm.runInNewContext(source, sandbox);
  const InkBleed = sandbox.window.InkBleed;

  return {
    doc,
    win,
    InkBleed,
    rafCallbacks,
    timeouts,
    setSimulatedTime(t) { simulatedNow = t; },
    flushRaf(timestamp) {
      const cbs = Array.from(rafCallbacks.values());
      rafCallbacks.clear();
      for (const cb of cbs) {
        cb(timestamp || simulatedNow);
      }
    },
    flushTimeouts() {
      const entries = Array.from(timeouts.values());
      timeouts.clear();
      for (const item of entries) {
        item.fn();
      }
    },
    getMediaListeners() {
      return mediaListeners;
    },
    getActiveMql() {
      return activeMql;
    },
    triggerReducedMotionChange(matches) {
      if (activeMql) {
        activeMql.matches = matches;
      }
      for (const fn of [...mediaListeners]) {
        fn({ matches });
      }
    }
  };
}

test('ink bleed: does not initialize when data-ink="on" is absent', () => {
  const env = setupEnvironment({ inkEnabled: false });
  assert.equal(env.InkBleed.isInkEnabled(), false);
  const state = env.InkBleed.getState();
  assert.equal(state.isInitialized, false);
  assert.equal(state.canvas, null);
  assert.equal(env.doc.querySelectorAll('.ink-bleed-canvas').length, 0);
});

test('ink bleed: initializes canvas and hooks when data-ink="on" is present', () => {
  const env = setupEnvironment({ inkEnabled: true });
  assert.equal(env.InkBleed.isInkEnabled(), true);
  const state = env.InkBleed.getState();
  assert.equal(state.isInitialized, true);
  assert.notEqual(state.canvas, null);
  assert.equal(state.canvas.getAttribute('aria-hidden'), 'true');
  assert.equal(state.canvas.className, 'ink-bleed-canvas');
});

test('ink bleed: devicePixelRatio is capped at 1.5', () => {
  const env = setupEnvironment({ inkEnabled: true, dpr: 3.0 });
  const state = env.InkBleed.getState();
  assert.equal(state.dpr, 1.5);
});

test('ink bleed: mouse pointermove spawns particles with capped alpha and particles count', () => {
  const env = setupEnvironment({ inkEnabled: true });
  env.setSimulatedTime(1000);

  // Initial pointermove
  env.doc.fire('pointermove', { pointerType: 'mouse', clientX: 100, clientY: 100 });
  let state = env.InkBleed.getState();
  assert.equal(state.particleCount, 1);
  assert.ok(state.particles[0].alpha <= 0.10, 'Particle alpha must be capped at 0.10');

  // Spawn up to 80 particles; must be capped at MAX_PARTICLES (60)
  for (let i = 0; i < 80; i++) {
    env.setSimulatedTime(1000 + (i + 1) * 200);
    env.doc.fire('pointermove', { pointerType: 'mouse', clientX: 100 + (i + 1) * 25, clientY: 100 });
  }

  state = env.InkBleed.getState();
  assert.equal(state.particleCount, 60, 'Particle count must not exceed 60');
  for (const p of state.particles) {
    assert.ok(p.alpha <= 0.10, 'All particles must have alpha <= 0.10');
  }
});

test('ink bleed: touch and pen pointers are completely ignored for ambient trail', () => {
  const env = setupEnvironment({ inkEnabled: true });
  env.setSimulatedTime(1000);

  env.doc.fire('pointermove', { pointerType: 'touch', clientX: 200, clientY: 200 });
  assert.equal(env.InkBleed.getState().particleCount, 0);

  env.doc.fire('pointermove', { pointerType: 'pen', clientX: 300, clientY: 300 });
  assert.equal(env.InkBleed.getState().particleCount, 0);

  env.doc.fire('pointermove', { touches: [{ clientX: 400, clientY: 400 }], clientX: 400, clientY: 400 });
  assert.equal(env.InkBleed.getState().particleCount, 0);
});

test('ink bleed: RAF loop stops on idle when particles decay to zero', () => {
  const env = setupEnvironment({ inkEnabled: true });
  env.setSimulatedTime(1000);
  env.doc.fire('pointermove', { pointerType: 'mouse', clientX: 50, clientY: 50 });

  assert.equal(env.InkBleed.getState().particleCount, 1);
  assert.ok(env.rafCallbacks.size > 0, 'RAF must be scheduled when particle exists');

  // Advance frames until particle decays
  let time = 1000;
  for (let i = 0; i < 150; i++) {
    time += 20;
    env.flushRaf(time);
    if (env.InkBleed.getState().particleCount === 0) break;
  }

  assert.equal(env.InkBleed.getState().particleCount, 0);
  assert.equal(env.rafCallbacks.size, 0, 'RAF must stop when no particles remain');
});

test('ink bleed: visibility hidden immediately halts RAF and clears particles', () => {
  const env = setupEnvironment({ inkEnabled: true });
  env.setSimulatedTime(1000);
  env.doc.fire('pointermove', { pointerType: 'mouse', clientX: 60, clientY: 60 });
  assert.equal(env.InkBleed.getState().particleCount, 1);
  assert.ok(env.rafCallbacks.size > 0);

  // Document becomes hidden (tab switch/minimize)
  env.doc.hidden = true;
  env.doc.fire('visibilitychange');

  assert.equal(env.InkBleed.getState().particleCount, 0, 'Particles must be cleared on hidden');
  assert.equal(env.rafCallbacks.size, 0, 'RAF must be cancelled on hidden');
});

test('ink bleed: pointerdown on interactive control creates 3–4 transient rings without blocking', () => {
  const env = setupEnvironment({ inkEnabled: true });

  const btn = env.doc.createElement('button');
  env.doc.body.appendChild(btn);

  const event = env.doc.fire('pointerdown', {
    pointerType: 'mouse',
    button: 0,
    clientX: 120,
    clientY: 150,
    target: btn
  });

  assert.equal(event.preventDefaultCalled, false, 'Must not call preventDefault');
  assert.equal(event.stopPropagationCalled, false, 'Must not call stopPropagation');

  const containers = env.doc.querySelectorAll('.ink-ring-container');
  assert.equal(containers.length, 1, 'One ring container must be mounted');
  assert.equal(containers[0].getAttribute('aria-hidden'), 'true');

  const rings = containers[0].querySelectorAll('.ink-ring');
  assert.ok(rings.length >= 3 && rings.length <= 4, 'Must create 3 to 4 ink rings');

  // Rings should expire and be removed after timeout
  env.flushTimeouts();
  assert.equal(env.doc.querySelectorAll('.ink-ring-container').length, 0, 'Rings container must be removed on expire');
});

test('ink bleed: pointerdown ignores touch/pen, non-interactive elements, and secondary clicks', () => {
  const env = setupEnvironment({ inkEnabled: true });

  const btn = env.doc.createElement('button');
  const div = env.doc.createElement('div');
  env.doc.body.appendChild(btn);
  env.doc.body.appendChild(div);

  // Touch on button -> ignored
  env.doc.fire('pointerdown', { pointerType: 'touch', button: 0, target: btn });
  assert.equal(env.doc.querySelectorAll('.ink-ring-container').length, 0);

  // Right-click on button -> ignored
  env.doc.fire('pointerdown', { pointerType: 'mouse', button: 2, target: btn });
  assert.equal(env.doc.querySelectorAll('.ink-ring-container').length, 0);

  // Click on plain non-interactive div -> ignored
  env.doc.fire('pointerdown', { pointerType: 'mouse', button: 0, target: div });
  assert.equal(env.doc.querySelectorAll('.ink-ring-container').length, 0);
});

test('ink bleed: prefers-reduced-motion disables canvas trail and click rings', () => {
  const env = setupEnvironment({ inkEnabled: true, reducedMotion: true });

  assert.equal(env.InkBleed.isReducedMotion(), true);
  assert.equal(env.InkBleed.getState().canvas, null, 'No canvas when reduced motion is enabled');

  // Pointermove does not spawn particles
  env.doc.fire('pointermove', { pointerType: 'mouse', clientX: 100, clientY: 100 });
  assert.equal(env.InkBleed.getState().particleCount, 0);

  // Pointerdown on button does not spawn rings
  const btn = env.doc.createElement('button');
  env.doc.body.appendChild(btn);
  env.doc.fire('pointerdown', { pointerType: 'mouse', button: 0, target: btn });
  assert.equal(env.doc.querySelectorAll('.ink-ring-container').length, 0);
});

test('ink bleed: HTMX event delegation creates rings on newly swapped content', () => {
  const env = setupEnvironment({ inkEnabled: true });

  const resultsDiv = env.doc.createElement('div');
  resultsDiv.setAttribute('id', 'online-results');
  env.doc.body.appendChild(resultsDiv);

  // Simulate HTMX inner swap
  const newRow = env.doc.createElement('article');
  newRow.setAttribute('class', 'online-result-row');
  const quickBookBtn = env.doc.createElement('button');
  newRow.appendChild(quickBookBtn);
  resultsDiv.appendChild(newRow);

  // Pointerdown on the freshly swapped button
  env.doc.fire('pointerdown', {
    pointerType: 'mouse',
    button: 0,
    clientX: 250,
    clientY: 300,
    target: quickBookBtn
  });

  const containers = env.doc.querySelectorAll('.ink-ring-container');
  assert.equal(containers.length, 1, 'Ring container must be created for HTMX swapped elements via delegation');
});

test('ink bleed: reduced-motion recovers canvas and interactions when reduce preference changes to false, without duplicate listeners, and cleanup unregisters change handler', () => {
  const env = setupEnvironment({ inkEnabled: true, reducedMotion: true });

  assert.equal(env.InkBleed.isReducedMotion(), true);
  assert.equal(env.InkBleed.getState().canvas, null, 'Initially null canvas under reduced-motion');
  assert.equal(env.doc.querySelectorAll('.ink-bleed-canvas').length, 0);

  // Preference changes from reduce=true to reduce=false
  env.triggerReducedMotionChange(false);

  assert.equal(env.InkBleed.isReducedMotion(), false);
  const state = env.InkBleed.getState();
  assert.notEqual(state.canvas, null, 'Canvas must be created/restored after reduced motion turns off');
  assert.equal(env.doc.querySelectorAll('.ink-bleed-canvas').length, 1, 'Exactly one canvas attached to DOM');
  assert.equal(state.isResizeBound, true);

  // Redundant trigger of false must not create duplicate canvas or listeners
  env.triggerReducedMotionChange(false);
  assert.equal(env.doc.querySelectorAll('.ink-bleed-canvas').length, 1, 'Must not duplicate canvas');

  // Verify interactions now work
  env.setSimulatedTime(1000);
  env.doc.fire('pointermove', { pointerType: 'mouse', clientX: 150, clientY: 150 });
  assert.equal(env.InkBleed.getState().particleCount, 1, 'Mouse trail must work after recovery');

  const btn = env.doc.createElement('button');
  env.doc.body.appendChild(btn);
  env.doc.fire('pointerdown', { pointerType: 'mouse', button: 0, clientX: 100, clientY: 100, target: btn });
  assert.equal(env.doc.querySelectorAll('.ink-ring-container').length, 1, 'Click rings must work after recovery');

  // Cleanup should remove MediaQueryList change listener and canvas
  assert.equal(env.getMediaListeners().length, 1, 'MediaQueryList listener must be retained');
  env.InkBleed.cleanup();
  assert.equal(env.getMediaListeners().length, 0, 'MediaQueryList listener must be removed on cleanup');
  assert.equal(env.InkBleed.getState().canvas, null, 'Canvas must be removed and null on cleanup');
  assert.equal(env.doc.querySelectorAll('.ink-bleed-canvas').length, 0);
});

test('ink bleed: transient click rings use 3–4 theme CSS variables (--ok, --link, --pending-text, --stamp) with low opacity', () => {
  const env = setupEnvironment({ inkEnabled: true });

  const btn = env.doc.createElement('button');
  env.doc.body.appendChild(btn);

  env.doc.fire('pointerdown', {
    pointerType: 'mouse',
    button: 0,
    clientX: 200,
    clientY: 250,
    target: btn
  });

  const container = env.doc.querySelector('.ink-ring-container');
  assert.notEqual(container, null);
  const rings = container.querySelectorAll('.ink-ring');
  assert.ok(rings.length >= 3 && rings.length <= 4, 'Must create 3 to 4 rings');

  const expectedTokens = ['--ok', '--link', '--pending-text', '--stamp'];
  const usedTokens = [];

  for (let i = 0; i < rings.length; i++) {
    const ring = rings[i];
    const borderColor = ring.style.borderColor || '';
    assert.ok(
      expectedTokens.some(token => borderColor.includes(token)),
      `Ring ${i + 1} must use one of the theme CSS variables (${expectedTokens.join(', ')}), got: ${borderColor}`
    );
    usedTokens.push(borderColor);
  }

  // Ensure rings use diverse theme tokens, not just one hardcoded color
  const uniqueTokens = new Set(usedTokens);
  assert.ok(uniqueTokens.size >= 3, `Expected at least 3 distinct theme colors across rings, got ${uniqueTokens.size}`);
});
