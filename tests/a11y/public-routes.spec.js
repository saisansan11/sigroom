const { test, expect } = require('@playwright/test');
const AxeBuilder = require('@axe-core/playwright').default;

const PUBLIC_ROUTES = [
  '/',
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
    await page.locator('#lka-hub-action-3d').click();
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
