(function () {
  "use strict";

  var card = document.getElementById("keycard");
  if (!card) return;

  var cassette = card.querySelector(".cassette");
  var packs = card.querySelectorAll(".cassette-tape-pack");
  var hubs = card.querySelectorAll(".cassette-reel-hub");
  var flipButton = document.getElementById("cassetteFlipBtn");
  var qrOpenButton = document.getElementById("cassetteQrOpenBtn");
  var qrDialog = document.getElementById("cassetteQrDialog");
  var qrCloseButton = document.getElementById("cassetteQrCloseBtn");
  var copyButton = document.getElementById("copyPassBtn");
  var copyStatus = document.getElementById("cassetteCopyStatus");
  if (!cassette || packs.length < 2 || hubs.length < 2) return;

  var motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
  var reducedMotion = motionQuery.matches;
  var MINR = 12;
  var MAXR = 40;
  var PLAY = 9;
  var FFWD = 140;
  var nightsTotal = Math.max(1, Number(card.dataset.nightsTotal) || 1);
  var nightsElapsed = Math.max(0, Math.min(nightsTotal, Number(card.dataset.nightsElapsed) || 0));
  var targetFraction = nightsElapsed / nightsTotal;
  var progress = Number(card.dataset.progress);
  if (card.dataset.progress !== undefined && card.dataset.progress.trim() !== "" && Number.isFinite(progress)) {
    targetFraction = clamp(progress, 0, 1);
  }
  var shownFraction = reducedMotion ? targetFraction : 0;
  var windElapsed = 0;
  var windFrom = shownFraction;
  var windDuration = reducedMotion ? 0 : 700 + Math.abs(targetFraction - shownFraction) * 1100;
  var hubLeftAngle = 0;
  var hubRightAngle = 0;
  var lastFrame = null;
  var rafId = 0;
  var flipped = false;
  var rotateX = 0;
  var rotateY = 0;
  var pointerState = null;
  var ignoreSyntheticClick = false;
  var inViewport = !("IntersectionObserver" in window);
  var qrOpen = false;

  function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
  }

  function radius(fraction) {
    fraction = clamp(fraction, 0, 1);
    return Math.sqrt(MINR * MINR + (MAXR * MAXR - MINR * MINR) * fraction);
  }

  function renderTape() {
    var leftRadius = radius(1 - shownFraction);
    var rightRadius = radius(shownFraction);
    packs[0].setAttribute("transform", "scale(" + (leftRadius / MAXR).toFixed(4) + ")");
    packs[1].setAttribute("transform", "scale(" + (rightRadius / MAXR).toFixed(4) + ")");
    hubs[0].setAttribute("transform", "rotate(" + hubLeftAngle.toFixed(2) + ")");
    hubs[1].setAttribute("transform", "rotate(" + hubRightAngle.toFixed(2) + ")");
    return [leftRadius, rightRadius];
  }

  function applyCassetteTransform() {
    var baseY = flipped ? 180 : 0;
    cassette.style.transform = "rotateX(" + rotateX.toFixed(2) + "deg) rotateY(" + (baseY + rotateY).toFixed(2) + "deg)";
    card.style.setProperty("--light-x", (30 + rotateY * .65).toFixed(2) + "%");
    card.style.setProperty("--shadow-x", (rotateY * -.15).toFixed(2) + "px");
  }

  function shouldAnimate() {
    return !reducedMotion && !flipped && !qrOpen && inViewport && !document.hidden;
  }

  function stopLoop() {
    if (rafId) {
      window.cancelAnimationFrame(rafId);
      rafId = 0;
    }
    lastFrame = null;
  }

  function tick(now) {
    rafId = 0;
    if (!shouldAnimate()) {
      lastFrame = null;
      return;
    }

    var dt = lastFrame === null ? 0 : Math.min(0.05, (now - lastFrame) / 1000);
    lastFrame = now;
    var speed = PLAY;

    if (shownFraction !== targetFraction) {
      windElapsed += dt * 1000;
      var k = windDuration <= 0 ? 1 : clamp(windElapsed / windDuration, 0, 1);
      var eased = 1 - Math.pow(1 - k, 3);
      shownFraction = windFrom + (targetFraction - windFrom) * eased;
      speed = FFWD * Math.sign(targetFraction - windFrom || 1);
      if (k >= 1) shownFraction = targetFraction;
    }

    var radii = renderTape();
    var degrees = 180 / Math.PI;
    hubLeftAngle += (speed / radii[0]) * degrees * dt;
    hubRightAngle += (speed / radii[1]) * degrees * dt;
    renderTape();
    rafId = window.requestAnimationFrame(tick);
  }

  function startLoop() {
    if (!shouldAnimate() || rafId) return;
    lastFrame = null;
    rafId = window.requestAnimationFrame(tick);
  }

  function syncFlipUi() {
    card.classList.toggle("is-flipped", flipped);
    card.setAttribute("aria-pressed", flipped ? "true" : "false");
    card.setAttribute(
      "aria-label",
      flipped
        ? card.dataset.backLabel || "บัตรกำลังแสดงด้าน QR สำหรับรายงานตัว กดเพื่อพลิกกลับดูด้านหน้า"
        : card.dataset.frontLabel || "บัตรกำลังแสดงด้านหน้า กดเพื่อพลิกดู QR สำหรับรายงานตัว"
    );
    if (flipButton) {
      flipButton.textContent = flipped ? "พลิกกลับด้านหน้า" : card.dataset.flipLabel || "พลิกดู QR เช็กอิน";
    }
  }

  function setFlip(next) {
    flipped = Boolean(next);
    rotateX = 0;
    rotateY = 0;
    applyCassetteTransform();
    syncFlipUi();
    if (flipped) stopLoop();
    else startLoop();
  }

  function toggleFlip() {
    setFlip(!flipped);
  }

  function pointerDown(event) {
    if (event.isPrimary === false || event.button !== 0) return;
    pointerState = { x: event.clientX, y: event.clientY, moved: false, pointerId: event.pointerId };
    cassette.classList.add("is-dragging");
    if (card.setPointerCapture) {
      try { card.setPointerCapture(event.pointerId); } catch (error) { /* pointer capture is optional */ }
    }
  }

  function pointerMove(event) {
    if (!pointerState || pointerState.pointerId !== event.pointerId) return;
    var dx = event.clientX - pointerState.x;
    var dy = event.clientY - pointerState.y;
    if (Math.abs(dx) + Math.abs(dy) > 6) pointerState.moved = true;
    if (flipped || reducedMotion) return;
    rotateY = clamp(dx * 0.25, -26, 26);
    rotateX = clamp(-dy * 0.2, -16, 16);
    applyCassetteTransform();
  }

  function pointerEnd(event) {
    if (!pointerState || pointerState.pointerId !== event.pointerId) return;
    var wasTap = event.type === "pointerup" && !pointerState.moved;
    pointerState = null;
    cassette.classList.remove("is-dragging");
    rotateX = 0;
    rotateY = 0;
    applyCassetteTransform();
    if (wasTap) {
      ignoreSyntheticClick = true;
      toggleFlip();
      window.setTimeout(function () { ignoreSyntheticClick = false; }, 0);
    }
  }

  card.addEventListener("pointerdown", pointerDown);
  card.addEventListener("pointermove", pointerMove);
  card.addEventListener("pointerup", pointerEnd);
  card.addEventListener("pointercancel", pointerEnd);
  card.addEventListener("lostpointercapture", pointerEnd);
  card.addEventListener("click", function (event) {
    if (ignoreSyntheticClick) return;
    if (event.detail === 0) toggleFlip();
  });
  card.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " " || event.key === "Spacebar") {
      event.preventDefault();
      toggleFlip();
    }
  });

  if (flipButton) {
    flipButton.addEventListener("click", toggleFlip);
  }

  if (qrDialog && qrOpenButton) {
    qrOpenButton.addEventListener("click", function () {
      if (typeof qrDialog.showModal === "function") qrDialog.showModal();
      else qrDialog.setAttribute("open", "");
      qrOpen = true;
      stopLoop();
    });
    qrDialog.addEventListener("close", resumeAfterQr);
  }
  function resumeAfterQr() {
    qrOpen = false;
    qrOpenButton.focus();
    startLoop();
  }
  if (qrDialog && qrCloseButton) {
    qrCloseButton.addEventListener("click", function () {
      if (typeof qrDialog.close === "function") qrDialog.close();
      else {
        qrDialog.removeAttribute("open");
        resumeAfterQr();
      }
    });
  }

  if (copyButton) {
    copyButton.addEventListener("click", function () {
      var url = copyButton.dataset.passUrl || window.location.href;
      if (url.charAt(0) === "/") url = new URL(url, window.location.href).href;
      if (!navigator.clipboard || !navigator.clipboard.writeText) {
        if (copyStatus) copyStatus.textContent = "ไม่สามารถคัดลอกอัตโนมัติได้ กรุณาคัดลอก URL จากแถบเบราว์เซอร์";
        return;
      }
      navigator.clipboard.writeText(url).then(function () {
        if (copyStatus) copyStatus.textContent = "คัดลอกลิงก์บัตรแล้ว";
        copyButton.classList.add("is-copied");
        window.setTimeout(function () { copyButton.classList.remove("is-copied"); }, 2200);
      }).catch(function () {
        if (copyStatus) copyStatus.textContent = "ไม่สามารถคัดลอกอัตโนมัติได้ กรุณาคัดลอก URL จากแถบเบราว์เซอร์";
      });
    });
  }

  document.addEventListener("visibilitychange", function () {
    if (document.hidden) stopLoop();
    else startLoop();
  });

  function handleMotionPreference(event) {
    reducedMotion = event.matches;
    if (reducedMotion) {
      stopLoop();
      shownFraction = targetFraction;
      renderTape();
      rotateX = 0;
      rotateY = 0;
      applyCassetteTransform();
    } else {
      startLoop();
    }
  }
  if (motionQuery.addEventListener) motionQuery.addEventListener("change", handleMotionPreference);

  if ("IntersectionObserver" in window) {
    new IntersectionObserver(function (entries) {
      inViewport = entries[0].isIntersecting;
      if (inViewport) startLoop();
      else stopLoop();
    }).observe(card);
  }

  syncFlipUi();
  if (reducedMotion) {
    shownFraction = targetFraction;
    renderTape();
  } else {
    shownFraction = 0;
    windFrom = 0;
    windElapsed = 0;
    renderTape();
    startLoop();
  }
})();
