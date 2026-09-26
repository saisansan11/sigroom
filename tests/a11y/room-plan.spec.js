const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test.beforeEach(async ({ page }) => {
  await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
  const shell = page.locator('#lka-explorer-shell');
  const width = page.viewportSize()?.width || 1280;
  if (width >= 896) {
    await expect(shell).toHaveAttribute('open');
  } else {
    await page.locator('#lka-hub-action-3d').click();
    await expect(shell).toHaveAttribute('open');
  }
});

async function rooms(page) {
  return page.locator('.lka-room-model').evaluateAll(nodes => nodes.map(node => ({
    num: Number(node.dataset.num), x: Number(node.dataset.x), y: Number(node.dataset.y),
    w: Number(node.dataset.w), d: Number(node.dataset.d), side: node.dataset.side,
  })));
}

test('desktop viewport: explorer shell auto-opens by default before interaction', async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 900 });
  await page.reload({ waitUntil: 'networkidle' });
  const shell = page.locator('#lka-explorer-shell');
  expect(await shell.evaluate(el => el.open)).toBe(true);
  await expect(shell).toHaveAttribute('open');
});

test('mobile viewport: shell initially closed, 3D hub action opens shell, and document root has no horizontal overflow', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle' });

  const shell = page.locator('#lka-explorer-shell');
  expect(await shell.evaluate(el => el.open)).toBe(false);

  await page.locator('#lka-hub-action-3d').click();
  expect(await shell.evaluate(el => el.open)).toBe(true);
  await expect(shell).toHaveAttribute('open');

  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('mobile viewport: fallback action opens both explorer shell and fallback text plan', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.reload({ waitUntil: 'networkidle' });

  const shell = page.locator('#lka-explorer-shell');
  const fallback = page.locator('#lka-explorer-fallback');

  expect(await shell.evaluate(el => el.open)).toBe(false);
  expect(await fallback.evaluate(el => el.open)).toBe(false);

  await page.locator('#lka-hub-action-fallback').click();

  expect(await shell.evaluate(el => el.open)).toBe(true);
  expect(await fallback.evaluate(el => el.open)).toBe(true);
  await expect(shell).toHaveAttribute('open');
  await expect(fallback).toHaveAttribute('open');
});

test('floor plans preserve room ordering, gaps, sides and non-overlapping footprints', async ({ page }) => {
  for (const floor of [4, 5]) {
    await page.locator(`[data-floor="${floor}"].lka-ftoggle`).click();
    await expect(page.locator('.lka-room-model')).toHaveCount(floor === 4 ? 57 : 30);
    const data = await rooms(page);
    await page.locator('[data-filter="facility"]').click();
    await expect(page.locator('.lka-facility-model:not(.hidden-filter)')).toHaveCount(floor === 4 ? 12 : 7);
    await expect(page.locator('.lka-room-model:not(.hidden-filter)')).toHaveCount(0);
    if (floor === 4) {
      await page.locator('[data-filter="future"]').click();
      await expect(page.locator('.lka-facility-model:not(.hidden-filter)')).toHaveCount(3);
      await expect(page.locator('.lka-room-model:not(.hidden-filter)')).toHaveCount(0);
    }
    await page.locator('[data-filter="all"]').click();
    const row = y => data.filter(room => room.y === y).sort((a, b) => a.x - b.x).map(room => room.num);
    if (floor === 4) {
      expect(row(22)).toEqual([401,402,403,404,405,406,407,411,412,413,414,415,416]);
      expect(row(190)).toEqual([432,431,430,429,428,427,426,425,424,423,422,421,420,419,418,417]);
      expect(row(302)).toEqual(Array.from({length:16}, (_, i) => 433 + i));
      expect(row(474)).toEqual(Array.from({length:12}, (_, i) => 460 - i));
      expect(data.find(r => r.num === 424).x - data.find(r => r.num === 425).x).toBeGreaterThan(80);
    } else {
      expect(row(60)).toEqual(Array.from({length:16}, (_, i) => 501 + i));
      expect(row(266)).toEqual(Array.from({length:14}, (_, i) => 530 - i));
      expect(data.find(r => r.num === 526).x - data.find(r => r.num === 527).x).toBeGreaterThan(80);
      expect(data.find(r => r.num === 520).x - data.find(r => r.num === 521).x).toBeGreaterThan(80);
    }
    for (const a of data) {
      for (const b of data.filter(r => r.num > a.num)) {
        expect(a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.d && a.y + a.d > b.y,
          `${a.num} overlaps ${b.num}`).toBe(false);
      }
      expect(a.side).toBe(a.y === (floor === 4 ? 22 : 60) ? 'rear' : a.y === (floor === 4 ? 474 : 266) ? 'front' : 'inner');
    }
  }
});

test('picker selects the correct side, persists in perspective, and clears with filters', async ({ page }) => {
  const picker = page.locator('#lka-room-picker');
  await picker.selectOption('401');
  await expect(page.locator('#lka-panel-facing')).toHaveText('ด้านสระว่ายน้ำ');
  await expect(page.locator('.lka-room-model.selected')).toHaveAttribute('data-num', '401');
  await page.locator('#lka-perspective').click();
  await expect(page.locator('.lka-room-model.selected')).toHaveAttribute('data-num', '401');
  await page.locator('#lka-panel-close').click();
  await page.locator('[data-filter="fan"]').click();
  await expect(picker.locator('option')).toHaveCount(33);
  await picker.selectOption('444');
  await expect(page.locator('#lka-panel-facing')).toHaveText('โซนกลางอาคาร');
  await page.locator('#lka-panel-close').click();
  await page.locator('[data-filter="all"]').click();
  await page.locator('#lka-btn-f5').click();
  await picker.selectOption('530');
  await expect(page.locator('#lka-panel-facing')).toHaveText('ด้านหน้าอาคาร');
  await expect(page.locator('#lka-panel-capacity')).toHaveText('4 คน');
});

test('selected inspector is accessible and page has no horizontal overflow', async ({ page }) => {
  await page.locator('#lka-room-picker').selectOption('401');
  const results = await new AxeBuilder({ page }).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(results.violations).toEqual([]);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});

test('raised room paints above service blocks in every camera view', async ({ page }) => {
  await page.locator('#lka-room-picker').selectOption('460');
  for (let quarter = 0; quarter < 4; quarter++) {
    await expect(page.locator('.lka-selection-layer > .lka-room-model.selected')).toHaveAttribute('data-num', '460');
    const selectionPaintsLast = await page.locator('.lka-selection-layer').evaluate(layer =>
      [...layer.parentElement.querySelectorAll('.lka-facility-model')].every(service =>
        Boolean(service.compareDocumentPosition(layer) & Node.DOCUMENT_POSITION_FOLLOWING)));
    expect(selectionPaintsLast).toBe(true);
    await page.locator('#lka-view-right').click();
  }
});

test('internal stair pairs have equal readable footprints without intersecting rooms', async ({ page }) => {
  for (const floor of [4, 5]) {
    await page.locator(`#lka-btn-f${floor}`).click();
    await expect(page.locator('.lka-room-model')).toHaveCount(floor === 4 ? 57 : 30);
    const stairs = await page.locator('.lka-core-model').evaluateAll(nodes => nodes
      .map(node => ({x: +node.dataset.x, y: +node.dataset.y, w: +node.dataset.w, d: +node.dataset.d}))
      .filter(stair => stair.x > 100 && stair.x < 800));
    expect(stairs).toHaveLength(2);
    expect(stairs[0].w).toBe(stairs[1].w);
    expect(stairs[0].d).toBe(stairs[1].d);
    expect(stairs[0].w).toBeGreaterThanOrEqual(44);
    const data = await rooms(page);
    for (const stair of stairs) {
      for (const room of data) {
        expect(stair.x < room.x + room.w && stair.x + stair.w > room.x && stair.y < room.y + room.d && stair.y + stair.d > room.y,
          `stair intersects room ${room.num}`).toBe(false);
      }
    }
  }
});


test('mobile fit mode keeps the full SVG scene inside the canvas on narrow iPhone-class widths', async ({ page }) => {
  const assertFit = async () => {
    const metrics = await page.evaluate(() => {
      const canvas = document.querySelector('#lka-explorer-canvas');
      const scene = document.querySelector('#lka-iso-scene');
      const svg = document.querySelector('#lka-iso-scene .lka-iso-svg');
      const c = canvas.getBoundingClientRect();
      const s = scene.getBoundingClientRect();
      const v = svg.getBoundingClientRect();
      return {
        documentOverflow: document.documentElement.scrollWidth > innerWidth,
        canvasClientWidth: canvas.clientWidth,
        canvasScrollWidth: canvas.scrollWidth,
        sceneScrollWidth: scene.scrollWidth,
        canvas: { left: c.left, right: c.right, top: c.top, bottom: c.bottom },
        scene: { left: s.left, right: s.right, top: s.top, bottom: s.bottom },
        svg: { left: v.left, right: v.right, top: v.top, bottom: v.bottom },
      };
    });
    expect(metrics.documentOverflow).toBe(false);
    expect(metrics.canvasScrollWidth).toBeLessThanOrEqual(metrics.canvasClientWidth + 1);
    expect(metrics.sceneScrollWidth).toBeLessThanOrEqual(metrics.canvasClientWidth + 1);
    expect(metrics.scene.left).toBeGreaterThanOrEqual(metrics.canvas.left - 2);
    expect(metrics.scene.right).toBeLessThanOrEqual(metrics.canvas.right + 2);
    expect(metrics.svg.left).toBeGreaterThanOrEqual(metrics.canvas.left - 2);
    expect(metrics.svg.right).toBeLessThanOrEqual(metrics.canvas.right + 2);
    expect(metrics.svg.top).toBeGreaterThanOrEqual(metrics.canvas.top - 2);
    expect(metrics.svg.bottom).toBeLessThanOrEqual(metrics.canvas.bottom + 2);
  };

  for (const width of [360, 390, 430]) {
    await page.setViewportSize({ width, height: 900 });
    await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
    const shell = page.locator('#lka-explorer-shell');
    if (!(await shell.evaluate(el => el.open))) {
      await page.locator('#lka-hub-action-3d').click();
    }
    await expect(shell).toHaveAttribute('open');

    for (const floor of [4, 5]) {
      await page.locator(`#lka-btn-f${floor}`).click();
      await assertFit();
      await page.locator('#lka-perspective').click();
      await assertFit();
      for (let quarter = 0; quarter < 4; quarter++) {
        await page.locator('#lka-view-right').click();
        await assertFit();
      }
      await page.locator('#lka-reset').click();
      await expect(page.locator('#lka-perspective')).toHaveAttribute('aria-pressed', 'false');
      await expect(page.locator('#lka-model-view')).toHaveText('ผังจากด้านบน');
      await assertFit();
    }
  }
});


test('service gateway responsive matrix has no page overflow, 16px body text, and 48px primary touch targets', async ({ page }) => {
  const widths = [320, 360, 390, 393, 430, 768, 834, 1024, 1280, 1440];
  for (const width of widths) {
    await page.setViewportSize({ width, height: width < 600 ? 900 : 1000 });
    await page.goto('/lodging/about/', { waitUntil: 'networkidle' });

    const metrics = await page.evaluate(() => {
      const bodySize = parseFloat(getComputedStyle(document.querySelector('.lka-page-wrap')).fontSize);
      const targets = [...document.querySelectorAll('.lka-service-cta, .lka-service-primary, .lka-online-room-card > a')];
      const smallTargets = targets.filter(el => el.getBoundingClientRect().height < 48).map(el => ({
        text: el.textContent.trim().replace(/\s+/g, ' ').slice(0, 60),
        height: el.getBoundingClientRect().height,
      }));
      return {
        pageOverflow: document.documentElement.scrollWidth > innerWidth + 1,
        bodySize,
        smallTargets,
      };
    });
    expect(metrics.pageOverflow, `horizontal overflow at ${width}px`).toBe(false);
    expect(metrics.bodySize, `body text below 16px at ${width}px`).toBeGreaterThanOrEqual(16);
    expect(metrics.smallTargets, `touch target below 48px at ${width}px`).toEqual([]);

    const lodging = page.locator('.lka-service-card--lodging .lka-service-primary');
    const online = page.locator('.lka-service-card--online .lka-service-primary');
    await expect(lodging).toBeVisible();
    await expect(online).toBeVisible();
    await expect(page.locator('.lka-service-card--learning')).toContainText('กำลังพัฒนาระบบ');

    await page.locator('.lka-rates-disclosure > summary').click();
    if (width <= 768) {
      await expect(page.locator('.lka-rates-table tr').nth(1)).toHaveCSS('display', 'block');
    } else {
      await expect(page.locator('.lka-rates-table')).toHaveCSS('display', 'table');
    }
  }
});

test('FAQ uses one disclosure indicator and whole summary row is keyboard operable', async ({ page }) => {
  const item = page.locator('.lka-faq-item').first();
  const summary = item.locator('summary');
  await expect(summary.locator('.lka-faq-icon')).toHaveCount(0);
  await summary.focus();
  await page.keyboard.press('Enter');
  await expect(item).toHaveAttribute('open');
  await page.keyboard.press('Enter');
  await expect(item).not.toHaveAttribute('open');
});

test('reduced motion mode still opens and operates the 3D explorer', async ({ page }) => {
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
  await page.locator('#lka-hub-action-3d').click();
  await expect(page.locator('#lka-explorer-shell')).toHaveAttribute('open');
  await page.locator('#lka-btn-f5').click();
  await expect(page.locator('.lka-room-model')).toHaveCount(30);
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
});
