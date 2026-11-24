import { expect, test } from '@playwright/test';

test.beforeEach(async ({ page }) => {
  await page.goto('/workspace/g_network');
  await page.evaluate(() => localStorage.clear());
  await page.reload();
  await expect(page.getByRole('heading', { name: 'DNS 查询', exact: true })).toBeVisible();
});

test('A → browse B → ask → S → return A → inspect the original S record', async ({ page }) => {
  const nodeList = page.getByRole('navigation', { name: '节点列表' });
  await nodeList.getByRole('button', { name: /缓存与 TTL/ }).click();
  await expect(page.getByRole('heading', { name: '缓存与 TTL', exact: true })).toBeVisible();
  await expect(page.getByText('提问记在 DNS 查询 · 引用 缓存与 TTL')).toBeVisible();

  const question = '权威地址已更新，为什么同一个递归解析器还可能回旧地址？';
  await page.getByRole('textbox', { name: '向 Teacher 提问' }).fill(question);
  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.getByText(question, { exact: true })).toBeVisible();
  await expect(page.getByText('它们是两个独立事件', { exact: false })).toBeVisible();

  await page.getByRole('button', { name: '由此开支线' }).click();
  await page.getByLabel('支线名称').fill('为什么更新后仍有旧地址');
  await page.getByRole('button', { name: '创建并进入支线' }).click();
  await expect(page.getByRole('heading', { name: '为什么更新后仍有旧地址', exact: true })).toBeVisible();

  const branchNote = '解析器 10:00:00 取得旧地址，TTL 为 120 秒，10:02:00 才到期。10:01:00 的查询到达时，缓存里的旧记录还有效。';
  await page.getByRole('textbox', { name: '学习理解编辑器' }).fill(branchNote);
  await page.getByRole('button', { name: '保存支线成果' }).click();
  await expect(page.getByText('这段表达已保存为 v1，可在记录中回查。')).toBeVisible();
  await page.getByRole('button', { name: '返回 DNS 查询' }).click();
  await expect(page.getByText('正在接续', { exact: true })).toBeVisible();
  await expect(page.getByText('你算出 10:01:00 时缓存仍有效', { exact: false })).toBeVisible();

  await page.getByRole('button', { name: /原记录 s_note/ }).click();
  await expect(page.getByRole('dialog', { name: '当时的学习记录' })).toBeVisible();
  await expect(page.getByText(branchNote, { exact: true })).toBeVisible();
  await expect(page.getByText('焦点版本 v3', { exact: true })).toBeVisible();
});

test('refresh restores focus, browsing and local drafts', async ({ page }) => {
  const nodeList = page.getByRole('navigation', { name: '节点列表' });
  await nodeList.getByRole('button', { name: /缓存与 TTL/ }).click();
  await page.getByRole('textbox', { name: '向 Teacher 提问' }).fill('刷新后仍要保留的问题');
  await page.getByRole('button', { name: '在此学习' }).click();
  await expect(page.getByText('焦点版本 v2', { exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: '向 Teacher 提问' }).fill('刷新后仍要保留的问题');
  await page.reload();
  await expect(page.getByText('焦点版本 v2', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '向 Teacher 提问' })).toHaveValue('刷新后仍要保留的问题');
});

test('source drawer opens a frozen version without changing focus', async ({ page }) => {
  await test.step('open source', async () => {
    await page.locator('.source-card').click();
    await expect(page.getByRole('dialog')).toBeVisible();
    await expect(page.getByText('冻结版本 v1', { exact: true })).toBeVisible();
    await expect(page.getByText('焦点版本 v1', { exact: true })).toBeVisible();
  });
  await test.step('close source', async () => {
    await page.getByRole('button', { name: '关闭出处' }).click();
    await expect(page.getByRole('dialog')).toHaveCount(0);
  });
});

test('failed resume can be retried without losing the branch result', async ({ page }) => {
  await page.getByRole('button', { name: '由此开支线' }).click();
  await page.getByLabel('支线名称').fill('缓存边界');
  await page.getByLabel('想弄清什么').fill('缓存到期前后会发生什么？');
  await page.getByRole('button', { name: '创建并进入支线' }).click();
  await expect(page.getByRole('heading', { name: '缓存边界', exact: true })).toBeVisible();
  await page.getByRole('textbox', { name: '学习理解编辑器' }).fill('10:01:00 时缓存仍有效。');
  await page.getByRole('button', { name: '保存支线成果' }).click();
  await expect(page.getByText('这段表达已保存为 v1，可在记录中回查。')).toBeVisible();

  await page.getByText('Mock', { exact: true }).click();
  await page.getByLabel('下次续学返回失败').check();
  await page.getByText('Mock', { exact: true }).click();
  await page.getByRole('button', { name: '返回 DNS 查询' }).click();
  await expect(page.getByText('续学暂时没有完成', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '重试这次接续' }).click();
  await expect(page.getByText('你算出 10:01:00 时缓存仍有效', { exact: false })).toBeVisible();
  await page.getByRole('button', { name: /原记录 s_note/ }).click();
  await expect(page.getByRole('dialog').getByText('10:01:00 时缓存仍有效。', { exact: true })).toBeVisible();
});

test('a stale focus conflict preserves unsubmitted text', async ({ page }) => {
  const draft = '这段尚未提交的问题必须保留';
  await page.getByRole('textbox', { name: '向 Teacher 提问' }).fill(draft);

  const otherTab = await page.context().newPage();
  await otherTab.goto('/workspace/g_network');
  await expect(otherTab.getByRole('heading', { name: 'DNS 查询', exact: true })).toBeVisible();
  await otherTab.getByRole('navigation', { name: '节点列表' }).getByRole('button', { name: /缓存与 TTL/ }).click();
  await otherTab.getByRole('button', { name: '在此学习' }).click();
  await expect(otherTab.getByText('焦点版本 v2', { exact: true })).toBeVisible();
  await otherTab.close();

  await page.getByRole('button', { name: '发送问题' }).click();
  await expect(page.getByText('FOCUS_CHANGED', { exact: true })).toBeVisible();
  await expect(page.getByRole('textbox', { name: '向 Teacher 提问' })).toHaveValue(draft);
});
