/**
 * UX-27 Lodging Explorer — plan-derived positions and selected-room elevation.
 * Self-hosted vanilla JS. No WebGL, no external CDN, no continuous animation loop.
 *
 * Starts overhead, with an optional isometric camera. Room coordinates follow
 * the supplied floor plans; inventory membership does not determine placement.
 */

(function () {
  'use strict';

  const REDUCED_MOTION = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const SVG_NS = 'http://www.w3.org/2000/svg';
  const ISO_X = 0.8660254;
  const ISO_Y = 0.48;

  const ROOM_H = 3;
  const BASE_H = 9;
  const CORRIDOR_H = 2;
  const WALL_H = 8;
  const WALL_T = 3;
  const MODEL_MARGIN = 96;

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
    4: { rooms: buildFloor4Rooms(), label: 'ชั้น 4' },
    5: { rooms: buildFloor5Rooms(), label: 'ชั้น 5' },
  };

  let currentFloor = 4;
  let currentFilter = 'all';
  let viewQuarter = 0;
  let perspective = false;
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
  const shell = document.getElementById('lka-explorer-shell');
  const fallback = document.getElementById('lka-explorer-fallback');
  const hubActionFallback = document.getElementById('lka-hub-action-fallback');

  if (!canvas || !scene || !panel || !panelClose) return;

  function openExplorerShell() {
    if (shell) shell.open = true;
  }

  function initExplorerShell() {
    if (shell && window.matchMedia && window.matchMedia('(min-width: 56rem)').matches) {
      shell.open = true;
    }
  }

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
      ['lka-wall-top', [['0%', '#f8fbfd'], ['100%', '#dce8ef']], 'diagonal'],
      ['lka-wall-x', [['0%', '#bdccd7'], ['100%', '#91a6b5']], 'vertical'],
      ['lka-wall-y', [['0%', '#dce6ec'], ['100%', '#b1c2ce']], 'reverse'],
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
    if (!perspective) return { x: rx - z * 0.38, y: ry - z * 0.72 };
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
    const sides = [
      [b10, b11, t11, t10], [b01, b11, t11, t01],
      [b00, b01, t01, t00], [b00, b10, t10, t00],
    ];
    return {
      top: [t00, t10, t11, t01],
      sideX: sides[viewQuarter],
      sideY: sides[(viewQuarter + 1) % 4],
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
    // Coordinates follow the supplied plans, not sequential inventory packing.
    // Deliberately schematic: topology and room order, not measured dimensions.
    const positions = new Map();
    const row = (numbers, x, y, side, step = 44, d = 110) => numbers.forEach((num, i) => {
      positions.set(num, { x: x + i * step, y, w: step - 2, d, side });
    });
    const sequence = (start, end) => Array.from({ length: Math.abs(end - start) + 1 }, (_, i) => start + i * Math.sign(end - start));
    const service = (label, x, y, w, d, type = 'service') => ({ label, x, y, w, d, type });
    let spaces;
    let corridors;
    const fourth = data.rooms[0].floor === 4;
    if (fourth) {
      row(sequence(401, 407), 106, 22, 'rear');
      row(sequence(411, 416), 604, 22, 'rear', 38);
      row(sequence(432, 425), 106, 190, 'inner');
      row(sequence(424, 417), 528, 190, 'inner', 38);
      row(sequence(433, 440), 106, 302, 'inner');
      row(sequence(441, 448), 528, 302, 'inner', 38);
      row(sequence(460, 457), 106, 474, 'front');
      row([456, 455], 331, 474, 'front', 67);
      row([454, 453], 528, 474, 'front', 39);
      row([452, 451, 450, 449], 656, 474, 'front');
      spaces = [
        service('ห้องส้วม', 2, 22, 32, 280),
        service('ห้องอาบน้ำ', 38, 22, 32, 390),
        service('ที่ซักล้าง', 2, 306, 32, 160),
        service('ห้องอาบน้ำ', 868, 22, 40, 390),
        service('ห้องส้วม', 914, 22, 44, 280),
        service('ที่ซักล้าง', 914, 306, 44, 160),
        service('ห้องพัก / บริการ', 414, 22, 112, 110),
        service('409 · พื้นที่บริการ', 528, 22, 36, 110),
        service('410 · พื้นที่บริการ', 566, 22, 36, 110),
        service('ห้องเก็บของ', 38, 474, 66, 110),
        service('ห้องพยาบาล', 832, 474, 76, 110),
        service('บันได', 282, 474, 47, 110, 'stairs'),
        service('บันได', 607, 474, 47, 110, 'stairs'),
        service('บันได', 2, 498, 32, 86, 'stairs'),
        service('บันได', 912, 498, 46, 86, 'stairs'),
      ];
      corridors = [[72, 138, 790, 46], [72, 418, 790, 50], [72, 184, 28, 234], [832, 184, 30, 234], [466, 184, 60, 234]];
    } else {
      row(sequence(501, 508), 88, 60, 'rear', 45, 148);
      row(sequence(509, 516), 492, 60, 'rear', 41.5, 148);
      row(sequence(530, 527), 88, 266, 'front', 40, 144);
      row([526, 525, 524], 328, 266, 'front', 40, 144);
      row([523, 522, 521], 492, 266, 'front', 40, 144);
      row([520, 519, 518, 517], 665, 266, 'front', 40, 144);
      spaces = [
        service('ห้องอาบน้ำ', 2, 60, 50, 204),
        service('ห้องอาบน้ำ', 852, 60, 46, 204),
        service('ห้องส้วม', 900, 60, 58, 120),
        service('ห้องนอนทหาร', 2, 294, 84, 116),
        service('ห้องนอนทหาร', 826, 294, 72, 116),
        service('บันได', 266, 328, 47, 82, 'stairs'),
        service('บันได', 615, 328, 47, 82, 'stairs'),
      ];
      corridors = [[54, 210, 796, 54], [450, 60, 40, 350]];
    }
    return {
      roomItems: data.rooms.map(room => ({ room: { ...room, side: positions.get(room.num).side }, ...positions.get(room.num) })),
      spaces, corridors, worldW: 960, worldD: fourth ? 590 : 420,
    };
  }

  function appendPerimeterWalls(svg, project, worldW, worldD) {
    const group = svgEl('g', { class: 'lka-building-perimeter', 'aria-hidden': 'true' });
    const z = BASE_H;
    [
      [0, 0, worldW, WALL_T],
      [0, worldD - WALL_T, worldW, WALL_T],
      [0, WALL_T, WALL_T, worldD - WALL_T * 2],
      [worldW - WALL_T, WALL_T, WALL_T, worldD - WALL_T * 2],
    ].forEach(([x, y, w, d]) => {
      appendCuboid(group, cuboidFaces(project, x, y, w, d, z, WALL_H), 'lka-wall');
    });
    svg.appendChild(group);
  }

  function appendCirculationSpine(svg, project, layout) {
    const group = svgEl('g', { class: 'lka-circulation-spine', 'aria-hidden': 'true' });
    layout.corridors.forEach(([x, y, w, d]) => {
      appendCuboid(group, cuboidFaces(project, x, y, w, d, BASE_H, 1), 'lka-spine');
      if (w > 200) {
        const point = project(x + w / 2, y + d / 2, BASE_H + 2);
        const label = svgEl('text', { x: point.x, y: point.y, class: 'lka-context-label' });
        label.textContent = 'ทางเดิน';
        group.appendChild(label);
      }
    });
    svg.appendChild(group);
  }

  function appendRoomArchitecture(group, project, x, y, room, w, d) {
    const facadeZ = BASE_H + CORRIDOR_H + 5;
    const windowY = room.side === 'rear' ? y : y + d;
    const windowA = project(x + w * 0.2, windowY, facadeZ + 24);
    const windowB = project(x + w * 0.8, windowY, facadeZ + 24);
    group.appendChild(svgEl('line', {
      x1: windowA.x,
      y1: windowA.y,
      x2: windowB.x,
      y2: windowB.y,
      class: 'lka-room-window',
      'aria-hidden': 'true',
    }));

    const doorY = room.side === 'rear' ? y + d : y;
    const doorA = project(x + w * 0.4, doorY, facadeZ - 1);
    const doorB = project(x + w * 0.4, doorY, facadeZ + 14);
    group.appendChild(svgEl('line', {
      x1: doorA.x,
      y1: doorA.y,
      x2: doorB.x,
      y2: doorB.y,
      class: 'lka-room-door',
      'aria-hidden': 'true',
    }));

    const sill = project(
      x + w * 0.82,
      y + d * 0.72,
      BASE_H + CORRIDOR_H + 43,
    );
    group.appendChild(svgEl('circle', {
      cx: sill.x,
      cy: sill.y,
      r: room.cooling === 'air' ? 1.8 : 1.25,
      class: `lka-room-service-dot ${room.cooling}`,
      'aria-hidden': 'true',
    }));
  }

  function appendSiteContext(svg, project, worldW, worldD) {
    // Illustrative landscape to explain building sides; not surveyed planting.
    const context = svgEl('g', { class: 'lka-site-context', 'aria-hidden': 'true' });
    const plane = (x, y, w, d, className) => {
      context.appendChild(svgEl('polygon', {
        points: points([[x, y], [x + w, y], [x + w, y + d], [x, y + d]].map(([a, b]) => project(a, b, 0))),
        class: className,
      }));
    };
    plane(-42, -90, worldW + 84, worldD + 174, 'lka-site-ground');
    plane(285, -87, 390, 55, 'lka-pool-deck');
    plane(300, -80, 360, 40, 'lka-pool-water');
    for (let i = 1; i < 7; i++) {
      const a = project(300 + i * 51, -77, 0);
      const b = project(300 + i * 51, -43, 0);
      context.appendChild(svgEl('line', { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'lka-pool-lane' }));
    }
    plane(110, worldD + 12, 730, 38, 'lka-site-promenade');
    for (let i = 0; i < 12; i++) {
      const a = project(130 + i * 60, worldD + 12, 0);
      const b = project(130 + i * 60, worldD + 50, 0);
      context.appendChild(svgEl('line', { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'lka-paving-joint' }));
    }
    [[75, -62], [150, -62], [225, -62], [735, -62], [810, -62], [885, -62],
      [-24, 95], [-24, worldD / 2], [-24, worldD - 75],
      [worldW + 24, 95], [worldW + 24, worldD / 2], [worldW + 24, worldD - 75],
      [65, worldD + 32], [890, worldD + 32]].forEach(([x, y], index) => {
      const p = project(x, y, 0);
      const tree = svgEl('g', { class: 'lka-site-tree' });
      tree.appendChild(svgEl('ellipse', { cx: p.x + 6, cy: p.y + 5, rx: 19, ry: 12, class: 'lka-tree-shadow' }));
      tree.appendChild(svgEl('circle', { cx: p.x, cy: p.y, r: 16 + index % 3, class: 'lka-tree-crown' }));
      tree.appendChild(svgEl('circle', { cx: p.x - 4, cy: p.y - 5, r: 9, class: 'lka-tree-light' }));
      context.appendChild(tree);
    });
    svg.appendChild(context);
  }

  function makeSVG(floor) {
    const data = FLOOR_DATA[floor];
    const layout = roomLayout(data);
    const { roomItems, worldW, worldD } = layout;
    const projector = createProjector(worldW, worldD, BASE_H + 60);
    const project = projector.project;

    const svg = svgEl('svg', {
      viewBox: `0 0 ${projector.width.toFixed(1)} ${projector.height.toFixed(1)}`,
      role: 'group',
      'aria-label': `โมเดลจำลองสามมิติ ${data.label}`,
      class: 'lka-iso-svg',
      preserveAspectRatio: 'xMidYMid meet',
    });

    appendModelDefs(svg);
    appendSiteContext(svg, project, worldW, worldD);

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
    appendPerimeterWalls(svg, project, worldW, worldD);

    const corridor = svgEl('g', { class: 'lka-corridor-model' });
    svg.appendChild(corridor);
    appendCirculationSpine(corridor, project, layout);

    [['ด้านหลัง · สระว่ายน้ำ', -13], ['ด้านหน้า · หน้าอาคาร / พื้นที่โรงเรียน', worldD + 72]].forEach(([text, y]) => {
      const p = project(worldW / 2, y, 0);
      const label = svgEl('text', { x: p.x, y: p.y, class: 'lka-site-label' });
      label.textContent = text;
      svg.appendChild(label);
    });

    const orderedRooms = roomItems
      .map(item => ({ ...item, depth: modelDepth(item.x, item.y, item.w, item.d, worldW, worldD) }))
      .sort((a, b) => (a.room.num === selectedRoomNumber ? 1 : b.room.num === selectedRoomNumber ? -1 : a.depth - b.depth));

    orderedRooms.forEach(({ room, x, y, w, d }) => {
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
      group.dataset.side = room.side;
      group.dataset.x = x;
      group.dataset.y = y;
      group.dataset.w = w;
      group.dataset.d = d;

      const faces = cuboidFaces(project, x, y, w, d, BASE_H + CORRIDOR_H, isSelected ? 42 : ROOM_H);
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
        scheduleRender();
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
      if (isSelected) appendRoomArchitecture(group, project, x, y, room, w, d);
      group.appendChild(accent);
      group.appendChild(label);
      svg.appendChild(group);
    });

    layout.spaces.forEach(facility => {
      const group = svgEl('g', {
        class: `lka-facility-model facility${facility.type === 'stairs' ? ' lka-core-model' : ''}`,
        'data-cooling': 'facility',
        'aria-label': facility.label,
        'data-x': facility.x,
        'data-y': facility.y,
        'data-w': facility.w,
        'data-d': facility.d,
      });
      const faces = cuboidFaces(project, facility.x, facility.y, facility.w, facility.d, BASE_H + CORRIDOR_H, 2);
      appendCuboid(group, faces, 'lka-facility');
      const label = svgEl('text', {
        x: faces.center.x,
        y: faces.center.y,
        class: 'lka-facility-label',
      });
      label.textContent = facility.label;
      if (facility.d > facility.w * 1.5) label.setAttribute('transform', `rotate(-90 ${faces.center.x} ${faces.center.y})`);
      group.appendChild(label);
      if (facility.type === 'stairs') {
        for (let i = 1; i < 6; i++) {
          const a = project(facility.x + 4, facility.y + facility.d * i / 7, BASE_H + 3);
          const b = project(facility.x + facility.w - 4, facility.y + facility.d * i / 7, BASE_H + 3);
          group.insertBefore(svgEl('line', { x1: a.x, y1: a.y, x2: b.x, y2: b.y, class: 'lka-stair-tread' }), label);
        }
      }
      svg.appendChild(group);
    });

    // SVG paints in DOM order. Selection must sit above ALL service geometry,
    // not only above the other rooms (room 460 used to hide behind storage).
    const selectionLayer = svgEl('g', { class: 'lka-selection-layer' });
    const selectedModel = svg.querySelector('.lka-room-model.selected');
    if (selectedModel) selectionLayer.appendChild(selectedModel);
    svg.appendChild(selectionLayer);

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
    if (modelView) modelView.textContent = perspective ? `มุมมอง ${viewQuarter + 1}/4` : 'ผังจากด้านบน';
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
    populateRoomPicker();

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
    const side = room.side || roomLayout(FLOOR_DATA[room.floor]).roomItems.find(item => item.room.num === room.num).side;
    panel.dataset.side = side;
    document.getElementById('lka-panel-facing').textContent = side === 'rear' ? 'ด้านสระว่ายน้ำ' : side === 'front' ? 'ด้านหน้าอาคาร' : 'โซนกลางอาคาร';
    document.getElementById('lka-panel-context').textContent = side === 'rear'
      ? 'อยู่แถวหลังของอาคาร ฝั่งสระว่ายน้ำกรมการทหารสื่อสาร'
      : side === 'front' ? 'อยู่แถวหน้าอาคาร ฝั่งพื้นที่โรงเรียนทหารสื่อสาร' : 'อยู่ในกลุ่มห้องกลางผัง ดูตำแหน่งทางเดินและห้องข้างเคียงได้จากแผนผัง';
    panel.dataset.state = 'selected';
    panel.classList.add('has-selection');
    if (panelStatus) {
      panelStatus.textContent = [panelNumber.textContent, panelFloor.textContent, panelCooling.textContent, panelCapacity.textContent, document.getElementById('lka-panel-facing').textContent].join(', ');
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
    scheduleRender();
  }

  const picker = document.getElementById('lka-room-picker');
  function populateRoomPicker() {
    if (!picker) return;
    picker.replaceChildren(new Option('เลือกหมายเลขห้อง', ''));
    FLOOR_DATA[currentFloor].rooms.filter(room => currentFilter === 'all' || currentFilter === room.cooling).forEach(room => {
      picker.add(new Option(`${room.num} · ${room.cooling === 'air' ? 'ปรับอากาศ' : 'พัดลม'}`, room.num));
    });
    picker.value = selectedRoomNumber || '';
  }
  picker?.addEventListener('change', () => {
    const room = FLOOR_DATA[currentFloor].rooms.find(item => item.num === Number(picker.value));
    if (!room) { closePanel(); return; }
    selectedRoomNumber = room.num;
    showPanel(room);
    scheduleRender();
  });
  document.getElementById('lka-perspective')?.addEventListener('click', event => {
    perspective = !perspective;
    viewQuarter = 0;
    scale = 1;
    event.currentTarget.setAttribute('aria-pressed', String(perspective));
    event.currentTarget.textContent = perspective ? 'กลับสู่ผังแบน' : 'ดูมุมอาคาร';
    scheduleRender();
  });

  panelClose.addEventListener('click', () => closePanel({ restoreFocus: true }));
  panel.querySelector('.lka-room-next')?.addEventListener('click', () => closePanel());
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
      openExplorerShell();
      const targetFloor = button.dataset.explorerFloor;
      if (targetFloor) switchFloor(targetFloor);
    });
  });

  document.querySelectorAll('#lka-hub-action-3d, a[href="#lka-explorer"]').forEach(trigger => {
    trigger.addEventListener('click', () => {
      openExplorerShell();
    });
  });

  if (hubActionFallback) {
    hubActionFallback.addEventListener('click', () => {
      openExplorerShell();
      if (fallback) fallback.open = true;
    });
  }

  document.querySelectorAll('.lka-filter').forEach(button => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.lka-filter').forEach(candidate => {
        candidate.classList.remove('active');
        candidate.setAttribute('aria-pressed', 'false');
      });
      button.classList.add('active');
      button.setAttribute('aria-pressed', 'true');
      applyFilter(button.dataset.filter);
      populateRoomPicker();
    });
  });

  function clampScale(value) {
    return Math.min(1.7, Math.max(0.7, value));
  }

  function rotateView(delta) {
    perspective = true;
    const toggle = document.getElementById('lka-perspective');
    toggle.setAttribute('aria-pressed', 'true');
    toggle.textContent = 'กลับสู่ผังแบน';
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
    if (!perspective) return;
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
    if (!perspective) return;
    if (event.touches.length !== 1) return;
    lastTouchX = event.touches[0].clientX;
    lastTouchY = event.touches[0].clientY;
    touchCommitted = false;
  }, { passive: true });

  canvas.addEventListener('touchmove', event => {
    if (!perspective) return;
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

  initExplorerShell();
  applyTransform();
  renderFloor();
})();
