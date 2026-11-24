import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MockStudyApi } from './mockStudyApi';
import { StudyApiError } from './studyApi';
import type { Ref } from '@/types';

const sourceB: Ref = { kind: 'source', id: 'src_mini_book', revision: 1, locator: { section: '缓存与 TTL' } };

describe('MockStudyApi A/B/S learning flow', () => {
  let api: MockStudyApi;

  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date('2026-11-24T02:00:00Z'));
    localStorage.clear();
    api = new MockStudyApi({ latency: 0 });
    api.reset();
  });

  afterEach(() => vi.useRealTimers());

  it('keeps browsing separate from focus and attributes a delayed answer to A', async () => {
    const initial = await api.getWorkspace('g_network', 'node_b');
    expect(initial.node.id).toBe('node_b');
    expect(initial.focus.node_id).toBe('node_a');

    const { job_id } = await api.askTeacher({
      message_md: '为什么更新后仍可能得到旧地址？',
      expected_focus_revision: initial.focus.revision,
      refs: [{ kind: 'node', id: 'node_b', revision: 1 }, sourceB],
    });
    await api.startFocus('node_c', initial.focus.revision);
    vi.setSystemTime(Date.now() + 1000);
    expect((await api.getJob(job_id)).status).toBe('succeeded');

    const recordsA = await api.listRecords('node_a');
    const recordsC = await api.listRecords('node_c');
    expect(recordsA.map((record) => record.kind)).toEqual(['question', 'answer']);
    expect(recordsA[0].refs).toContainEqual(sourceB);
    expect(recordsC).toEqual([]);
  });

  it('creates S, restores A checkpoint, resumes from the actual S record and survives reload', async () => {
    const initial = await api.getWorkspace('g_network');
    const { branch, focus } = await api.createBranch({
      expected_focus_revision: initial.focus.revision,
      title: '为什么更新后仍有旧地址',
      question_md: '权威更新与缓存回答是什么关系？',
      origin_refs: [],
      checkpoint: { section_id: 'example_update' },
    });
    expect(focus.node_id).toBe(branch.id);

    const reloaded = new MockStudyApi({ latency: 0 });
    expect((await reloaded.getWorkspace('g_network')).focus.node_id).toBe(branch.id);
    const saved = await reloaded.saveRecord(branch.id, {
      kind: 'explanation',
      body_md: '解析器 10:00:00 取得旧地址，TTL 为 120 秒，10:02:00 才到期。',
      refs: [sourceB],
      action: 'finish_expression',
      expected_focus_revision: focus.revision,
    });
    const returned = await reloaded.returnBranch(branch.id, focus.revision);
    expect(returned.focus.node_id).toBe('node_a');
    expect(returned.focus.checkpoint.section_id).toBe('example_update');
    expect(returned.focus.revision).toBe(initial.focus.revision + 2);

    vi.setSystemTime(Date.now() + 1300);
    expect((await reloaded.getJob(returned.job_id)).status).toBe('succeeded');
    const records = await reloaded.listRecords('node_a');
    const answer = records.find((record) => record.kind === 'answer');
    expect(answer?.body_md).toContain('10:01:00');
    expect(answer?.refs).toContainEqual(saved.record_ref);
    expect((await reloaded.getReference(saved.record_ref)).body_md).toContain('10:02:00');
  });

  it('uses the alternate teaching result when S contains a later query', async () => {
    const { focus: initial } = await api.getWorkspace('g_network');
    const { branch, focus } = await api.createBranch({ expected_focus_revision: initial.revision, title: 'S', question_md: 'Q', origin_refs: [], checkpoint: {} });
    await api.saveRecord(branch.id, {
      kind: 'explanation', body_md: '这次查询发生在 10:03:00，旧缓存已经到期。', refs: [], action: 'finish_expression', expected_focus_revision: focus.revision,
    });
    const { job_id } = await api.returnBranch(branch.id, focus.revision);
    vi.setSystemTime(Date.now() + 1300);
    await api.getJob(job_id);
    const answer = (await api.listRecords('node_a')).find((record) => record.kind === 'answer');
    expect(answer?.body_md).toContain('10:03:00');
    expect(answer?.body_md).toContain('没有发生');
  });

  it('rejects stale focus writes and reports the current revision', async () => {
    const { focus } = await api.getWorkspace('g_network');
    await api.startFocus('node_b', focus.revision);
    const request = api.askTeacher({ message_md: '不会丢失的文字', expected_focus_revision: focus.revision, refs: [] });
    await expect(request).rejects.toMatchObject({ code: 'FOCUS_CHANGED' });
    await expect(request).rejects.toBeInstanceOf(StudyApiError);
  });

  it('supports failure and retry of the same resume snapshot', async () => {
    const { focus: initial } = await api.getWorkspace('g_network');
    const { branch, focus } = await api.createBranch({ expected_focus_revision: initial.revision, title: 'S', question_md: 'Q', origin_refs: [], checkpoint: {} });
    await api.saveRecord(branch.id, { kind: 'explanation', body_md: '一段成果', refs: [], action: 'finish_expression', expected_focus_revision: focus.revision });
    api.setResumeFailure(true);
    const { job_id } = await api.returnBranch(branch.id, focus.revision);
    vi.setSystemTime(Date.now() + 1300);
    expect((await api.getJob(job_id)).status).toBe('failed');

    await api.retryJob(job_id);
    vi.setSystemTime(Date.now() + 1000);
    expect((await api.getJob(job_id)).status).toBe('succeeded');
    expect((await api.listRecords('node_a')).filter((record) => record.kind === 'answer')).toHaveLength(1);
  });

  it('returns an explicit error for an unavailable reference revision', async () => {
    await expect(api.getReference({ kind: 'source', id: 'src_mini_book', revision: 99 })).rejects.toMatchObject({ code: 'REF_UNAVAILABLE' });
  });

  it('saves a checkpoint without changing the focus revision', async () => {
    const { focus } = await api.getWorkspace('g_network');
    const updated = await api.saveCheckpoint({ section_id: 'sec_2' }, focus.revision);
    expect(updated.revision).toBe(focus.revision);
    expect((await api.getWorkspace('g_network')).focus.checkpoint.section_id).toBe('sec_2');
  });
});
