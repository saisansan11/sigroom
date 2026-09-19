/**
 * UX-24 Lodging Isometric Explorer — visual polish and contextual inspection.
 * Self-hosted vanilla JS. No WebGL, no external CDN, no continuous animation loop.
 *
 * The old explorer rendered one flat SVG sheet and CSS-rotated the whole sheet.
 * UX-23 instead re-projects every room as an isometric cuboid with real top/front/
 * side faces. Camera changes rebuild the projection, so the result reads as an
 * architectural model rather than a spinning card.
 */

(function () {
  'use strict';

  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const ISO_X = 0.8660254;
  const ISO_Y = 0.48;

  const ROOM_W = 46;
  const ROOM_D = 32;
  const ROOM_H = 18;
  const GAP = 6;
  const BASE_H = 8;
  const CORRIDOR_H = 2;
  const FACILITY_W = 66;
  const FACILITY_D = 32;
  const FACILITY_H = 14;
  const MODEL_MARGIN = 58;

  function buildFloor4Rooms() {
    const rooms = [];
    for (let n = 401; n <= 407; n++) rooms.push({ num: n, floor: 4, cooling: 'air', capacity: 2 });
    for (let n = 411; n <= 416; n++) rooms.push({ num: n, floor: 4, cooling: 'air', capacity: 2 });
    for (let n = 417; n <= 448; n++) rooms.push({ num: n, floor: 4, cooling: 'fan', capacity: 2 });
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

  const FACILITIES = [
    { label: 'ห้องน้ำ ฝั่ง A', type: 'facility' },
    { label: 'ห้องน้ำ ฝั่ง B', type: 'facility' },
    { label: 'ห้องอาบน้ำ', type: 'facility' },
  ];

  let currentFloor = 4;
  let currentFilter = 'all';
  let viewQuarter = 0;
  let scale = 1;
  let selectedRoomNumber = null;
  let renderScheduled = false;
  let isDragging = false;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragCommitted = false;
  let lastTouchX = 0;
  let lastTouchY = 0;
  let touchCommitted = false;

  const canvas = document.getElementById('lka-explorer-canvas');
  const scene = document.getElementById('lka-iso-scene');
  const panel = document.getElementById('lka-room-panel');
  const panelClose = document.getElementById('lka-panel-close');
  const panelNumber = document.getElementById('lka-panel-number');
  const panelFloor = document.getElementById('lka-panel-floor');
  const panelCooling = document.getElementById('lka-panel-cooling');
  const panelCapacity = document.getElementById('lka-panel-capacity');
  const panelStatus = document.getElementById('lka-panel-status');
  const zoomIn = document.getElementById('lka-zoom-in');
  const zoomOut = document.getElementById('lka-zoom-out');
  const resetBtn = document.getElementById('lka-reset');
  const viewLeft = document.getElementById('lka-view-left');
  const viewRight = document.getElementById('lka-view-right');
  const modelFloor = document.getElementById('lka-model-floor');
  const modelView = document.getElementById('lka-model-view');
  const modelSelection = document.getElementById('lka-model-selection');

  if (!canvas || !scene || !panel || !panelClose) return;

  function svgEl(tag, attrs = {}) {
    const el = document.createElementNS(SVG_NS, tag);
    Object.entries(attrs).forEach(([key, value]) => el.setAttribute(key, String(value)));
    return el;
  }

  function appendLinearGradient(defs, id, colors, direction = 'diagonal') {
    const directions = {
      diagonal: ['0%', '0%', '100%', '100%'],
      vertical: ['0%', '0%', '0%', '100%'],
      reverse: ['100%', '0%', '0%', '100%'],
    };
    const [x1, y1, x2, y2] = directions[direction];
    const gradient = svgEl('linearGradient', { id, x1, y1, x2, y2 });
    colors.forEach(([offset, color]) => {
      gradient.appendChild(svgEl('stop', { offset, 'stop-color': color }));
    });
    defs.appendChild(gradient);
  }

  function appendModelDefs(svg) {
    const defs = svgEl('defs');
    [
      ['lka-air-top', [['0%', '#f4fcff'], ['58%', '#d8f3ff'], ['100%', '#b7e4f8']], 'diagonal'],
      ['lka-air-x', [['0%', '#7cc8e8'], ['100%', '#318fba']], 'vertical'],
      ['lka-air-y', [['0%', '#b9e7f8'], ['100%', '#67b8d9']], 'reverse'],
      ['lka-fan-top', [['0%', '#fffaf0'], ['58%', '#ffedb7'], ['100%', '#f5cf6c']], 'diagonal'],
      ['lka-fan-x', [['0%', '#e1b249'], ['100%', '#b97912']], 'vertical'],
      ['lka-fan-y', [['0%', '#f5d787'], ['100%', '#d79f2b']], 'reverse'],
      ['lka-facility-top', [['0%', '#effdf9'], ['100%', '#b7eee3']], 'diagonal'],
      ['lka-facility-x', [['0%', '#68cbbb'], ['100%', '#258e83']], 'vertical'],
      ['lka-facility-y', [['0%', '#a8e8dc'], ['100%', '#54b7a8']], 'reverse'],
      ['lka-base-top', [['0%', '#ffffff'], ['100%', '#e7eef3']], 'diagonal'],
      ['lka-base-x', [['0%', '#cfdae3'], ['100%', '#9fb0be']], 'vertical'],
      ['lka-base-y', [['0%', '#e5edf3'], ['100%', '#b9c8d3']], 'reverse'],
      ['lka-corridor-top', [['0%', '#ffffff'], ['100%', '#eaf1f5']], 'diagonal'],
    ].forEach(([id, colors, direction]) => appendLinearGradient(defs, id, colors, direction));
    svg.appendChild(defs);
  }

  function orientPoint(x, y, worldW, worldD) {
    switch (viewQuarter) {
      case 1: return [y, worldW - x];
      case 2: return [worldW - x, worldD - y];
      case 3: return [worldD - y, x];
      default: return [x, y];
    }
  }

  function rawProject(x, y, z, worldW, worldD) {
    const [rx, ry] = orientPoint(x, y, worldW, worldD);
    return {
      x: (rx - ry) * ISO_X,
      y: (rx + ry) * ISO_Y - z,
    };
  }

  function createProjector(worldW, worldD, maxZ) {
    const samples = [];
    [[0, 0], [worldW, 0], [worldW, worldD], [0, worldD]].forEach(([x, y]) => {
      samples.push(rawProject(x, y, 0, worldW, worldD));
      samples.push(rawProject(x, y, maxZ, worldW, worldD));
    });
    const xs = samples.map(p => p.x);
    const ys = samples.map(p => p.y);
    const minX = Math.min(...xs);
    const maxX = Math.max(...xs);
    const minY = Math.min(...ys);
    const maxY = Math.max(...ys);
    const width = maxX - minX + MODEL_MARGIN * 2;
    const height = maxY - minY + MODEL_MARGIN * 2;
    return {
      width,
      height,
      project(x, y, z) {
        const p = rawProject(x, y, z, worldW, worldD);
        return { x: p.x - minX + MODEL_MARGIN, y: p.y - minY + MODEL_MARGIN };
      },
    };
  }

  function points(pointsList) {
    return pointsList.map(p => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(' ');
  }

  function cuboidFaces(project, x, y, w, d, z, h) {
    const b00 = project(x, y, z);
    const b10 = project(x + w, y, z);
    const b11 = project(x + w, y + d, z);
    const b01 = project(x, y + d, z);
    const t00 = project(x, y, z + h);
    const t10 = project(x + w, y, z + h);
    const t11 = project(x + w, y + d, z + h);
    const t01 = project(x, y + d, z + h);
    return {
      top: [t00, t10, t11, t01],
      sideX: [b10, b11, t11, t10],
      sideY: [b01, b11, t11, t01],
      center: project(x + w / 2, y + d / 2, z + h + 0.5),
    };
  }

  function modelDepth(x, y, w, d, worldW, worldD) {
    const [rx, ry] = orientPoint(x + w / 2, y + d / 2, worldW, worldD);
    return rx + ry;
  }

  function appendCuboid(parent, faces, className) {
    const sideY = svgEl('polygon', { points: points(faces.sideY), class: `${className}-face ${className}-face--y` });
    const sideX = svgEl('polygon', { points: points(faces.sideX), class: `${className}-face ${className}-face--x` });
    const top = svgEl('polygon', { points: points(faces.top), class: `${className}-top` });
    parent.appendChild(sideY);
    parent.appendChild(sideX);
    parent.appendChild(top);
    return top;
  }

  function roomLayout(data) {
    const rooms = data.rooms;
    const rows = Math.ceil(rooms.length / data.cols);
    const hallwayRow = Math.floor(rows / 2);
    const stepX = ROOM_W + GAP;
    const stepY = ROOM_D + GAP;
    const roomItems = rooms.map((room, index) => {
      const col = index % data.cols;
      const row = Math.floor(index / data.cols);
      const adjustedRow = row >= hallwayRow ? row + 1 : row;
      return {
        room,
        x: GAP + col * stepX,
        y: GAP + adjustedRow * stepY,
      };
    });
    const worldW = GAP * 2 + data.cols * stepX - GAP;
    const facilityY = GAP + (rows + 1) * stepY + GAP;
    const facilitiesWidth = FACILITIES.length * (FACILITY_W + GAP) - GAP;
    const worldD = facilityY + FACILITY_D + GAP;
    return {
      roomItems,
      rows,
      hallwayRow,
      hallwayY: GAP + hallwayRow * stepY,
      worldW: Math.max(worldW, facilitiesWidth + GAP * 2),
      worldD,
      facilityY,
    };
  }

  function makeSVG(floor) {
    const data = FLOOR_DATA[floor];
    const layout = roomLayout(data);
    const { roomItems, hallwayY, worldW, worldD, facilityY } = layout;
    const projector = createProjector(worldW, worldD, BASE_H + ROOM_H + 6);
    const project = projector.project;

    const svg = svgEl('svg', {
      viewBox: `0 0 ${projector.width.toFixed(1)} ${projector.height.toFixed(1)}`,
      role: 'group',
      'aria-label': `โมเดลจำลองสามมิติ ${data.label}`,
      class: 'lka-iso-svg',
      preserveAspectRatio: 'xMidYMid meet',
    });

    appendModelDefs(svg);

    const ambient = svgEl('ellipse', {
      cx: projector.width / 2,
      cy: projector.height - 30,
      rx: Math.max(105, projector.width * 0.39),
      ry: 22,
      class: 'lka-model-ambient',
      'aria-hidden': 'true',
    });
    svg.appendChild(ambient);

    const shadow = svgEl('ellipse', {
      cx: projector.width / 2,
      cy: projector.height - 24,
      rx: Math.max(90, projector.width * 0.34),
      ry: 16,
      class: 'lka-model-ground-shadow',
    });
    svg.appendChild(shadow);

    const baseGroup = svgEl('g', { class: 'lka-building-base' });
    const baseFaces = cuboidFaces(project, 0, 0, worldW, worldD, 0, BASE_H);
    appendCuboid(baseGroup, baseFaces, 'lka-base');
    svg.appendChild(baseGroup);

    const corridor = svgEl('g', { class: 'lka-corridor-model' });
    const corridorFaces = cuboidFaces(
      project,
      GAP,
      hallwayY,
      worldW - GAP * 2,
      ROOM_D,
      BASE_H,
      CORRIDOR_H,
    );
    appendCuboid(corridor, corridorFaces, 'lka-corridor');
    svg.appendChild(corridor);

    const orderedRooms = roomItems
      .map(item => ({ ...item, depth: modelDepth(item.x, item.y, ROOM_W, ROOM_D, worldW, worldD) }))
      .sort((a, b) => a.depth - b.depth);

    orderedRooms.forEach(({ room, x, y }) => {
      const isSelected = selectedRoomNumber === room.num;
      const group = svgEl('g', {
        class: `lka-room-model ${room.cooling}${isSelected ? ' selected' : ''}`,
        'data-room': room.num,
        'data-cooling': room.cooling,
      });
      group.dataset.num = room.num;
      group.dataset.floor = room.floor;
      group.dataset.cooling = room.cooling;
      group.dataset.capacity = room.capacity;

      const faces = cuboidFaces(project, x, y, ROOM_W, ROOM_D, BASE_H + CORRIDOR_H, ROOM_H);
      const sideY = svgEl('polygon', { points: points(faces.sideY), class: 'lka-room-face lka-room-face--y' });
      const sideX = svgEl('polygon', { points: points(faces.sideX), class: 'lka-room-face lka-room-face--x' });
      const top = svgEl('polygon', {
        points: points(faces.top),
        class: `lka-room-block ${room.cooling}`,
        tabindex: '0',
        role: 'button',
        'aria-pressed': isSelected ? 'true' : 'false',
        'aria-label': `ห้อง ${room.num} ${room.cooling === 'air' ? 'ปรับอากาศ' : 'พัดลม'} ชั้น ${room.floor} ${room.capacity} คน`,
      });
      top.dataset.num = room.num;
      top.dataset.floor = room.floor;
      top.dataset.cooling = room.cooling;
      top.dataset.capacity = room.capacity;

      const label = svgEl('text', {
        x: faces.center.x,
        y: faces.center.y,
        class: 'lka-room-label',
      });
      label.textContent = String(room.num);

      const accent = svgEl('line', {
        x1: faces.top[0].x + (faces.top[1].x - faces.top[0].x) * 0.18,
        y1: faces.top[0].y + (faces.top[1].y - faces.top[0].y) * 0.18,
        x2: faces.top[0].x + (faces.top[1].x - faces.top[0].x) * 0.58,
        y2: faces.top[0].y + (faces.top[1].y - faces.top[0].y) * 0.58,
        class: 'lka-room-accent',
      });

      function selectRoom(event) {
        event.stopPropagation();
        selectedRoomNumber = room.num;
        scene.querySelectorAll('.lka-room-model.selected').forEach(el => {
          el.classList.remove('selected');
          const control = el.querySelector('.lka-room-block');
          if (control) control.setAttribute('aria-pressed', 'false');
        });
        group.classList.add('selected');
        top.setAttribute('aria-pressed', 'true');
        scene.classList.add('has-selection');
        showPanel(room);
      }

      top.addEventListener('click', selectRoom);
      top.addEventListener('keydown', event => {
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault();
          selectRoom(event);
        }
      });

      group.appendChild(sideY);
      group.appendChild(sideX);
      group.appendChild(top);
      group.appendChild(accent);
      group.appendChild(label);
      svg.appendChild(group);
    });

    FACILITIES.forEach((facility, index) => {
      const x = GAP + index * (FACILITY_W + GAP);
      const group = svgEl('g', {
        class: 'lka-facility-model facility',
        'data-cooling': 'facility',
        'aria-label': facility.label,
      });
      const faces = cuboidFaces(project, x, facilityY, FACILITY_W, FACILITY_D, BASE_H + CORRIDOR_H, FACILITY_H);
      appendCuboid(group, faces, 'lka-facility');
      const label = svgEl('text', {
        x: faces.center.x,
        y: faces.center.y,
        class: 'lka-facility-label',
      });
      label.textContent = facility.label;
      group.appendChild(label);
      svg.appendChild(group);
    });

    const badge = svgEl('g', { class: 'lka-svg-floor-badge', 'aria-hidden': 'true' });
    const badgeRect = svgEl('rect', { x: 18, y: 18, width: 118, height: 28, rx: 14 });
    const badgeText = svgEl('text', { x: 77, y: 36, 'text-anchor': 'middle' });
    badgeText.textContent = `${data.label} · ISOMETRIC`;
    badge.appendChild(badgeRect);
    badge.appendChild(badgeText);
    svg.appendChild(badge);

    if (floor === 4) {
      const note = svgEl('text', {
        x: 20,
        y: projector.height - 14,
        class: 'lka-svg-note',
      });
      note.textContent = '* 408, 409, 410 ไม่ใช่ห้องพักนักเรียน';
      svg.appendChild(note);
    }

    return svg;
  }

  function applyTransform() {
    scene.style.transform = `scale(${scale})`;
  }

  function updateViewStatus() {
    if (modelFloor) modelFloor.textContent = `ชั้น ${currentFloor}`;
    if (modelView) modelView.textContent = `มุมมอง ${viewQuarter + 1}/4`;
  }

  function renderFloor() {
    const activeRoomControl = document.activeElement?.closest?.('.lka-room-block');
    const focusedRoomNumber = activeRoomControl?.dataset?.num || null;

    scene.innerHTML = '';
    scene.appendChild(makeSVG(currentFloor));
    scene.classList.toggle('has-selection', selectedRoomNumber !== null);
    applyFilter(currentFilter);
    injectLegend();
    updateAriaLabel();
    updateViewStatus();
    applyTransform();

    if (focusedRoomNumber) {
      const replacement = scene.querySelector(`.lka-room-block[data-num="${focusedRoomNumber}"]`);
      if (replacement && replacement.getAttribute('tabindex') !== '-1') {
        replacement.focus({ preventScroll: true });
      }
    }

    renderScheduled = false;
  }

  function scheduleRender() {
    if (renderScheduled) return;
    renderScheduled = true;
    if (REDUCED_MOTION) {
      renderFloor();
    } else {
      requestAnimationFrame(renderFloor);
    }
  }

  function applyFilter(filter) {
    currentFilter = filter;
    scene.querySelectorAll('.lka-room-model, .lka-facility-model').forEach(model => {
      const isFacility = model.classList.contains('lka-facility-model');
      const cooling = model.dataset.cooling;
      let hidden = false;
      if (filter === 'facility') hidden = !isFacility;
      else if (filter !== 'all') hidden = isFacility || cooling !== filter;

      model.classList.toggle('hidden-filter', hidden);
      model.setAttribute('aria-hidden', hidden ? 'true' : 'false');
      const b = model.querySelector('.lka-room-block');
      if (b) {
        if (hidden) {
          b.setAttribute('tabindex', '-1');
          b.setAttribute('aria-hidden', 'true');
        } else {
          b.setAttribute('tabindex', '0');
          b.removeAttribute('aria-hidden');
        }
      }
      if (hidden && model.classList.contains('selected')) closePanel();
    });
  }

  function updateAriaLabel() {
    canvas.setAttribute(
      'aria-label',
      `โมเดลจำลองสามมิติ ${FLOOR_DATA[currentFloor].label} อาคารที่พักนักเรียน โรงเรียนทหารสื่อสาร`,
    );
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

  function showPanel(room) {
    panelNumber.textContent = `ห้อง ${room.num}`;
    panelFloor.textContent = `ชั้น ${room.floor}`;
    panelCooling.textContent = room.cooling === 'air' ? 'ปรับอากาศ' : 'พัดลม';
    panelCapacity.textContent = `${room.capacity} คน`;
    panel.dataset.state = 'selected';
    panel.classList.add('has-selection');
    if (panelStatus) {
      panelStatus.textContent = [panelNumber.textContent, panelFloor.textContent, panelCooling.textContent, panelCapacity.textContent].join(', ');
    }
    if (modelSelection) {
      modelSelection.textContent = `เลือกห้อง ${room.num}`;
      modelSelection.hidden = false;
    }
  }

  function closePanel({ restoreFocus = false } = {}) {
    const roomToRestore = selectedRoomNumber;
    selectedRoomNumber = null;
    panel.dataset.state = 'empty';
    panel.classList.remove('has-selection');
    scene.classList.remove('has-selection');
    scene.querySelectorAll('.lka-room-model.selected').forEach(el => {
      el.classList.remove('selected');
      const control = el.querySelector('.lka-room-block');
      if (control) control.setAttribute('aria-pressed', 'false');
    });
    if (panelStatus) panelStatus.textContent = '';
    if (modelSelection) {
      modelSelection.textContent = '';
      modelSelection.hidden = true;
    }
    if (restoreFocus) {
      const control = roomToRestore === null
        ? null
        : scene.querySelector(`.lka-room-block[data-num="${roomToRestore}"]`);
      if (control && control.getAttribute('tabindex') !== '-1') {
        control.focus({ preventScroll: true });
      } else {
        canvas.focus({ preventScroll: true });
      }
    }
  }

  panelClose.addEventListener('click', () => closePanel({ restoreFocus: true }));
  canvas.addEventListener('click', event => {
    if (event.target === canvas || event.target === scene) closePanel();
  });

  function switchFloor(floorNum) {
    currentFloor = parseInt(floorNum, 10);
    document.querySelectorAll('.lka-ftoggle').forEach(button => {
      const active = parseInt(button.dataset.floor, 10) === currentFloor;
      button.classList.toggle('active', active);
      button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    closePanel();
    scheduleRender();
  }
  window.lkaSwitchFloor = switchFloor;

  document.querySelectorAll('.lka-ftoggle').forEach(button => {
    button.addEventListener('click', () => switchFloor(button.dataset.floor));
  });

  document.querySelectorAll('[data-explorer-floor]').forEach(button => {
    button.addEventListener('click', () => {
      const targetFloor = button.dataset.explorerFloor;
      if (targetFloor) switchFloor(targetFloor);
    });
  });

  document.querySelectorAll('.lka-filter').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.lka-filter').forEach(candidate => {
        candidate.classList.remove('active');
        candidate.setAttribute('aria-pressed', 'false');
      });
      button.classList.add('active');
      button.setAttribute('aria-pressed', 'true');
      applyFilter(button.dataset.filter);
    });
  });

  function clampScale(value) {
    return Math.min(1.7, Math.max(0.7, value));
  }

  function rotateView(delta) {
    viewQuarter = (viewQuarter + delta + 4) % 4;
    scheduleRender();
  }

  if (viewLeft) viewLeft.addEventListener('click', () => rotateView(-1));
  if (viewRight) viewRight.addEventListener('click', () => rotateView(1));
  if (zoomIn) zoomIn.addEventListener('click', () => { scale = clampScale(scale + 0.12); applyTransform(); });
  if (zoomOut) zoomOut.addEventListener('click', () => { scale = clampScale(scale - 0.12); applyTransform(); });
  if (resetBtn) {
    resetBtn.addEventListener('click', () => {
      viewQuarter = 0;
      scale = 1;
      scheduleRender();
    });
  }

  canvas.addEventListener('mousedown', event => {
    isDragging = true;
    dragCommitted = false;
    dragStartX = event.clientX;
    dragStartY = event.clientY;
  });

  window.addEventListener('mousemove', event => {
    if (!isDragging || dragCommitted) return;
    const dx = event.clientX - dragStartX;
    const dy = event.clientY - dragStartY;
    if (Math.abs(dx) >= 68 && Math.abs(dx) > Math.abs(dy) * 1.15) {
      rotateView(dx > 0 ? 1 : -1);
      dragCommitted = true;
    }
  });

  window.addEventListener('mouseup', () => {
    isDragging = false;
    dragCommitted = false;
  });

  canvas.addEventListener('touchstart', event => {
    if (event.touches.length !== 1) return;
    lastTouchX = event.touches[0].clientX;
    lastTouchY = event.touches[0].clientY;
    touchCommitted = false;
  }, { passive: true });

  canvas.addEventListener('touchmove', event => {
    if (event.touches.length !== 1 || touchCommitted) return;
    const dx = event.touches[0].clientX - lastTouchX;
    const dy = event.touches[0].clientY - lastTouchY;
    if (Math.abs(dx) >= 52 && Math.abs(dx) > Math.abs(dy) * 1.2) {
      rotateView(dx > 0 ? 1 : -1);
      touchCommitted = true;
    }
  }, { passive: true });

  canvas.addEventListener('keydown', event => {
    switch (event.key) {
      case 'ArrowLeft': rotateView(-1); event.preventDefault(); break;
      case 'ArrowRight': rotateView(1); event.preventDefault(); break;
      case 'ArrowUp': scale = clampScale(scale + 0.12); applyTransform(); event.preventDefault(); break;
      case 'ArrowDown': scale = clampScale(scale - 0.12); applyTransform(); event.preventDefault(); break;
      case '+':
      case '=': scale = clampScale(scale + 0.12); applyTransform(); event.preventDefault(); break;
      case '-':
      case '_': scale = clampScale(scale - 0.12); applyTransform(); event.preventDefault(); break;
      case 'r':
      case 'R': viewQuarter = 0; scale = 1; scheduleRender(); event.preventDefault(); break;
      case 'Escape': closePanel({ restoreFocus: true }); event.preventDefault(); break;
    }
  });

  document.addEventListener('keydown', event => {
    if (event.key !== 'Escape' || selectedRoomNumber === null) return;
    event.preventDefault();
    closePanel({ restoreFocus: true });
  });

  canvas.addEventListener('wheel', event => {
    if (!event.ctrlKey && !event.metaKey) return;
    event.preventDefault();
    scale = clampScale(scale - event.deltaY * 0.001);
    applyTransform();
  }, { passive: false });

  applyTransform();
  renderFloor();
})();
