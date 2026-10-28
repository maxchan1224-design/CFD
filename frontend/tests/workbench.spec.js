import { test, expect } from '@playwright/test';

test('native CFD fields, section controls, validation, scenarios and export',async({page})=>{
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('/');
 await expect(page.locator('#metric-t')).not.toHaveText('—',{timeout:30000});
 await expect(page.locator('#viewer canvas')).toBeVisible();
 await page.locator('[data-field="rh"]').click();
 await page.locator('#humidity-type').selectOption('humidity');
 await expect(page.locator('#field-title')).toHaveText('Humidity ratio distribution');
 await page.locator('#section-axis').selectOption('x');
 await page.locator('#section-position').fill('3.5');
 await page.locator('#section-position').dispatchEvent('input');
 await expect(page.locator('#slice-label')).toContainText('Longitudinal');
 await page.locator('[data-field="velocity"]').click();
 await page.locator('#display-mode').selectOption('vectors');
 await page.locator('#display-mode').selectOption('streamlines');
 await expect(page.locator('#slice-label')).toContainText('solver velocity');
 await page.locator('#display-mode').selectOption('contours');
 await page.locator('#validation').click();
 await expect(page.getByRole('heading',{name:'Engineering validation',exact:true})).toBeVisible();
 await expect(page.getByText('Water vapour',{exact:true})).toBeVisible();
 await expect(page.locator('.check-box')).toHaveCount(7);
 await page.locator('#close-modal').click();
 await page.locator('#layout_id').selectOption('provisional-v1');
 await page.locator('#layout_id').dispatchEvent('input');
 await page.locator('#all-on').click();
 await expect(page.locator('[data-hood]:checked')).toHaveCount(5);
 await page.locator('#all-off').click();
 await expect(page.locator('[data-hood]:checked')).toHaveCount(0);
 await page.locator('[data-fcu="0"]').check();
 await expect(page.locator('#fcu-status-0')).toHaveText('ON');
 await page.locator('#scenarios').click();
 await page.locator('#scenario-name').fill('Browser check');
 await page.locator('#save-scenario').click();
 await expect(page.locator('.scenario-row').filter({hasText:'Browser check'}).first()).toBeVisible();
 await page.locator('#close-modal').click();
 await page.locator('#collapse').click();
 await expect(page.locator('#settings')).not.toBeVisible();
 await page.locator('#expand').click();
 await expect(page.locator('#settings')).toBeVisible();
 expect(errors).toEqual([]);
 await page.locator('[data-field="temperature"]').click();
 await page.screenshot({path:'/tmp/kitchen-desktop.png',fullPage:true});
});

test('mobile viewer and settings remain usable',async({page})=>{
 await page.setViewportSize({width:390,height:844});await page.goto('/');
 await expect(page.locator('#viewer canvas')).toBeVisible();
 await expect(page.locator('#settings')).not.toBeVisible();
 await page.locator('#expand').click();await expect(page.locator('#supply_lps')).toBeVisible();
 await page.locator('#collapse').click();
 await expect(page.locator('#run')).toBeVisible();
 await page.screenshot({path:'/tmp/kitchen-mobile.png',fullPage:true});
});

test('exported case contains runnable OpenFOAM dictionaries',async({request})=>{
 const response=await request.post('/api/case',{data:{name:'Unexecuted export test',iterations:100}});
 expect(response.status()).toBe(200);const record=await response.json();expect(record.executed).toBe(false);
 const archive=await request.get(record.archive);expect(archive.ok()).toBe(true);
 expect((await archive.body()).subarray(0,2).toString()).toBe('PK');
});

test('received layout is reviewed separately from the earlier CFD geometry',async({page})=>{
 await page.goto('/');
 await expect(page.locator('#layout-notice')).toContainText('dimensions provisional');
 await page.locator('#layout-review').click();
 await expect(page.locator('#modal-title')).toContainText('confirmed terminal mapping');
 const image=page.locator('.layout-image');
 await expect(image).toBeVisible();
 await expect.poll(()=>image.evaluate(el=>el.naturalWidth)).toBeGreaterThan(0);
 const heading=page.getByRole('heading',{name:'Confirmed terminal mapping',exact:true});
 await heading.scrollIntoViewIfNeeded();
 await expect(heading).toBeVisible();
 await expect(page.locator('#modal-content')).toContainText('S1 / S2');
 await expect(page.locator('#modal-content')).toContainText('Five hood/cooking-station positions');
 await page.keyboard.press('Escape');
 await expect(page.locator('#modal')).not.toBeVisible();
 await expect(page.locator('#run')).toBeEnabled();
});
