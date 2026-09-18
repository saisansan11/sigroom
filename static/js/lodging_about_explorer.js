/**
 * UX-17 Dormitory Showcase — Floor Explorer
 * Self-hosted, vanilla JS. No React, no external CDN, no WebGL.
 * Generates an SVG isometric-style floor plan inside #lka-iso-scene.
 *
 * Behaviour:
 *  - Floor 4 / Floor 5 toggle
 *  - Drag / touch rotation
 *  - Arrow key rotation, +/- zoom
 *  - Filter: All / Air / Fan / Facilities
 *  - Room click → detail panel
 *  - Reduced-motion: no auto-rotate; manual controls still work
 *  - No continuous idle loop when not interacting
 */

(function () {
  'use strict';

  /* ─── Constants ─────────────────────────────────────────────── */
  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  // Floor 4 room data
  function buildFloor4Rooms() {
    const rooms = [];
    // Air: 401-407
    for (let n = 401; n <= 407; n++) rooms.push({ num: n, floor: 4, cooling: 'air', capacity: 2 });
    // Non-lodging 408,409,410 — excluded from inventory, not rendered as bookable
    // Air: 411-416
    for (let n = 411; n <= 416; n++) rooms.push({ num: n, floor: 4, cooling: 'air', capacity: 2 });
    // Fan: 417-448
    for (let n = 417; n <= 448; n++) rooms.push({ num: n, floor: 4, cooling: 'fan', capacity: 2 });
    // Air: 449-460
    for (let n = 449; n <= 460; n++) rooms.push({ num: n, floor: 4, cooling: 'air', capacity: 2 });
    return rooms;
  }

  function buildFloor5Rooms() {
    const rooms = [];
    for (let n = 501; n <= 530; n++) rooms.push({ num: n, floor: 5, cooling: 'air', capacity: 4 });
    return rooms;
  }

  const FLOOR_DATA = {
    4: { rooms: buildFloor4Rooms(), label: 'ชั้น 4', cols: 14 },
    5: { rooms: buildFloor5Rooms(), label: 'ชั้น 5', cols: 10 },
  };

  // Facilities (not room numbers, just markers on the plan)
  const FACILITIES = [
    { label: 'ห้องน้ำ ฝั่ง A', type: 'facility' },
    { label: 'ห้องน้ำ ฝั่ง B', type: 'facility' },
    { label: 'ห้องอาบน้ำ', type: 'facility' },
  ];

  /* ─── State ──────────────────────────────────────────────────── */
  let currentFloor = 4;
  let currentFilter = 'all';
  let rotateX = 50;  // degrees for isometric tilt
  let rotateZ = 20;  // degrees for rotation
  let scale = 1;
  let isDragging = false;
  let lastX = 0;
  let lastY = 0;
  let renderScheduled = false;

  /* ─── DOM refs ───────────────────────────────────────────────── */
  const canvas = document.getElementById('lka-explorer-canvas');
  const scene = document.getElementById('lka-iso-scene');
  const panel = document.getElementById('lka-room-panel');
  const panelClose = document.getElementById('lka-panel-close');
  const panelNumber = document.getElementById('lka-panel-number');
  const panelFloor = document.getElementById('lka-panel-floor');
  const panelCooling = document.getElementById('lka-panel-cooling');
  const panelCapacity = document.getElementById('lka-panel-capacity');
  const zoomIn = document.getElementById('lka-zoom-in');
  const zoomOut = document.getElementById('lka-zoom-out');
  const resetBtn = document.getElementById('lka-reset');

  if (!canvas || !scene) return; // Guard: exit if elements not found

  /* ─── SVG floor plan generator ──────────────────────────────── */
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const ROOM_W = 38;
  const ROOM_H = 28;
  const GAP = 2;
  const HALLWAY_H = 24;

  function makeSVG(floor) {
    const data = FLOOR_DATA[floor];
    const rooms = data.rooms;
    const COLS = data.cols;

    // Layout: rooms above and below a central hallway
    const rows = Math.ceil(rooms.length / COLS);
    const svgW = COLS * (ROOM_W + GAP) + GAP;
    const svgH = rows * (ROOM_H + GAP) + HALLWAY_H + 2 * GAP + 30;

    const svg = document.createElementNS(SVG_NS, 'svg');
    svg.setAttribute('viewBox', `0 0 ${svgW} ${svgH}`);
    svg.setAttribute('width', svgW);
    svg.setAttribute('height', svgH);
    svg.setAttribute('role', 'img');
    svg.setAttribute('aria-label', `แผนผัง${data.label}`);
    svg.style.maxWidth = '100%';
    svg.style.height = 'auto';

    // Hallway
    const hallway = document.createElementNS(SVG_NS, 'rect');
    const hallwayY = Math.floor(rows / 2) * (ROOM_H + GAP) + GAP;
    hallway.setAttribute('x', String(GAP));
    hallway.setAttribute('y', String(hallwayY));
    hallway.setAttribute('width', String(svgW - 2 * GAP));
    hallway.setAttribute('height', String(HALLWAY_H));
    hallway.setAttribute('rx', '3');
    hallway.setAttribute('fill', 'oklch(.18 .018 243)');
    hallway.setAttribute('stroke', 'oklch(.31 .02 235)');
    hallway.setAttribute('stroke-width', '1');
    svg.appendChild(hallway);

    // Hallway label
    const hlabel = document.createElementNS(SVG_NS, 'text');
    hlabel.setAttribute('x', String(svgW / 2));
    hlabel.setAttribute('y', String(hallwayY + HALLWAY_H / 2));
    hlabel.setAttribute('dominant-baseline', 'middle');
    hlabel.setAttribute('text-anchor', 'middle');
    hlabel.setAttribute('fill', 'oklch(.59 .022 229)');
    hlabel.setAttribute('font-size', '9');
    hlabel.setAttribute('font-family', 'monospace');
    hlabel.setAttribute('pointer-events', 'none');
    hlabel.textContent = 'ทางเดิน / Corridor';
    svg.appendChild(hlabel);

    // Rooms
    rooms.forEach((room, i) => {
      const col = i % COLS;
      const row = Math.floor(i / COLS);
      const adjustedRow = row >= Math.floor(rows / 2) ? row + 1 : row;
      const x = col * (ROOM_W + GAP) + GAP;
      const y = adjustedRow * (ROOM_H + GAP) + GAP;

      const rect = document.createElementNS(SVG_NS, 'rect');
      rect.setAttribute('x', String(x));
      rect.setAttribute('y', String(y));
      rect.setAttribute('width', String(ROOM_W));
      rect.setAttribute('height', String(ROOM_H));
      rect.setAttribute('rx', '2');
      rect.setAttribute('class', `lka-room-block ${room.cooling}`);
      rect.setAttribute('tabindex', '0');
      rect.setAttribute('role', 'button');
      rect.setAttribute('aria-label', `ห้อง ${room.num} ${room.cooling === 'air' ? 'ปรับอากาศ' : 'พัดลม'} ชั้น ${room.floor} ${room.capacity} คน`);
      rect.dataset.num = room.num;
      rect.dataset.floor = room.floor;
      rect.dataset.cooling = room.cooling;
      rect.dataset.capacity = room.capacity;

      const label = document.createElementNS(SVG_NS, 'text');
      label.setAttribute('x', String(x + ROOM_W / 2));
      label.setAttribute('y', String(y + ROOM_H / 2));
      label.setAttribute('class', 'lka-room-label');
      label.textContent = String(room.num);

      // Events
      function selectRoom(e) {
        e.stopPropagation();
        document.querySelectorAll('.lka-room-block.selected').forEach(el => el.classList.remove('selected'));
        rect.classList.add('selected');
        showPanel(room);
      }
      rect.addEventListener('click', selectRoom);
      rect.addEventListener('keydown', e => {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); selectRoom(e); }
      });

      svg.appendChild(rect);
      svg.appendChild(label);
    });

    // Facilities (placed at the end of the plan) — rendered every time, filtered via applyFilter()
    FACILITIES.forEach((fac, fi) => {
      const x = fi * (ROOM_W + GAP) + GAP;
      const y = svgH - 28;
      const fr = document.createElementNS(SVG_NS, 'rect');
      fr.setAttribute('x', String(x));
      fr.setAttribute('y', String(y));
      fr.setAttribute('width', String(ROOM_W));
      fr.setAttribute('height', '22');
      fr.setAttribute('rx', '2');
      fr.setAttribute('class', 'lka-room-block facility');
      fr.setAttribute('aria-label', fac.label);
      fr.setAttribute('role', 'img');
      svg.appendChild(fr);

      const fl = document.createElementNS(SVG_NS, 'text');
      fl.setAttribute('x', String(x + ROOM_W / 2));
      fl.setAttribute('y', String(y + 11));
      fl.setAttribute('class', 'lka-room-label');
      fl.setAttribute('font-size', '7');
      fl.textContent = fac.label.slice(0, 5);
      svg.appendChild(fl);
    });

    // Non-lodging rooms note (floor 4 only)
    if (floor === 4) {
      const note = document.createElementNS(SVG_NS, 'text');
      note.setAttribute('x', String(GAP));
      note.setAttribute('y', String(svgH - 4));
      note.setAttribute('fill', 'oklch(.59 .022 229)');
      note.setAttribute('font-size', '7');
      note.setAttribute('font-family', 'monospace');
      note.textContent = '* 408, 409, 410 ไม่ใช่ห้องพักนักเรียน';
      svg.appendChild(note);
    }

    return svg;
  }

  /* ─── Render ─────────────────────────────────────────────────── */
  function applyTransform() {
    scene.style.transform = `rotateX(${rotateX}deg) rotateZ(${rotateZ}deg) scale(${scale})`;
  }

  function renderFloor() {
    scene.innerHTML = '';
    const svg = makeSVG(currentFloor);
    scene.appendChild(svg);
    applyFilter(currentFilter);
    injectLegend();
    updateAriaLabel();
    renderScheduled = false;
  }

  function scheduleRender() {
    if (!renderScheduled) {
      renderScheduled = true;
      requestAnimationFrame(renderFloor);
    }
  }

  function applyFilter(filter) {
    currentFilter = filter;
    const blocks = scene.querySelectorAll('.lka-room-block');
    blocks.forEach(b => {
      const isFacility = b.classList.contains('facility');
      const cooling = b.dataset.cooling;
      let isHidden = false;

      if (filter === 'all') {
        isHidden = false;
      } else if (filter === 'facility') {
        isHidden = !isFacility;
      } else {
        isHidden = isFacility || (cooling !== filter);
      }

      b.classList.toggle('hidden-filter', isHidden);

      if (isHidden) {
        b.setAttribute('tabindex', '-1');
        b.setAttribute('aria-hidden', 'true');
        if (b.classList.contains('selected')) {
          b.classList.remove('selected');
          closePanel();
        }
      } else {
        b.removeAttribute('aria-hidden');
        if (b.getAttribute('role') === 'button') {
          b.setAttribute('tabindex', '0');
        }
      }
    });
  }

  function updateAriaLabel() {
    const data = FLOOR_DATA[currentFloor];
    canvas.setAttribute('aria-label', `แผนผัง${data.label} อาคารที่พักนักเรียน โรงเรียนทหารสื่อสาร`);
  }

  function injectLegend() {
    let legend = canvas.parentElement.querySelector('.lka-legend');
    if (!legend) {
      legend = document.createElement('div');
      legend.className = 'lka-legend';
      legend.setAttribute('aria-hidden', 'true');
      canvas.parentElement.insertBefore(legend, canvas);
    }
    legend.innerHTML = `
      <span class="lka-legend-item"><span class="lka-legend-swatch lka-legend-swatch--air"></span>ปรับอากาศ</span>
      <span class="lka-legend-item"><span class="lka-legend-swatch lka-legend-swatch--fan"></span>พัดลม</span>
      <span class="lka-legend-item"><span class="lka-legend-swatch lka-legend-swatch--facility"></span>สิ่งอำนวยความสะดวก</span>
    `;
  }

  /* ─── Room detail panel ──────────────────────────────────────── */
  function showPanel(room) {
    panelNumber.textContent = `ห้อง ${room.num}`;
    panelFloor.textContent = `ชั้น ${room.floor}`;
    panelCooling.textContent = room.cooling === 'air' ? 'ปรับอากาศ' : 'พัดลม';
    panelCapacity.textContent = `${room.capacity} คน`;
    panel.hidden = false;
  }

  function closePanel() {
    panel.hidden = true;
    document.querySelectorAll('.lka-room-block.selected').forEach(el => el.classList.remove('selected'));
  }

  panelClose.addEventListener('click', closePanel);

  // Close panel on canvas background click
  canvas.addEventListener('click', e => {
    if (e.target === canvas || e.target === scene) closePanel();
  });

  /* ─── Floor toggle ───────────────────────────────────────────── */
  function switchFloor(floorNum) {
    currentFloor = parseInt(floorNum, 10);
    document.querySelectorAll('.lka-ftoggle').forEach(b => {
      const match = parseInt(b.dataset.floor, 10) === currentFloor;
      b.classList.toggle('active', match);
      b.setAttribute('aria-pressed', match ? 'true' : 'false');
    });
    closePanel();
    scheduleRender();
  }
  window.lkaSwitchFloor = switchFloor;

  document.querySelectorAll('.lka-ftoggle').forEach(btn => {
    btn.addEventListener('click', () => {
      switchFloor(btn.dataset.floor);
    });
  });

  // Room Experience cards / external floor switches
  document.querySelectorAll('[data-explorer-floor]').forEach(btn => {
    btn.addEventListener('click', () => {
      const targetFloor = btn.dataset.explorerFloor;
      if (targetFloor) {
        switchFloor(targetFloor);
      }
    });
  });

  /* ─── Filter buttons ─────────────────────────────────────────── */
  document.querySelectorAll('.lka-filter').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.lka-filter').forEach(b => {
        b.classList.remove('active');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('active');
      btn.setAttribute('aria-pressed', 'true');
      applyFilter(btn.dataset.filter);
    });
  });

  /* ─── Zoom controls ──────────────────────────────────────────── */
  function clampScale(v) { return Math.min(3, Math.max(0.4, v)); }

  zoomIn.addEventListener('click', () => { scale = clampScale(scale + 0.15); applyTransform(); });
  zoomOut.addEventListener('click', () => { scale = clampScale(scale - 0.15); applyTransform(); });
  resetBtn.addEventListener('click', () => {
    rotateX = 50; rotateZ = 20; scale = 1;
    applyTransform();
    closePanel();
  });

  /* ─── Drag rotation ──────────────────────────────────────────── */
  canvas.addEventListener('mousedown', e => {
    isDragging = true;
    lastX = e.clientX;
    lastY = e.clientY;
    e.preventDefault();
  });
  window.addEventListener('mousemove', e => {
    if (!isDragging) return;
    const dx = e.clientX - lastX;
    const dy = e.clientY - lastY;
    rotateZ = (rotateZ + dx * 0.4) % 360;
    rotateX = Math.min(85, Math.max(5, rotateX - dy * 0.3));
    lastX = e.clientX;
    lastY = e.clientY;
    applyTransform();
  });
  window.addEventListener('mouseup', () => { isDragging = false; });

  /* ─── Touch rotation ─────────────────────────────────────────── */
  let lastTouchX = 0;
  let lastTouchY = 0;
  canvas.addEventListener('touchstart', e => {
    if (e.touches.length === 1) {
      lastTouchX = e.touches[0].clientX;
      lastTouchY = e.touches[0].clientY;
    }
  }, { passive: true });
  canvas.addEventListener('touchmove', e => {
    if (e.touches.length === 1) {
      const dx = e.touches[0].clientX - lastTouchX;
      const dy = e.touches[0].clientY - lastTouchY;
      rotateZ = (rotateZ + dx * 0.5) % 360;
      rotateX = Math.min(85, Math.max(5, rotateX - dy * 0.35));
      lastTouchX = e.touches[0].clientX;
      lastTouchY = e.touches[0].clientY;
      applyTransform();
    }
  }, { passive: true });

  /* ─── Keyboard controls ──────────────────────────────────────── */
  canvas.addEventListener('keydown', e => {
    switch (e.key) {
      case 'ArrowLeft':  rotateZ = (rotateZ - 8) % 360; applyTransform(); e.preventDefault(); break;
      case 'ArrowRight': rotateZ = (rotateZ + 8) % 360; applyTransform(); e.preventDefault(); break;
      case 'ArrowUp':    rotateX = Math.min(85, rotateX + 8); applyTransform(); e.preventDefault(); break;
      case 'ArrowDown':  rotateX = Math.max(5, rotateX - 8); applyTransform(); e.preventDefault(); break;
      case '+':
      case '=':          scale = clampScale(scale + 0.15); applyTransform(); e.preventDefault(); break;
      case '-':
      case '_':          scale = clampScale(scale - 0.15); applyTransform(); e.preventDefault(); break;
      case 'r':
      case 'R':          rotateX = 50; rotateZ = 20; scale = 1; applyTransform(); e.preventDefault(); break;
      case 'Escape':     closePanel(); break;
    }
  });

  /* ─── Wheel zoom ─────────────────────────────────────────────── */
  canvas.addEventListener('wheel', e => {
    e.preventDefault();
    scale = clampScale(scale - e.deltaY * 0.001);
    applyTransform();
  }, { passive: false });

  /* ─── Initial render ─────────────────────────────────────────── */
  applyTransform();
  renderFloor();

})();
