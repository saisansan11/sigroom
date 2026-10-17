const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const PUBLIC_ROUTES = [
  '/',
  '/home/',
  '/about/',
  '/accounts/login/',
  '/accounts/password-reset/',
  '/accounts/password-reset/done/',
  '/accounts/password-reset/confirm/invalid/invalid-token/',
  '/lodging/',
  '/lodging/about/',
];

async function ensureExplorerOpen(page) {
  const shell = page.locator('#lka-explorer-shell');
  if (!(await shell.evaluate(el => el.open))) {
    await page.locator('.lka-explorer-shell-trigger').click();
    await expect(shell).toHaveAttribute('open');
  }
}

for (const route of PUBLIC_ROUTES) {
  test(`WCAG A/AA automated scan: ${route}`, async ({ page }) => {
    await page.goto(route, { waitUntil: 'networkidle' });

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa', 'wcag21a', 'wcag21aa', 'wcag22aa'])
      .analyze();

    expect(results.violations, JSON.stringify(results.violations, null, 2)).toEqual([]);
  });
}

test('lodging explorer preserves room focus across a camera rerender', async ({ page }) => {
  await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
  await ensureExplorerOpen(page);
  const room = page.locator('.lka-room-block[data-num="401"]');
  await room.focus();
  await expect(room).toBeFocused();

  await page.keyboard.press('ArrowRight');

  const replacement = page.locator('.lka-room-block[data-num="401"]');
  await expect(replacement).toBeFocused();
});

test('Escape closes the mobile inspector and restores the selected room focus', async ({ page }) => {
  await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
  await ensureExplorerOpen(page);
  const room = page.locator('.lka-room-block[data-num="401"]');
  await room.click();
  await expect(page.locator('#lka-room-panel')).toHaveAttribute('data-state', 'selected');

  await page.locator('#lka-panel-close').focus();
  await page.keyboard.press('Escape');

  await expect(page.locator('#lka-room-panel')).toHaveAttribute('data-state', 'empty');
  await expect(page.locator('.lka-room-block[data-num="401"]')).toBeFocused();
});

test('room inspector uses a scoped polite live region', async ({ page }) => {
  await page.goto('/lodging/about/', { waitUntil: 'networkidle' });
  await expect(page.locator('#lka-room-panel')).not.toHaveAttribute('aria-live', /.+/);
  await expect(page.locator('#lka-panel-status')).toHaveAttribute('aria-live', 'polite');
  await expect(page.locator('#lka-panel-status')).toHaveAttribute('aria-atomic', 'true');
});


test('home service gateway stays compact and hides detailed board by default', async ({ page }) => {
  await page.goto('/home/', { waitUntil: 'networkidle' });
  await expect(page.locator('.home-service-gateway')).toBeVisible();
  await expect(page.locator('.home-service-card')).toHaveCount(3);
  await expect(page.locator('.home-status-disclosure')).not.toHaveAttribute('open');

  const metrics = await page.evaluate(() => ({
    scrollWidth: document.documentElement.scrollWidth,
    clientWidth: document.documentElement.clientWidth,
    bodyFont: parseFloat(getComputedStyle(document.body).fontSize),
  }));
  expect(metrics.scrollWidth).toBeLessThanOrEqual(metrics.clientWidth + 1);
  expect(metrics.bodyFont).toBeGreaterThanOrEqual(16);

  const labels = await page.locator('.home-service-card strong').allTextContents();
  expect(labels.some(text => text.includes('หาห้องว่างแล้วจอง'))).toBeTruthy();
  expect(labels.some(text => text.includes('เข้าสู่ระบบแล้วจอง') || text.includes('เลือก 1 ใน 3 ห้อง'))).toBeTruthy();
  expect(labels.some(text => text.includes('ดูห้อง ราคา และจองที่พัก'))).toBeTruthy();
});
