const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

test.beforeEach(async ({ page }) => {
  await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
});

async function rooms(page) {
  return page.locator('.lka-room-model').evaluateAll(nodes => nodes.map(node => ({
    num: Number(node.dataset.num), x: Number(node.dataset.x), y: Number(node.dataset.y),
    w: Number(node.dataset.w), d: Number(node.dataset.d), side: node.dataset.side,
  })));
}

test('floor plans preserve room ordering, gaps, sides and non-overlapping footprints', async ({ page }) => {
  for (const floor of [4, 5]) {
    await page.locator(`[data-floor="${floor}"].lka-ftoggle`).click();
    await expect(page.locator('.lka-room-model')).toHaveCount(floor === 4 ? 57 : 30);
    const data = await rooms(page);
    await page.locator('[data-filter="facility"]').click();
    await expect(page.locator('.lka-facility-model:not(.hidden-filter)')).toHaveCount(floor === 4 ? 15 : 7);
    await expect(page.locator('.lka-room-model:not(.hidden-filter)')).toHaveCount(0);
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
