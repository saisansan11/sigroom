/**
 * SIGROOM PR-8 — Ink Bleed Interaction Layer
 * Ambient mouse canvas trail & transient click rings.
 * Public gateway and online teaching booking surfaces only.
 * Reduced-motion compliant, touch/pen ignored, non-blocking.
 */
(function () {
  'use strict';

  var MAX_PARTICLES = 60;
  var MAX_ALPHA = 0.10;
  var MAX_DPR = 1.5;
  var RING_CONTAINER_LIFETIME_MS = 800;
  var RING_ANIMATION_DURATION_MS = 620;
  var RING_MAX_DELAY_MS = 150;

  var canvas = null;
  var ctx = null;
  var particles = [];
  var rafId = null;
  var lastFrameTime = 0;
  var lastEmitX = -9999;
  var lastEmitY = -9999;
  var lastEmitTime = 0;
  var dpr = 1;
  var isInitialized = false;
  var reducedMotionMql = null;
  var isResizeBound = false;

  var RING_COLOR_TOKENS = [
    'var(--ok, #2F6B3A)',
    'var(--link, #1F4E79)',
    'var(--pending-text, #7A5F18)',
    'var(--stamp, #A3241C)'
  ];

  function isInkEnabled() {
    if (typeof document === 'undefined' || !document.body) return false;
    if (document.body.dataset && document.body.dataset.ink === 'on') return true;
    if (typeof document.body.getAttribute === 'function' && document.body.getAttribute('data-ink') === 'on') return true;
    return false;
  }

  function isReducedMotion() {
    if (reducedMotionMql && typeof reducedMotionMql.matches === 'boolean') {
      return Boolean(reducedMotionMql.matches);
    }
    if (typeof window === 'undefined' || !window.matchMedia) return false;
    var mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    return Boolean(mql && mql.matches);
  }

  function resizeCanvas() {
    if (!canvas || typeof window === 'undefined') return;
    dpr = Math.min(window.devicePixelRatio || 1, MAX_DPR);
    var w = window.innerWidth || (document.documentElement && document.documentElement.clientWidth) || 800;
    var h = window.innerHeight || (document.documentElement && document.documentElement.clientHeight) || 600;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    if (ctx) {
      if (ctx.setTransform) {
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      } else if (ctx.scale) {
        ctx.scale(dpr, dpr);
      }
    }
  }

  function setupCanvas() {
    if (typeof document === 'undefined' || typeof window === 'undefined') return;
    if (isReducedMotion()) return;
    if (!document.createElement) return;
    if (canvas && ctx) return;

    canvas = document.createElement('canvas');
    canvas.className = 'ink-bleed-canvas';
    canvas.setAttribute('aria-hidden', 'true');
    ctx = canvas.getContext ? canvas.getContext('2d') : null;
    if (!ctx) return;

    resizeCanvas();
    if (document.body && document.body.appendChild) {
      document.body.appendChild(canvas);
    }
    if (!isResizeBound && typeof window !== 'undefined' && window.addEventListener) {
      window.addEventListener('resize', resizeCanvas);
      isResizeBound = true;
    }
  }

  function startRaf() {
    if (rafId !== null) return;
    if (typeof requestAnimationFrame === 'undefined') return;
    if (isReducedMotion() || (document && document.hidden)) return;
    if (particles.length === 0) return;

    lastFrameTime = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    rafId = requestAnimationFrame(renderLoop);
  }

  function stopRaf() {
    if (rafId !== null && typeof cancelAnimationFrame !== 'undefined') {
      cancelAnimationFrame(rafId);
    }
    rafId = null;
  }

  function clearCanvas() {
    if (ctx && canvas) {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
    }
  }

  function renderLoop(timestamp) {
    if (typeof timestamp !== 'number') {
      timestamp = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    }
    var dt = Math.min(timestamp - lastFrameTime, 100);
    lastFrameTime = timestamp;

    if (document && document.hidden) {
      stopRaf();
      particles = [];
      clearCanvas();
      return;
    }

    if (isReducedMotion()) {
      stopRaf();
      particles = [];
      clearCanvas();
      return;
    }

    if (!ctx || !canvas) {
      stopRaf();
      return;
    }

    clearCanvas();

    var alive = [];
    var stepFactor = (dt || 16.67) / 16.67;

    for (var i = 0; i < particles.length; i++) {
      var p = particles[i];
      p.alpha -= p.decay * stepFactor;
      p.r += p.bleed * stepFactor;

      if (p.alpha > 0.005) {
        alive.push(p);
        var curAlpha = Math.min(Math.max(p.alpha, 0), MAX_ALPHA);

        if (ctx.createRadialGradient) {
          var grad = ctx.createRadialGradient(p.x, p.y, Math.max(0, p.r * 0.2), p.x, p.y, p.r);
          grad.addColorStop(0, 'rgba(31, 42, 36, ' + curAlpha.toFixed(4) + ')');
          grad.addColorStop(0.7, 'rgba(31, 42, 36, ' + (curAlpha * 0.5).toFixed(4) + ')');
          grad.addColorStop(1, 'rgba(31, 42, 36, 0)');
          ctx.fillStyle = grad;
        } else {
          ctx.fillStyle = 'rgba(31, 42, 36, ' + curAlpha.toFixed(4) + ')';
        }
        ctx.beginPath();
        ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      }
    }

    particles = alive;

    if (particles.length === 0) {
      stopRaf();
    } else {
      rafId = requestAnimationFrame(renderLoop);
    }
  }

  function spawnParticle(x, y) {
    if (isReducedMotion()) return;
    if (particles.length >= MAX_PARTICLES) {
      particles.shift();
    }

    var isBlot = Math.random() < 0.08;
    var radius = isBlot ? (28 + Math.random() * 12) : (6 + Math.random() * 4);
    var baseAlpha = isBlot ? (0.04 + Math.random() * 0.03) : (0.06 + Math.random() * 0.03);
    var initialAlpha = Math.min(baseAlpha, MAX_ALPHA);

    var particle = {
      x: x + (Math.random() - 0.5) * 3,
      y: y + (Math.random() - 0.5) * 3,
      r: radius,
      alpha: initialAlpha,
      maxAlpha: initialAlpha,
      decay: isBlot ? 0.008 : 0.015,
      bleed: isBlot ? 0.04 : 0.08
    };

    particles.push(particle);
    startRaf();
  }

  function onPointerMove(e) {
    if (!e) return;
    // Mouse-only ambient canvas trail. Ignore touch and pen.
    if (e.touches || (e.pointerType && e.pointerType !== 'mouse')) return;
    if (isReducedMotion() || (document && document.hidden)) return;

    var x = e.clientX;
    var y = e.clientY;
    if (typeof x !== 'number' || typeof y !== 'number') return;

    var now = (typeof performance !== 'undefined' && performance.now) ? performance.now() : Date.now();
    var dx = x - lastEmitX;
    var dy = y - lastEmitY;
    var dist = Math.sqrt(dx * dx + dy * dy);

    // Throttle: require at least 20px distance or 100ms interval (and ignore jitter < 2px)
    if (dist < 2 || (dist < 20 && (now - lastEmitTime) < 100)) return;

    lastEmitX = x;
    lastEmitY = y;
    lastEmitTime = now;

    spawnParticle(x, y);
  }

  function createRings(x, y) {
    if (isReducedMotion() || typeof document === 'undefined') return null;
    var container = document.createElement('div');
    container.className = 'ink-ring-container';
    container.setAttribute('aria-hidden', 'true');
    container.style.left = x + 'px';
    container.style.top = y + 'px';

    // 3 to 4 short rings (600–800ms) with theme CSS variable colors
    var ringCount = 3 + Math.floor(Math.random() * 2);
    for (var i = 0; i < ringCount; i++) {
      var ring = document.createElement('span');
      ring.className = 'ink-ring ink-ring-' + (i + 1);
      ring.style.borderColor = RING_COLOR_TOKENS[i % RING_COLOR_TOKENS.length];
      container.appendChild(ring);
    }

    if (document.body && document.body.appendChild) {
      document.body.appendChild(container);
      setTimeout(function () {
        if (typeof container.remove === 'function') {
          container.remove();
        } else if (container.parentNode) {
          container.parentNode.removeChild(container);
        }
      }, RING_CONTAINER_LIFETIME_MS);
    }
    return container;
  }

  var INTERACTIVE_SELECTOR = 'a, button, summary, [role="button"], input[type="submit"], input[type="button"], input[type="radio"], input[type="checkbox"], label, .online-chip, .online-result-row, .lka-g2-cta, .gateway-card, .online-result-card, .chip, [data-ink-target]';

  function onPointerDown(e) {
    if (!e) return;
    // Touch/pen ignored
    if (e.touches || (e.pointerType && e.pointerType !== 'mouse')) return;
    if (e.button !== undefined && e.button !== 0) return;
    if (isReducedMotion()) return;

    var target = e.target && e.target.closest && e.target.closest(INTERACTIVE_SELECTOR);
    if (!target) return;

    var x = e.clientX;
    var y = e.clientY;
    if (typeof x !== 'number' || typeof y !== 'number') {
      if (target.getBoundingClientRect) {
        var rect = target.getBoundingClientRect();
        x = rect.left + rect.width / 2;
        y = rect.top + rect.height / 2;
      } else {
        x = 0;
        y = 0;
      }
    }

    // Create transient rings without preventDefault, navigation delay, or HTMX interference
    createRings(x, y);
  }

  function onVisibilityChange() {
    if (document && document.hidden) {
      stopRaf();
      particles = [];
      clearCanvas();
    }
  }

  function removeActiveRings() {
    if (typeof document === 'undefined' || !document.querySelectorAll) return;
    var activeRings = document.querySelectorAll('.ink-ring-container');
    for (var i = 0; i < activeRings.length; i++) {
      var ring = activeRings[i];
      if (typeof ring.remove === 'function') {
        ring.remove();
      } else if (ring.parentNode) {
        ring.parentNode.removeChild(ring);
      }
    }
  }

  function onReducedMotionChange(e) {
    if (reducedMotionMql && e && typeof e.matches === 'boolean') {
      try {
        reducedMotionMql.matches = e.matches;
      } catch (err) {
        // ignore if read-only property in standard browser
      }
    }
    var matches = (e && typeof e.matches === 'boolean') ? e.matches : isReducedMotion();
    if (matches) {
      stopRaf();
      particles = [];
      clearCanvas();
      removeActiveRings();
    } else {
      if (!canvas) {
        setupCanvas();
      } else {
        if (!canvas.parentNode && document.body && document.body.appendChild) {
          document.body.appendChild(canvas);
        }
        resizeCanvas();
      }
    }
  }

  function init() {
    if (isInitialized) return;
    if (!isInkEnabled()) return;

    isInitialized = true;

    if (typeof window !== 'undefined' && window.matchMedia) {
      reducedMotionMql = window.matchMedia('(prefers-reduced-motion: reduce)');
      if (reducedMotionMql) {
        if (reducedMotionMql.addEventListener) {
          reducedMotionMql.addEventListener('change', onReducedMotionChange);
        } else if (reducedMotionMql.addListener) {
          reducedMotionMql.addListener(onReducedMotionChange);
        }
      }
    }

    setupCanvas();

    if (typeof document !== 'undefined' && document.addEventListener) {
      document.addEventListener('pointermove', onPointerMove, { passive: true });
      document.addEventListener('pointerdown', onPointerDown, { passive: true });
      document.addEventListener('visibilitychange', onVisibilityChange);
    }
  }

  function cleanup() {
    stopRaf();
    particles = [];
    clearCanvas();
    removeActiveRings();
    if (canvas) {
      if (typeof canvas.remove === 'function') {
        canvas.remove();
      } else if (canvas.parentNode) {
        canvas.parentNode.removeChild(canvas);
      }
    }
    canvas = null;
    ctx = null;
    lastEmitX = -9999;
    lastEmitY = -9999;
    lastEmitTime = 0;
    if (typeof document !== 'undefined' && document.removeEventListener) {
      document.removeEventListener('pointermove', onPointerMove);
      document.removeEventListener('pointerdown', onPointerDown);
      document.removeEventListener('visibilitychange', onVisibilityChange);
    }
    if (isResizeBound && typeof window !== 'undefined' && window.removeEventListener) {
      window.removeEventListener('resize', resizeCanvas);
      isResizeBound = false;
    }
    if (reducedMotionMql) {
      if (reducedMotionMql.removeEventListener) {
        reducedMotionMql.removeEventListener('change', onReducedMotionChange);
      } else if (reducedMotionMql.removeListener) {
        reducedMotionMql.removeListener(onReducedMotionChange);
      }
      reducedMotionMql = null;
    }
    isInitialized = false;
  }

  var InkBleed = {
    init: init,
    cleanup: cleanup,
    spawnParticle: spawnParticle,
    createRings: createRings,
    renderLoop: renderLoop,
    isInkEnabled: isInkEnabled,
    isReducedMotion: isReducedMotion,
    getState: function () {
      return {
        isInitialized: isInitialized,
        particles: particles,
        particleCount: particles.length,
        rafId: rafId,
        canvas: canvas,
        dpr: dpr,
        reducedMotionMql: reducedMotionMql,
        isResizeBound: isResizeBound,
        maxParticles: MAX_PARTICLES,
        maxAlpha: MAX_ALPHA,
        ringContainerLifetimeMs: RING_CONTAINER_LIFETIME_MS,
        ringAnimationDurationMs: RING_ANIMATION_DURATION_MS,
        ringMaxDelayMs: RING_MAX_DELAY_MS,
        ringColorTokens: RING_COLOR_TOKENS.slice()
      };
    }
  };

  if (typeof window !== 'undefined') {
    window.InkBleed = InkBleed;
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', init);
    } else {
      init();
    }
  }

  if (typeof module !== 'undefined' && module.exports) {
    module.exports = InkBleed;
  }
})();
