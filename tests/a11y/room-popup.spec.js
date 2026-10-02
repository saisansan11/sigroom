const {test, expect}=require('@playwright/test');
const AxeBuilder=require('@axe-core/playwright').default;
const room={id:'42',code:'DORM-425',building:'อาคารที่พัก',capacity:2,active:true,status:'ใช้งาน',request_url:'/lodging/request/?room_id=42',cohorts:[{title:'หลักสูตรทดสอบที่มีชื่อยาวเพื่อทดสอบการแสดงผลบนมือถือ',total:2,used:1,free:1,dates:'29/09/2569 – 09/10/2569',url:'/lodging/c/popup-qa/?room_id=42#room-42'}]};
async function open(page){
 await page.goto('/lodging/about/');
 await page.locator('.lka-explorer-shell-trigger').click();
 await page.locator('#lka-room-picker').selectOption('425');
 await expect(page.locator('#lka-room-panel')).toHaveAttribute('open');
}
test('live popup shows server counts and context links across small and landscape screens',async({page})=>{
 await page.route('**/lodging/rooms/425/',route=>route.fulfill({json:{room}}));
 for(const [width,height] of [[320,740],[375,812],[812,375],[1280,900]]){
  await page.setViewportSize({width,height}); await open(page);
  await expect(page.locator('#lka-room-availability')).toContainText('เหลือ 1 เตียง');
  await expect(page.locator('#lka-room-book')).toHaveAttribute('href',room.cohorts[0].url);
  await expect(page.locator('#lka-room-request')).toHaveAttribute('href',room.request_url);
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1)).toBe(true);
  const result=await new AxeBuilder({page}).include('#lka-room-panel').withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
  expect(result.violations).toEqual([]);
  await page.locator('#lka-panel-close').click();
 }
});
test('read failure can retry and closed dialog cannot be updated by stale response',async({page})=>{
 let attempts=0;
 await page.route('**/lodging/rooms/425/',route=>{attempts++;return attempts===1?route.abort():route.fulfill({json:{room}})});
 await open(page);
 await expect(page.locator('#lka-room-retry')).toBeVisible();
 await expect(page.locator('#lka-room-book')).toBeHidden();
 await page.locator('#lka-room-retry').click();
 await expect(page.locator('#lka-room-book')).toBeVisible();
 await page.keyboard.press('Escape');
 await expect(page.locator('#lka-room-panel')).not.toHaveAttribute('open');
});
test('full and unavailable states never offer a course booking',async({page})=>{
 for(const data of [null,{...room,active:false,cohorts:[],request_url:null},{...room,cohorts:[{...room.cohorts[0],free:0,used:2}]}]){
  await page.route('**/lodging/rooms/425/',route=>route.fulfill({json:{room:data}}));
  await open(page);
  await expect(page.locator('#lka-room-live')).not.toHaveText('กำลังตรวจสอบข้อมูลห้อง…');
  await expect(page.locator('#lka-room-book')).toBeHidden();
  await page.keyboard.press('Escape');
  await page.unroute('**/lodging/rooms/425/');
 }
});
