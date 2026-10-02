/**
 * R3-G2 — โมเดลสามมิติอาคารที่พักนักเรียน รร.ส.สส. บนหน้า /lodging/about/
 *
 * - WebGL 1 แบบเขียนเอง ไม่มีไลบรารีภายนอก ไม่โหลดอะไรจากอินเทอร์เน็ต (ขนาดเล็กกว่า 6KB gzip)
 * - ภาพนิ่ง (poster) แสดงก่อนเสมอ โมเดลเริ่มทำงานหลังหน้าโหลดเสร็จ + เบราว์เซอร์ว่าง + Hero อยู่ในจอ
 * - ไม่เริ่มโมเดลเมื่อ: ผู้ใช้ตั้งลดการเคลื่อนไหว, เครื่องสเปกต่ำ, โหมดประหยัดข้อมูล, หรือไม่มี WebGL
 * - หมุนเองช้า ๆ เฉพาะตอนมองเห็นอยู่ หยุดเมื่อเลื่อนพ้นจอ/สลับแท็บ และมีปุ่มหยุดหมุน
 * - ลากแนวนอนเพื่อหมุน แนวตั้งปล่อยให้หน้าเลื่อนตามปกติ (touch-action: pan-y)
 *
 * รูปทรงอ้างอิงผังชั้น 4–5: อาคาร 5 ชั้น หน้ากว้าง ลึก มีบันไดสองแกนด้านหน้า
 * ด้านหลังติดสระว่ายน้ำ ขนาดเป็นภาพประกอบ ไม่ใช่แบบวัดขนาดจริง
 */
(function () {
  'use strict';

  var stage = document.getElementById('lka-hero-stage');
  if (!stage) return;

  var query = window.location.search || '';
  var CAPTURE = /[?&]hero=capture\b/.test(query); // ใช้สร้างภาพ poster เท่านั้น
  var FORCE_POSTER = /[?&]hero=poster\b/.test(query);

  // ---------- ขนาดอาคาร (เมตร) ----------
  var W = 64;          // หน้ากว้าง (แกน x)
  var D = 26;          // ความลึก (แกน z) ด้านหน้า = +z
  var FH = 3.4;        // ความสูงต่อชั้น
  var FLOORS = 5;
  var H = FH * FLOORS; // 17 m
  var HW = W / 2;
  var HD = D / 2;

  var BG = [0.094, 0.129, 0.114]; // #18211D
  var LIGHT = normalize([-0.5, 0.8, 0.55]);

  // ---------- คณิตศาสตร์เวกเตอร์/เมทริกซ์ (column-major) ----------
  function normalize(v) {
    var l = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / l, v[1] / l, v[2] / l];
  }
  function cross(a, b) {
    return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  }
  function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
  function perspective(fovy, aspect, near, far) {
    var f = 1 / Math.tan(fovy / 2);
    var nf = 1 / (near - far);
    return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0];
  }
  function lookAt(eye, target, up) {
    var z = normalize([eye[0] - target[0], eye[1] - target[1], eye[2] - target[2]]);
    var x = normalize(cross(up, z));
    var y = cross(z, x);
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0,
      -dot(x, eye), -dot(y, eye), -dot(z, eye), 1];
  }
  function multiply(a, b) {
    var out = new Array(16);
    for (var c = 0; c < 4; c++) {
      for (var r = 0; r < 4; r++) {
        var s = 0;
        for (var k = 0; k < 4; k++) s += a[k * 4 + r] * b[c * 4 + k];
        out[c * 4 + r] = s;
      }
    }
    return out;
  }

  // ---------- กล้อง ----------
  var FOVY = 30 * Math.PI / 180;
  var TARGET = [0, 6.5, -2];
  var DEFAULT_YAW = 0.6;
  var DEFAULT_PITCH = 0.37;
  var cam = { yaw: DEFAULT_YAW, pitch: DEFAULT_PITCH };
  var size = { w: 1, h: 1 };

  function cameraMatrix() {
    var aspect = size.w / size.h;
    var tanY = Math.tan(FOVY / 2);
    var tanX = tanY * aspect;
    // ให้อาคาร+บริเวณพอดีกรอบทั้งจอกว้างและจอแคบ
    var radius = Math.max(50 / tanX, 29 / tanY);
    var cp = Math.cos(cam.pitch);
    var eye = [
      TARGET[0] + radius * cp * Math.sin(cam.yaw),
      TARGET[1] + radius * Math.sin(cam.pitch),
      TARGET[2] + radius * cp * Math.cos(cam.yaw),
    ];
    var proj = perspective(FOVY, aspect, 5, radius * 3);
    return { vp: multiply(proj, lookAt(eye, TARGET, [0, 1, 0])), eye: eye };
  }

  function project(vp, p) {
    var x = vp[0] * p[0] + vp[4] * p[1] + vp[8] * p[2] + vp[12];
    var y = vp[1] * p[0] + vp[5] * p[1] + vp[9] * p[2] + vp[13];
    var w = vp[3] * p[0] + vp[7] * p[1] + vp[11] * p[2] + vp[15];
    return [(x / w * 0.5 + 0.5) * size.w, (1 - (y / w * 0.5 + 0.5)) * size.h];
  }

  // ---------- ป้ายชั้น (HTML ภาษาไทย คมชัด) ----------
  var tags = Array.prototype.slice.call(stage.querySelectorAll('[data-hero-tag]'));

  function layoutTags(vp) {
    if (!tags.length) return;
    var placed = [];
    tags.forEach(function (tag) {
      var y = (Number(tag.getAttribute('data-hero-tag')) - 0.5) * FH;
      var pts = [[HW, y, HD], [-HW, y, HD], [HW, y, -HD], [-HW, y, -HD]].map(function (p) {
        return project(vp, p);
      });
      var right = pts.reduce(function (a, b) { return b[0] > a[0] ? b : a; });
      var left = pts.reduce(function (a, b) { return b[0] < a[0] ? b : a; });
      var width = tag.offsetWidth || 120;
      var flip = right[0] + 12 + width > size.w - 6;
      var x = flip ? Math.max(6, left[0] - 12 - width) : right[0] + 12;
      var h = tag.offsetHeight || 22;
      var yy = (flip ? left[1] : right[1]) - h / 2;
      // ป้ายชั้น 5 อยู่ก่อนใน DOM: ป้ายถัดไปต้องไม่ทับป้ายก่อนหน้า
      placed.forEach(function (prev) {
        if (Math.abs(prev.x - x) < width && yy < prev.y + prev.h + 4) yy = prev.y + prev.h + 4;
      });
      placed.push({ x: x, y: yy, h: h });
      tag.classList.toggle('is-flipped', flip);
      tag.style.transform = 'translate(' + Math.round(x) + 'px,' + Math.round(yy) + 'px)';
    });
    stage.classList.add('has-tags');
  }

  function measure() {
    var rect = stage.getBoundingClientRect();
    size.w = Math.max(1, rect.width);
    size.h = Math.max(1, rect.height);
  }

  // ป้ายชั้นใช้ได้ทั้งโหมดภาพนิ่งและโหมด 3 มิติ (ภาพนิ่งถ่ายจากมุมกล้องเริ่มต้นเดียวกัน)
  function layoutPosterTags() {
    measure();
    layoutTags(cameraMatrix().vp);
  }

  // ---------- ตัดสินว่าจะเปิดโมเดลหรือไม่ ----------
  function shouldStayPoster() {
    if (CAPTURE) return false;
    if (FORCE_POSTER) return true;
    if (window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches) return true;
    var cores = navigator.hardwareConcurrency;
    var mem = navigator.deviceMemory;
    if (cores && cores <= 2) return true;
    if (mem && mem <= 2) return true;
    var conn = navigator.connection;
    if (conn && conn.saveData) return true;
    return false;
  }

  if (!CAPTURE) {
    layoutPosterTags();
    if ('ResizeObserver' in window) {
      new ResizeObserver(function () {
        if (stage.getAttribute('data-mode') !== 'live') layoutPosterTags();
      }).observe(stage);
    }
  }

  if (shouldStayPoster()) {
    stage.setAttribute('data-mode', 'poster');
    return;
  }

  // ---------- สร้างรูปทรง ----------
  // k (ช่องที่ 4 ของสี): 0 = พื้นดิน (จางหายที่ขอบ), 1 = วัตถุรับแสง, 2 = สีคงที่ (หน้าต่างมีไฟ/เส้นขอบ)
  var tri = { p: [], n: [], c: [] };
  var lines = { p: [], n: [], c: [] };
  var casters = [];

  function hex(h, k) {
    var v = parseInt(h.slice(1), 16);
    return [(v >> 16 & 255) / 255, (v >> 8 & 255) / 255, (v & 255) / 255, k];
  }

  var COL = {
    ground: hex('#26302B', 0),
    court: hex('#353F39', 0),
    road: hex('#1D2521', 0),
    lawn: hex('#2A3A30', 0),
    stone: hex('#CBBE9F', 1),
    paper: hex('#EEE7D5', 1),
    slab: hex('#F7F2E6', 1),
    roof: hex('#C9BFA7', 1),
    tower: hex('#E2D8C1', 1),
    glass: hex('#33423C', 1),
    glassLow: hex('#2B3833', 1),
    warm: hex('#E9C47E', 2),
    warmDim: hex('#C79A57', 2),
    curtain: hex('#8C7B5A', 2),
    stair: hex('#B99B63', 2),
    rim: hex('#D8CFB8', 1),
    water: hex('#4D8183', 1),
    canopy: hex('#3D5A45', 1),
    canopy2: hex('#46664D', 1),
    trunk: hex('#4A3F33', 1),
    edge: hex('#3C463F', 2),
    stamp: hex('#A3241C', 1),
  };

  function pushVert(buf, p, n, c) {
    buf.p.push(p[0], p[1], p[2]);
    buf.n.push(n[0], n[1], n[2]);
    buf.c.push(c[0], c[1], c[2], c[3]);
  }

  function quad(a, b, c, d, color) {
    var n = normalize(cross([b[0] - a[0], b[1] - a[1], b[2] - a[2]], [d[0] - a[0], d[1] - a[1], d[2] - a[2]]));
    [a, b, c, a, c, d].forEach(function (p) { pushVert(tri, p, n, color); });
  }

  // กล่องหมุนรอบแกนตั้งได้ (yaw) — ใช้กับอาคาร ต้นไม้ อุปกรณ์บนหลังคา
  function box(cx, cy, cz, sx, sy, sz, color, opts) {
    opts = opts || {};
    var cs = Math.cos(opts.yaw || 0);
    var sn = Math.sin(opts.yaw || 0);
    function P(x, y, z) {
      var lx = x * sx / 2;
      var lz = z * sz / 2;
      return [cx + lx * cs + lz * sn, cy + y * sy / 2, cz - lx * sn + lz * cs];
    }
    var v = [P(-1, -1, 1), P(1, -1, 1), P(1, 1, 1), P(-1, 1, 1), P(-1, -1, -1), P(1, -1, -1), P(1, 1, -1), P(-1, 1, -1)];
    var top = opts.topColor || color;
    quad(v[0], v[1], v[2], v[3], color);   // หน้า +z
    quad(v[5], v[4], v[7], v[6], color);   // หลัง -z
    quad(v[1], v[5], v[6], v[2], color);   // ขวา +x
    quad(v[4], v[0], v[3], v[7], color);   // ซ้าย -x
    quad(v[3], v[2], v[6], v[7], top);     // บน
    if (opts.edges) {
      [[0, 1], [1, 2], [2, 3], [3, 0], [4, 5], [5, 6], [6, 7], [7, 4], [0, 4], [1, 5], [2, 6], [3, 7]].forEach(function (e) {
        pushVert(lines, v[e[0]], [0, 1, 0], opts.edgeColor || COL.edge);
        pushVert(lines, v[e[1]], [0, 1, 0], opts.edgeColor || COL.edge);
      });
    }
    if (opts.shadow !== false) casters.push(v);
  }

  // สี่เหลี่ยมบนพื้น (ไม่ทอดเงา)
  function flat(x0, z0, x1, z1, y, color) {
    quad([x0, y, z1], [x1, y, z1], [x1, y, z0], [x0, y, z0], color);
  }

  // หน้าต่างบนผนัง: origin = มุมล่างซ้ายของผนัง, u = ทิศแนวนอนตามผนัง, n = ทิศออกนอกผนัง
  function windowQuad(origin, u, n, s0, s1, y0, y1, color) {
    var off = 0.06;
    function P(s, y) {
      return [origin[0] + u[0] * s + n[0] * off, y, origin[2] + u[2] * s + n[2] * off];
    }
    quad(P(s0, y0), P(s1, y0), P(s1, y1), P(s0, y1), color);
  }

  // สุ่มแบบกำหนดผลได้ (ให้ภาพ poster กับโมเดลตรงกันทุกครั้ง)
  var seed = 7;
  function rand() {
    seed = (seed * 16807) % 2147483647;
    return (seed - 1) / 2147483646;
  }

  function facade(origin, u, n, length, bays, skip) {
    var bay = length / bays;
    for (var f = 0; f < FLOORS; f++) {
      var base = f * FH;
      for (var b = 0; b < bays; b++) {
        if (skip && skip(b, f)) continue;
        var mid = (b + 0.5) * bay;
        if (f === 0) {
          windowQuad(origin, u, n, mid - bay * 0.36, mid + bay * 0.36, 0.35, 2.75, COL.glassLow);
          continue;
        }
        var color = COL.glass;
        if (f >= 3) {
          // ชั้น 4–5 คือชั้นห้องพัก: เปิดไฟเป็นส่วนใหญ่
          var r = rand();
          color = r < 0.62 ? COL.warm : (r < 0.82 ? COL.warmDim : COL.curtain);
        }
        windowQuad(origin, u, n, mid - bay * 0.3, mid + bay * 0.3, base + 0.95, base + 2.6, color);
      }
    }
  }

  function buildScene() {
    // พื้นที่รอบอาคาร
    flat(-140, -140, 140, 140, 0, COL.ground);
    flat(-HW - 10, HD, HW + 10, HD + 15, 0.02, COL.court);         // ลานหน้าอาคาร
    flat(-140, HD + 19, 140, HD + 27, 0.02, COL.road);             // ถนนด้านหน้า
    flat(-HW - 6, -HD - 34, HW + 6, -HD - 2, 0.02, COL.lawn);       // สนามหญ้าด้านหลัง

    // สระว่ายน้ำด้านหลังอาคาร
    box(8, 0.15, -HD - 17, 30, 0.3, 15, COL.rim, { edges: true, shadow: false });
    flat(-5.5, -HD - 23, 21.5, -HD - 11, 0.32, COL.water);

    // ตัวอาคาร: ชั้นล่างฐานหิน + ชั้นบนสีกระดาษ
    box(0, FH / 2, 0, W, FH, D, COL.stone, { edges: true });
    box(0, FH + (H - FH) / 2, 0, W, H - FH, D, COL.paper, { edges: true, topColor: COL.roof });

    // แนวพื้นแต่ละชั้น (ยื่นออกมาเล็กน้อย ให้เห็นจังหวะชั้น)
    for (var f = 1; f < FLOORS; f++) {
      box(0, f * FH, 0, W + 0.8, 0.32, D + 0.8, COL.slab, { edges: true });
    }
    // เสาครีบด้านหน้า/หลัง ทุก 2 ช่วงเสา
    for (var i = 0; i <= 8; i++) {
      var x = -HW + i * 8;
      if (Math.abs(x) === HW) continue;
      box(x, FH + (H - FH) / 2, HD + 0.2, 0.5, H - FH, 0.4, COL.slab, { edges: false });
      box(x, FH + (H - FH) / 2, -HD - 0.2, 0.5, H - FH, 0.4, COL.slab, { edges: false });
    }

    // กันตกหลังคา
    box(0, H + 0.5, HD - 0.15, W, 1, 0.3, COL.slab, { edges: true });
    box(0, H + 0.5, -HD + 0.15, W, 1, 0.3, COL.slab, { edges: true });
    box(HW - 0.15, H + 0.5, 0, 0.3, 1, D - 0.6, COL.slab, { edges: true });
    box(-HW + 0.15, H + 0.5, 0, 0.3, 1, D - 0.6, COL.slab, { edges: true });

    // แกนบันไดสองแกนด้านหน้า (ตามผังชั้น 4–5)
    [-14, 14].forEach(function (tx) {
      box(tx, (H + 2.6) / 2, HD + 1.7, 6, H + 2.6, 3.4, COL.tower, { edges: true, topColor: COL.roof });
      windowQuad([tx - 3, 0, HD + 3.4], [1, 0, 0], [0, 0, 1], 2.4, 3.6, FH + 0.6, H - 0.4, COL.stair);
    });

    // หลังคา: ถังน้ำและห้องเครื่อง
    box(6, H + 1.9, -5, 6, 3.8, 4, COL.tower, { edges: true, topColor: COL.roof });
    box(-20, H + 0.8, -4, 3, 1.6, 2, COL.rim, { edges: true });
    box(-25, H + 0.8, -4, 3, 1.6, 2, COL.rim, { edges: true });
    box(22, H + 0.8, 3, 3, 1.6, 2, COL.rim, { edges: true });

    // หลังคาทางเข้าหน้าอาคาร + เสา
    box(0, 3.25, HD + 2.5, 12, 0.4, 5, COL.slab, { edges: true });
    box(-5.5, 1.5, HD + 4.5, 0.45, 3, 0.45, COL.slab, { edges: true });
    box(5.5, 1.5, HD + 4.5, 0.45, 3, 0.45, COL.slab, { edges: true });
    // แถบสีแดงตราใต้หลังคาทางเข้า (สัญลักษณ์ทางเข้า)
    box(0, 3.0, HD + 4.95, 12, 0.12, 0.1, COL.stamp, { shadow: false });

    // หน้าต่าง: หน้า/หลัง 16 ช่วง ด้านข้าง 6 ช่วง
    var towerBay = function (b, f) { return f === 0 ? false : (b === 4 || b === 11); };
    facade([-HW, 0, HD], [1, 0, 0], [0, 0, 1], W, 16, towerBay);
    facade([HW, 0, -HD], [-1, 0, 0], [0, 0, -1], W, 16, null);
    facade([HW, 0, HD], [0, 0, -1], [1, 0, 0], D, 6, null);
    facade([-HW, 0, -HD], [0, 0, 1], [-1, 0, 0], D, 6, null);

    // ต้นไม้ทรงเรียบ (สองชั้นพุ่ม)
    var trees = [
      [-44, HD + 17], [-36, HD + 17], [36, HD + 17], [44, HD + 17], [-24, HD + 17.5], [24, HD + 17.5],
      [-42, 4], [-42, -8], [42, -4], [43, 8],
      [-26, -HD - 10], [-18, -HD - 28], [30, -HD - 26], [34, -HD - 9], [-30, -HD - 22],
    ];
    trees.forEach(function (t, idx) {
      var s = 0.85 + rand() * 0.45;
      box(t[0], 1.3 * s, t[1], 0.5, 2.6 * s, 0.5, COL.trunk);
      box(t[0], 3.6 * s, t[1], 4.2 * s, 2.8 * s, 4.2 * s, idx % 2 ? COL.canopy : COL.canopy2, { yaw: 0.785 });
      box(t[0], 5.4 * s, t[1], 2.6 * s, 1.6 * s, 2.6 * s, COL.canopy2, { yaw: 0.2 });
    });
  }

  // เงาตกกระทบพื้น: ฉายทุกสามเหลี่ยมของวัตถุลงระนาบพื้นตามทิศแสง
  function buildShadows() {
    var out = [];
    var y0 = 0.06;
    function proj(p) {
      var t = (p[1] - y0) / LIGHT[1];
      return [p[0] - LIGHT[0] * t, y0, p[2] - LIGHT[2] * t];
    }
    casters.forEach(function (v) {
      var s = v.map(proj);
      // แต่ละกล่อง: ฉาย 6 หน้า (ครบทุกด้านให้เงาทึบเต็มรูป)
      [[0, 1, 2, 3], [5, 4, 7, 6], [1, 5, 6, 2], [4, 0, 3, 7], [3, 2, 6, 7], [4, 5, 1, 0]].forEach(function (f) {
        [f[0], f[1], f[2], f[0], f[2], f[3]].forEach(function (i) { out.push(s[i][0], s[i][1], s[i][2]); });
      });
    });
    return new Float32Array(out);
  }

  // ---------- WebGL ----------
  var VS = [
    'attribute vec3 aP; attribute vec3 aN; attribute vec4 aC;',
    'uniform mat4 uVP; uniform vec3 uL;',
    'varying vec3 vCol; varying vec3 vW; varying float vK;',
    'void main(){',
    '  vW = aP; vK = aC.a;',
    '  vec3 col = aC.rgb;',
    '  if (aC.a > 0.5 && aC.a < 1.5) {',
    '    float d = max(dot(aN, uL), 0.0);',
    '    float hemi = 0.5 + 0.5 * aN.y;',
    '    float ao = mix(0.74, 1.0, clamp(aP.y / 4.0, 0.0, 1.0));',
    '    col = aC.rgb * (0.36 + 0.2 * hemi + 0.6 * d) * ao;',
    '  }',
    '  vCol = col;',
    '  gl_Position = uVP * vec4(aP, 1.0);',
    '}',
  ].join('\n');

  var FS = [
    'precision mediump float;',
    'uniform vec3 uBg; uniform vec3 uEye; uniform float uMode;',
    'varying vec3 vCol; varying vec3 vW; varying float vK;',
    'void main(){',
    '  if (uMode > 0.5) { gl_FragColor = vec4(0.03, 0.05, 0.04, 0.42); return; }',
    '  vec3 c = vCol;',
    '  if (vK < 0.5) {',
    '    float r = length(vW.xz * vec2(1.0, 1.25));',
    '    c = mix(c, uBg, smoothstep(46.0, 104.0, r));',
    '  }',
    '  float dist = length(vW - uEye);',
    '  c = mix(c, uBg, clamp((dist - 110.0) / 320.0, 0.0, 0.22));',
    '  gl_FragColor = vec4(c, 1.0);',
    '}',
  ].join('\n');

  var canvas = null;
  var gl = null;
  var prog = null;
  var loc = {};
  var buffers = {};
  var counts = {};

  function compile(type, src) {
    var sh = gl.createShader(type);
    gl.shaderSource(sh, src);
    gl.compileShader(sh);
    if (!gl.getShaderParameter(sh, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(sh));
    return sh;
  }

  function makeBuffer(data) {
    var b = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, b);
    gl.bufferData(gl.ARRAY_BUFFER, data, gl.STATIC_DRAW);
    return b;
  }

  function setupGL() {
    canvas = document.createElement('canvas');
    canvas.className = 'lka-hero-canvas';
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', stage.getAttribute('data-model-label') || 'โมเดลสามมิติอาคารที่พักนักเรียน');
    canvas.setAttribute('tabindex', '0');
    canvas.setAttribute('aria-describedby', 'lka-hero-hint');
    var opts = { antialias: true, alpha: false, stencil: true, preserveDrawingBuffer: CAPTURE, powerPreference: 'low-power' };
    gl = canvas.getContext('webgl', opts) || canvas.getContext('experimental-webgl', opts);
    if (!gl) return false;

    prog = gl.createProgram();
    gl.attachShader(prog, compile(gl.VERTEX_SHADER, VS));
    gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FS));
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) return false;
    gl.useProgram(prog);
    ['aP', 'aN', 'aC'].forEach(function (n) { loc[n] = gl.getAttribLocation(prog, n); });
    ['uVP', 'uL', 'uBg', 'uEye', 'uMode'].forEach(function (n) { loc[n] = gl.getUniformLocation(prog, n); });

    buildScene();
    buffers.tp = makeBuffer(new Float32Array(tri.p));
    buffers.tn = makeBuffer(new Float32Array(tri.n));
    buffers.tc = makeBuffer(new Float32Array(tri.c));
    counts.tri = tri.p.length / 3;
    buffers.lp = makeBuffer(new Float32Array(lines.p));
    buffers.ln = makeBuffer(new Float32Array(lines.n));
    buffers.lc = makeBuffer(new Float32Array(lines.c));
    counts.lines = lines.p.length / 3;
    var shadow = buildShadows();
    buffers.sp = makeBuffer(shadow);
    counts.shadow = shadow.length / 3;

    gl.uniform3fv(loc.uL, LIGHT);
    gl.uniform3fv(loc.uBg, BG);
    gl.enable(gl.DEPTH_TEST);
    gl.enable(gl.CULL_FACE);
    gl.cullFace(gl.BACK);
    return true;
  }

  function bindAttrs(p, n, c) {
    gl.bindBuffer(gl.ARRAY_BUFFER, p);
    gl.enableVertexAttribArray(loc.aP);
    gl.vertexAttribPointer(loc.aP, 3, gl.FLOAT, false, 0, 0);
    if (n) {
      gl.bindBuffer(gl.ARRAY_BUFFER, n);
      gl.enableVertexAttribArray(loc.aN);
      gl.vertexAttribPointer(loc.aN, 3, gl.FLOAT, false, 0, 0);
      gl.bindBuffer(gl.ARRAY_BUFFER, c);
      gl.enableVertexAttribArray(loc.aC);
      gl.vertexAttribPointer(loc.aC, 4, gl.FLOAT, false, 0, 0);
    } else {
      gl.disableVertexAttribArray(loc.aN);
      gl.disableVertexAttribArray(loc.aC);
      gl.vertexAttrib3f(loc.aN, 0, 1, 0);
      gl.vertexAttrib4f(loc.aC, 0, 0, 0, 2);
    }
  }

  function resize() {
    measure();
    var dpr = Math.min(window.devicePixelRatio || 1, 2);
    var w = Math.round(size.w * dpr);
    var h = Math.round(size.h * dpr);
    if (canvas.width !== w || canvas.height !== h) {
      canvas.width = w;
      canvas.height = h;
    }
    gl.viewport(0, 0, w, h);
  }

  function draw() {
    var m = cameraMatrix();
    gl.clearColor(BG[0], BG[1], BG[2], 1);
    gl.clearStencil(0);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT | gl.STENCIL_BUFFER_BIT);
    gl.uniformMatrix4fv(loc.uVP, false, new Float32Array(m.vp));
    gl.uniform3fv(loc.uEye, m.eye);

    // 1) พื้น + อาคาร
    gl.uniform1f(loc.uMode, 0);
    gl.enable(gl.POLYGON_OFFSET_FILL);
    gl.polygonOffset(1, 1);
    bindAttrs(buffers.tp, buffers.tn, buffers.tc);
    gl.drawArrays(gl.TRIANGLES, 0, counts.tri);
    gl.disable(gl.POLYGON_OFFSET_FILL);

    // 2) เส้นขอบแบบหุ่นจำลองสถาปัตยกรรม
    bindAttrs(buffers.lp, buffers.ln, buffers.lc);
    gl.drawArrays(gl.LINES, 0, counts.lines);

    // 3) เงา: stencil กันเงาซ้อนจนดำเกิน
    gl.uniform1f(loc.uMode, 1);
    gl.disable(gl.CULL_FACE);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    gl.enable(gl.STENCIL_TEST);
    gl.stencilFunc(gl.EQUAL, 0, 0xff);
    gl.stencilOp(gl.KEEP, gl.KEEP, gl.INCR);
    gl.depthMask(false);
    bindAttrs(buffers.sp, null, null);
    gl.drawArrays(gl.TRIANGLES, 0, counts.shadow);
    gl.depthMask(true);
    gl.disable(gl.STENCIL_TEST);
    gl.disable(gl.BLEND);
    gl.enable(gl.CULL_FACE);

    layoutTags(m.vp);
  }

  // ---------- การหมุนและการโต้ตอบ ----------
  var SPEED = (Math.PI * 2) / 100000; // รอบละ 100 วินาที
  var raf = 0;
  var lastT = 0;
  var visible = true;
  var userPaused = false;
  var resumeAt = 0;
  var dirty = true;
  var dragging = null;
  var toggle = document.getElementById('lka-hero-toggle');

  function autoOn() { return !userPaused && !CAPTURE; }

  function frame(t) {
    raf = 0;
    var dt = Math.min(64, t - lastT);
    lastT = t;
    if (autoOn() && !dragging && t > resumeAt) {
      cam.yaw += dt * SPEED;
      dirty = true;
    }
    if (dirty) {
      draw();
      dirty = false;
    }
    if (visible && !document.hidden && autoOn()) raf = requestAnimationFrame(frame);
  }

  function kick() {
    if (raf || !gl) return;
    lastT = performance.now();
    raf = requestAnimationFrame(frame);
  }

  function requestDraw() {
    dirty = true;
    kick();
  }

  function holdAuto(ms) {
    resumeAt = performance.now() + ms;
  }

  function setPaused(paused) {
    userPaused = paused;
    if (toggle) {
      toggle.setAttribute('aria-pressed', paused ? 'true' : 'false');
      toggle.textContent = paused ? 'หมุนอัตโนมัติ' : 'หยุดหมุน';
    }
    if (!paused) kick();
  }

  function bindInteraction() {
    canvas.addEventListener('pointerdown', function (e) {
      if (e.button !== undefined && e.button !== 0) return;
      dragging = { id: e.pointerId, x: e.clientX, y: e.clientY, type: e.pointerType };
      try { canvas.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ }
      stage.classList.add('is-dragging');
    });
    canvas.addEventListener('pointermove', function (e) {
      if (!dragging || dragging.id !== e.pointerId) return;
      var dx = e.clientX - dragging.x;
      var dy = e.clientY - dragging.y;
      dragging.x = e.clientX;
      dragging.y = e.clientY;
      cam.yaw -= dx * 0.008;
      if (dragging.type === 'mouse' || dragging.type === 'pen') {
        cam.pitch = Math.min(0.72, Math.max(0.14, cam.pitch + dy * 0.004));
      }
      requestDraw();
    });
    function end(e) {
      if (!dragging || dragging.id !== e.pointerId) return;
      dragging = null;
      stage.classList.remove('is-dragging');
      holdAuto(4000);
      kick();
    }
    canvas.addEventListener('pointerup', end);
    canvas.addEventListener('pointercancel', end);
    canvas.addEventListener('keydown', function (e) {
      var step = 0.18;
      if (e.key === 'ArrowLeft') cam.yaw += step;
      else if (e.key === 'ArrowRight') cam.yaw -= step;
      else if (e.key === 'ArrowUp') cam.pitch = Math.min(0.72, cam.pitch + 0.06);
      else if (e.key === 'ArrowDown') cam.pitch = Math.max(0.14, cam.pitch - 0.06);
      else if (e.key === 'Home') { cam.yaw = DEFAULT_YAW; cam.pitch = DEFAULT_PITCH; }
      else return;
      e.preventDefault();
      holdAuto(6000);
      requestDraw();
    });
    if (toggle) {
      toggle.addEventListener('click', function () { setPaused(!userPaused); });
    }
    document.addEventListener('visibilitychange', function () {
      if (!document.hidden) kick();
    });
    if ('IntersectionObserver' in window) {
      new IntersectionObserver(function (entries) {
        visible = entries[0].isIntersecting;
        if (visible) kick();
      }).observe(stage);
    }
    if ('ResizeObserver' in window) {
      new ResizeObserver(function () { resize(); requestDraw(); }).observe(stage);
    } else {
      window.addEventListener('resize', function () { resize(); requestDraw(); });
    }
    canvas.addEventListener('webglcontextlost', function (e) {
      e.preventDefault();
      if (raf) cancelAnimationFrame(raf);
      raf = 0;
      gl = null;
      stage.setAttribute('data-mode', 'poster');
      if (stage.parentNode && stage.parentNode.classList) stage.parentNode.classList.remove('is-live');
    });
  }

  function start() {
    var ok = false;
    try { ok = setupGL(); } catch (err) { ok = false; }
    if (!ok) {
      stage.setAttribute('data-mode', 'poster');
      return;
    }
    stage.appendChild(canvas);
    resize();
    draw();
    dirty = false;
    stage.setAttribute('data-mode', 'live');
    if (stage.parentNode && stage.parentNode.classList) stage.parentNode.classList.add('is-live');
    if (CAPTURE) {
      document.documentElement.setAttribute('data-hero-ready', '1');
      return;
    }
    bindInteraction();
    holdAuto(1200);
    kick();
  }

  if (CAPTURE) {
    start();
    return;
  }

  // ---------- เริ่มหลังหน้าโหลดเสร็จ + เบราว์เซอร์ว่าง + Hero อยู่ในจอ ----------
  function whenIdle(fn) {
    if ('requestIdleCallback' in window) window.requestIdleCallback(fn, { timeout: 2500 });
    else window.setTimeout(fn, 400);
  }

  function whenVisible(fn) {
    if (!('IntersectionObserver' in window)) { fn(); return; }
    var io = new IntersectionObserver(function (entries) {
      if (entries[0].isIntersecting) {
        io.disconnect();
        fn();
      }
    }, { rootMargin: '120px' });
    io.observe(stage);
  }

  function boot() { whenVisible(function () { whenIdle(start); }); }

  if (document.readyState === 'complete') boot();
  else window.addEventListener('load', boot, { once: true });
})();
