/**
 * SIGROOM — หมึกสีน้ำซึมกระดาษ
 * 1) ลากเมาส์: รอยสีน้ำหลายสีซึมตามปลายเมาส์แล้วค่อย ๆ จาง (วาดบน canvas เดียว)
 * 2) กดปุ่ม/เมนู/ชิป: หมึกหลายสีแผ่ซึมเข้าไปในองค์ประกอบที่กด
 * ปิดเองเมื่อ prefers-reduced-motion · ไม่ขวางการกด · ปิดรายหน้าได้ด้วย <body data-ink="off">
 */
(function () {
  'use strict';

  var MAX_LOBES = 180;
  var MAX_DPR = 1.5;
  var EMIT_DISTANCE = 14;       // px ระหว่างหยดบนเส้นทางเมาส์
  var MAX_EMITS_PER_MOVE = 6;
  var COLOR_SPAN = 170;         // px ที่เมาส์ต้องเดินก่อนเปลี่ยนไปสีถัดไป
  var PEAK_ALPHA = 0.22;        // บนกระดาษ (multiply) · พื้นเข้มลดลงเล็กน้อยเพราะ screen สว่างเร็ว
  var SOAK_LIFETIME_MS = 1500;
  var SOAK_MAX_AREA_RATIO = 0.5;
  // เขียว น้ำเงิน เหลืองอำพัน แดง (สีแถบแฟ้มบริการ) + ม่วง เขียวน้ำทะเล ให้ไล่สีต่อเนื่อง
  var PIGMENTS = [
    [47, 107, 58], [31, 78, 121], [196, 132, 24], [163, 36, 28], [104, 74, 145], [24, 122, 122]
  ];
  var INTERACTIVE_SELECTOR = 'a, button, summary, [role="button"], input[type="submit"], input[type="button"], label, .online-chip, .chip, [data-ink-target]';

  var canvas = null;       // พื้นสว่าง: ผสมแบบ multiply เหมือนสีน้ำบนกระดาษ
  var ctx = null;
  var glowCanvas = null;   // พื้นเข้ม: ผสมแบบ screen ให้สีสว่างเรืองบนพื้นหมึก
  var glowCtx = null;
  var lobes = [];
  var rafId = null;
  var dpr = 1;
  var lastX = null;
  var lastY = null;
  var carry = 0;
  var travel = 0;
  var isInitialized = false;
  var isResizeBound = false;
  var motionQuery = null;
  var soakTimers = [];

  function now() {
    return (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
  }

  function isInkEnabled() {
    if (typeof document === 'undefined' || !document.body) return false;
    var value = document.body.getAttribute ? document.body.getAttribute('data-ink') : null;
    return value !== 'off';
  }

  function isReducedMotion() {
    if (motionQuery && typeof motionQuery.matches === 'boolean') return Boolean(motionQuery.matches);
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    var query = window.matchMedia('(prefers-reduced-motion: reduce)');
    return Boolean(query && query.matches);
  }

  function pigmentAt(position) {
    var count = PIGMENTS.length;
    var base = Math.floor(position) % count;
    var next = (base + 1) % count;
    var mix = position - Math.floor(position);
    var a = PIGMENTS[base];
    var b = PIGMENTS[next];
    return [
      Math.round(a[0] + (b[0] - a[0]) * mix),
      Math.round(a[1] + (b[1] - a[1]) * mix),
      Math.round(a[2] + (b[2] - a[2]) * mix)
    ];
  }

  function resizeCanvas() {
    if (!canvas || typeof window === 'undefined') return;
    dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    [[canvas, ctx], [glowCanvas, glowCtx]].forEach(function (pair) {
      if (!pair[0]) return;
      pair[0].width = Math.round((window.innerWidth || 800) * dpr);
      pair[0].height = Math.round((window.innerHeight || 600) * dpr);
      if (pair[1] && pair[1].setTransform) pair[1].setTransform(dpr, 0, 0, dpr, 0, 0);
    });
  }

  function createLayer(className) {
    var element = document.createElement('canvas');
    var context = element.getContext ? element.getContext('2d') : null;
    if (!context) return null;
    element.className = className;
    element.setAttribute('aria-hidden', 'true');
    return [element, context];
  }

  function setupCanvas() {
    if (canvas || isReducedMotion() || !document.createElement) return;
    var paper = createLayer('ink-bleed-canvas');
    var glow = createLayer('ink-bleed-canvas ink-bleed-canvas--glow');
    if (!paper || !glow) return;
    canvas = paper[0];
    ctx = paper[1];
    glowCanvas = glow[0];
    glowCtx = glow[1];
    resizeCanvas();
    document.body.appendChild(canvas);
    document.body.appendChild(glowCanvas);
    if (!isResizeBound && window.addEventListener) {
      window.addEventListener('resize', resizeCanvas);
      isResizeBound = true;
    }
  }

  function clearCanvas() {
    if (ctx && canvas) ctx.clearRect(0, 0, canvas.width, canvas.height);
    if (glowCtx && glowCanvas) glowCtx.clearRect(0, 0, glowCanvas.width, glowCanvas.height);
  }

  function stopRaf() {
    if (rafId !== null && typeof cancelAnimationFrame !== 'undefined') cancelAnimationFrame(rafId);
    rafId = null;
  }

  function startRaf() {
    if (rafId !== null || typeof requestAnimationFrame === 'undefined') return;
    if (!lobes.length || isReducedMotion() || document.hidden) return;
    rafId = requestAnimationFrame(renderLoop);
  }

  function drawLobe(lobe, t) {
    var grow = 1 - Math.pow(1 - t, 3);                       // ซึมเร็วตอนแรกแล้วช้าลง
    var radius = lobe.r0 + (lobe.r1 - lobe.r0) * grow;
    var alpha = lobe.peak * Math.min(1, t / 0.08) * Math.pow(1 - t, 1.5);
    if (alpha <= 0.002) return;
    var c = lobe.color;
    var layer = lobe.dark ? glowCtx : ctx;
    var rgb = 'rgba(' + c[0] + ',' + c[1] + ',' + c[2] + ',';
    if (layer.createRadialGradient) {
      var gradient = layer.createRadialGradient(lobe.x, lobe.y, 0, lobe.x, lobe.y, radius);
      gradient.addColorStop(0, rgb + (alpha * 0.75).toFixed(4) + ')');
      gradient.addColorStop(0.6, rgb + (alpha * 0.6).toFixed(4) + ')');
      gradient.addColorStop(0.84, rgb + alpha.toFixed(4) + ')');   // สีเข้มขึ้นที่ขอบแบบสีน้ำแห้ง
      gradient.addColorStop(1, rgb + '0)');
      layer.fillStyle = gradient;
    } else {
      layer.fillStyle = rgb + alpha.toFixed(4) + ')';
    }
    layer.beginPath();
    layer.arc(lobe.x, lobe.y, radius, 0, Math.PI * 2);
    layer.fill();
  }

  function renderLoop(timestamp) {
    rafId = null;
    if (!ctx || !canvas || document.hidden || isReducedMotion()) {
      lobes = [];
      clearCanvas();
      return;
    }
    var time = typeof timestamp === 'number' ? timestamp : now();
    clearCanvas();
    var alive = [];
    for (var i = 0; i < lobes.length; i++) {
      var lobe = lobes[i];
      var t = (time - lobe.born) / lobe.life;
      if (t >= 1) continue;
      alive.push(lobe);
      drawLobe(lobe, Math.max(0, t));
    }
    lobes = alive;
    if (lobes.length) rafId = requestAnimationFrame(renderLoop);
  }

  function lighten(color) {
    return color.map(function (channel) { return Math.round(channel + (255 - channel) * 0.45); });
  }

  function addLobe(x, y, color, scale, lifeScale, dark) {
    if (lobes.length >= MAX_LOBES) lobes.shift();
    lobes.push({
      x: x, y: y, color: dark ? lighten(color) : color, dark: Boolean(dark), born: now(),
      r0: (7 + Math.random() * 7) * scale,
      r1: (30 + Math.random() * 28) * scale,
      life: (1500 + Math.random() * 900) * lifeScale,
      peak: PEAK_ALPHA * (dark ? 0.75 : 1) * (0.6 + Math.random() * 0.4)
    });
  }

  /** หยดสีน้ำหนึ่งจุด: 3 วงซ้อนเยื้องกันให้ขอบไม่กลมเรียบ */
  function spawnWash(x, y, color, scale, dark) {
    if (isReducedMotion()) return;
    color = color || pigmentAt(travel / COLOR_SPAN);
    scale = scale || 1;
    for (var i = 0; i < 3; i++) {
      addLobe(x + (Math.random() - 0.5) * 16 * scale, y + (Math.random() - 0.5) * 16 * scale, color, scale, 1, dark);
    }
    startRaf();
  }

  /** หมึกหลายสีแตกกระจายที่จุดกด */
  function spawnBurst(x, y) {
    if (isReducedMotion()) return;
    var dark = isDarkAt(x, y);
    var start = Math.floor(travel / COLOR_SPAN);
    for (var i = 0; i < 4; i++) {
      var angle = (Math.PI * 2 * i) / 4 + Math.random();
      var distance = 10 + Math.random() * 18;
      var color = PIGMENTS[(start + i) % PIGMENTS.length];
      addLobe(x + Math.cos(angle) * distance, y + Math.sin(angle) * distance, color, 1.7, 1.35, dark);
      addLobe(x + Math.cos(angle) * distance * 0.4, y + Math.sin(angle) * distance * 0.4, color, 1.1, 1.2, dark);
    }
    startRaf();
  }

  function onPointerMove(event) {
    if (!event || (event.pointerType && event.pointerType !== 'mouse')) return;
    if (isReducedMotion() || document.hidden || !ctx) return;
    var x = event.clientX;
    var y = event.clientY;
    if (typeof x !== 'number' || typeof y !== 'number') return;
    if (lastX === null) {
      lastX = x;
      lastY = y;
      return;
    }
    var dx = x - lastX;
    var dy = y - lastY;
    var distance = Math.sqrt(dx * dx + dy * dy);
    if (distance < 1) return;
    // วางหยดตามระยะทางบนเส้นทาง เมาส์เร็วแค่ไหนรอยก็ยังต่อเนื่อง
    var covered = carry + distance;
    var emits = Math.min(Math.floor(covered / EMIT_DISTANCE), MAX_EMITS_PER_MOVE);
    var dark = emits ? isDarkAt(x, y) : false;
    for (var i = 1; i <= emits; i++) {
      var along = Math.min(1, Math.max(0, (i * EMIT_DISTANCE - carry) / distance));
      travel += EMIT_DISTANCE;
      spawnWash(lastX + dx * along, lastY + dy * along, null, 1, dark);
    }
    carry = emits ? 0 : covered;
    lastX = x;
    lastY = y;
  }

  /** คืน true/false เมื่อองค์ประกอบมีสีพื้นทึบ, null เมื่อโปร่งใส (ต้องดูชั้นที่อยู่ข้างหลัง) */
  function surfaceTone(element) {
    if (typeof window === 'undefined' || !window.getComputedStyle) return null;
    var style = window.getComputedStyle(element).backgroundColor || '';
    var open = style.indexOf('(');
    var close = style.indexOf(')');
    if (style.indexOf('rgb') !== 0 || open < 0 || close < 0) return null;
    var parts = style.slice(open + 1, close).split(',').map(parseFloat);
    if (parts.length > 3 && parts[3] < 0.5) return null;
    return (0.2126 * parts[0] + 0.7152 * parts[1] + 0.0722 * parts[2]) / 255 < 0.4;
  }

  function isDarkSurface(element) {
    for (var depth = 0; element && depth < 10; depth++) {
      var tone = element.tagName ? surfaceTone(element) : null;
      if (tone !== null) return tone;
      element = element.parentNode;
    }
    return false;
  }

  function isDarkAt(x, y) {
    if (!document.elementFromPoint) return false;
    return isDarkSurface(document.elementFromPoint(x, y));
  }

  /** หมึกแผ่ซึมเข้าไปในองค์ประกอบที่กด (ชั้นภาพลอยทับ ไม่แตะ DOM ของปุ่ม) */
  function soak(target, x, y) {
    if (isReducedMotion() || !target || !target.getBoundingClientRect) return null;
    var rect = target.getBoundingClientRect();
    if (rect.width < 8 || rect.height < 8) return null;
    var viewport = (window.innerWidth || 800) * (window.innerHeight || 600);
    if (rect.width * rect.height > viewport * SOAK_MAX_AREA_RATIO) return null;

    var layer = document.createElement('span');
    layer.className = 'ink-soak' + (isDarkSurface(target) ? ' ink-soak--dark' : '');
    layer.setAttribute('aria-hidden', 'true');
    layer.style.left = rect.left + 'px';
    layer.style.top = rect.top + 'px';
    layer.style.width = rect.width + 'px';
    layer.style.height = rect.height + 'px';
    if (window.getComputedStyle) layer.style.borderRadius = window.getComputedStyle(target).borderRadius || '';

    var size = Math.max(rect.width, rect.height) * 2.3;
    var start = Math.floor(travel / COLOR_SPAN);
    for (var i = 0; i < 4; i++) {
      var c = PIGMENTS[(start + i) % PIGMENTS.length];
      var blob = document.createElement('span');
      blob.className = 'ink-soak-blob';
      blob.style.left = (x - rect.left + (Math.random() - 0.5) * rect.width * 0.5) + 'px';
      blob.style.top = (y - rect.top + (Math.random() - 0.5) * rect.height * 0.6) + 'px';
      blob.style.width = size + 'px';
      blob.style.height = size + 'px';
      blob.style.animationDelay = (i * 80) + 'ms';
      blob.style.background = 'radial-gradient(circle, rgba(' + c.join(',') + ',.62) 0%, rgba(' + c.join(',') + ',.42) 42%, rgba(' + c.join(',') + ',0) 70%)';
      layer.appendChild(blob);
    }
    document.body.appendChild(layer);
    var timer = setTimeout(function () {
      removeNode(layer);
      soakTimers = soakTimers.filter(function (entry) { return entry.layer !== layer; });
    }, SOAK_LIFETIME_MS);
    soakTimers.push({ layer: layer, timer: timer });
    return layer;
  }

  function removeNode(node) {
    if (!node) return;
    if (typeof node.remove === 'function') node.remove();
    else if (node.parentNode) node.parentNode.removeChild(node);
  }

  function onPointerDown(event) {
    if (!event || (event.button !== undefined && event.button !== 0)) return;
    if (isReducedMotion()) return;
    var target = event.target && event.target.closest && event.target.closest(INTERACTIVE_SELECTOR);
    if (!target) return;
    var x = event.clientX;
    var y = event.clientY;
    if (typeof x !== 'number' || typeof y !== 'number') {
      var rect = target.getBoundingClientRect();
      x = rect.left + rect.width / 2;
      y = rect.top + rect.height / 2;
    }
    // ไม่ preventDefault ไม่หน่วงการนำทางหรือ HTMX — เป็นแค่ภาพ
    soak(target, x, y);
    if (ctx) spawnBurst(x, y);
  }

  function clearEffects() {
    stopRaf();
    lobes = [];
    clearCanvas();
    soakTimers.forEach(function (entry) {
      clearTimeout(entry.timer);
      removeNode(entry.layer);
    });
    soakTimers = [];
  }

  function onVisibilityChange() {
    if (document.hidden) {
      stopRaf();
      lobes = [];
      clearCanvas();
    }
  }

  function onMotionChange() {
    if (isReducedMotion()) {
      clearEffects();
      removeNode(canvas);
      removeNode(glowCanvas);
      canvas = ctx = glowCanvas = glowCtx = null;
    } else {
      setupCanvas();
    }
  }

  function init() {
    if (isInitialized || !isInkEnabled()) return;
    isInitialized = true;
    if (window.matchMedia) {
      motionQuery = window.matchMedia('(prefers-reduced-motion: reduce)');
      if (motionQuery && motionQuery.addEventListener) motionQuery.addEventListener('change', onMotionChange);
    }
    setupCanvas();
    document.addEventListener('pointermove', onPointerMove, { passive: true });
    document.addEventListener('pointerdown', onPointerDown, { passive: true });
    document.addEventListener('visibilitychange', onVisibilityChange);
  }

  function cleanup() {
    clearEffects();
    removeNode(canvas);
    removeNode(glowCanvas);
    canvas = ctx = glowCanvas = glowCtx = null;
    lastX = null;
    lastY = null;
    carry = 0;
    travel = 0;
    if (typeof document !== 'undefined' && document.removeEventListener) {
      document.removeEventListener('pointermove', onPointerMove);
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    }
    if (isResizeBound && window.removeEventListener) {
      window.removeEventListener('resize', resizeCanvas);
      isResizeBound = false;
    }
    if (motionQuery && motionQuery.removeEventListener) motionQuery.removeEventListener('change', onMotionChange);
    motionQuery = null;
    isInitialized = false;
  }

  var InkBleed = {
    init: init,
    cleanup: cleanup,
    spawnWash: spawnWash,
    spawnBurst: spawnBurst,
    soak: soak,
    renderLoop: renderLoop,
    isInkEnabled: isInkEnabled,
    isReducedMotion: isReducedMotion,
    getState: function () {
      return {
        isInitialized: isInitialized,
        lobeCount: lobes.length,
        lobeColors: lobes.map(function (lobe) { return lobe.color.join(','); }),
        darkLobeCount: lobes.filter(function (lobe) { return lobe.dark; }).length,
        maxLobes: MAX_LOBES,
        peakAlpha: PEAK_ALPHA,
        canvas: canvas,
        soakCount: soakTimers.length,
        soakLifetimeMs: SOAK_LIFETIME_MS,
        pigmentCount: PIGMENTS.length
      };
    }
  };

  if (typeof window !== 'undefined') window.InkBleed = InkBleed;
  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
  if (typeof module !== 'undefined' && module.exports) module.exports = InkBleed;
})();
