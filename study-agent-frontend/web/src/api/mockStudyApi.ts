import examples from '../../../docs/development/examples.json';
import type {
  CreateBranchInput,
  Focus,
  Job,
  Ref,
  ReferenceContent,
  SaveRecordInput,
  Source,
  StudyGraph,
  StudyNode,
  StudyRecord,
  StudyRoute,
  TeacherMessageInput,
  Workspace,
} from '@/types';
import { StudyApiError } from './studyApi';
import type { StudyApi } from './studyApi';

interface PendingJob extends Job {
  ready_at: number;
  branch_id?: string;
  reply?: { node_id: string; body_md: string; refs: Ref[]; record_id: string };
}

interface BranchOrigin {
  node_id: string;
  checkpoint: Focus['checkpoint'];
}

interface MockState {
  focus: Focus;
  nodes: StudyNode[];
  records: StudyRecord[];
  jobs: PendingJob[];
  origins: Record<string, BranchOrigin>;
  checkpoints: Record<string, Focus['checkpoint']>;
  completions: { node_id: string; marked_at: string }[];
  sequence: number;
}

interface Fixture {
  sources: Source[];
  textbook_flow: {
    graph: StudyGraph;
    nodes: StudyNode[];
    routes: StudyRoute[];
    initial_focus: Focus;
    branch: StudyNode;
  };
  workflows: {
    resume_branch: {
      expected: { result: { reply_md: string; next_step_md: string } };
      alternate: { expected: { result: { reply_md: string; next_step_md: string } } };
    };
  };
}

const fixture = examples as unknown as Fixture;
const STORAGE_KEY = 'xuxue.mock.workspace.v1';
const SETTINGS_KEY = 'xuxue.mock.settings.v1';
const clone = <T,>(value: T): T => structuredClone(value);

function initialState(): MockState {
  return {
    focus: clone(fixture.textbook_flow.initial_focus),
    nodes: fixture.textbook_flow.nodes.filter((node) => node.kind !== 'branch').map(clone),
    records: [],
    jobs: [],
    origins: {},
    checkpoints: { node_a: clone(fixture.textbook_flow.initial_focus.checkpoint) },
    completions: [],
    sequence: 1,
  };
}

export class MockStudyApi implements StudyApi {
  private readonly latency: number;

  constructor(options: { latency?: number } = {}) {
    this.latency = options.latency ?? 90;
  }

  private read(): MockState {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) return JSON.parse(saved) as MockState;
    } catch {
      // A corrupt local fixture should never prevent the workspace from opening.
    }
    const state = initialState();
    this.write(state);
    return state;
  }

  private write(state: MockState) {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  }

  private async pause() {
    if (this.latency > 0) await new Promise((resolve) => setTimeout(resolve, this.latency));
  }

  private nextId(state: MockState, prefix: string) {
    state.sequence += 1;
    return `${prefix}_${String(state.sequence).padStart(2, '0')}`;
  }

  private assertFocus(state: MockState, nodeId: string, revision: number) {
    if (state.focus.node_id !== nodeId || state.focus.revision !== revision) {
      const current = this.node(state, state.focus.node_id);
      throw new StudyApiError(
        'FOCUS_CHANGED',
        `学习焦点已切换到「${current.title}」（版本 ${state.focus.revision}）。你的文字仍保留在编辑器中。`,
        { focus: state.focus },
      );
    }
  }

  private node(state: MockState, nodeId: string) {
    const node = state.nodes.find((item) => item.id === nodeId);
    if (!node) throw new StudyApiError('REF_UNAVAILABLE', '找不到这个学习节点。');
    return node;
  }

  private publicJob(job: PendingJob): Job {
    const { ready_at: _readyAt, reply: _reply, branch_id: _branchId, ...publicFields } = job;
    if (job.status === 'running' || job.status === 'queued') {
      const { result: _result, ...withoutResult } = publicFields;
      return withoutResult;
    }
    return publicFields;
  }

  private settle(state: MockState) {
    const now = Date.now();
    let changed = false;
    for (const job of state.jobs) {
      if (job.status !== 'running' || job.ready_at > now) continue;
      changed = true;
      if (job.kind === 'resume_branch' && this.failNextResume()) {
        job.status = 'failed';
        job.stage = 'resume';
        job.error = { code: 'PROVIDER_UNAVAILABLE', message: '续学服务暂时没有返回结果，可基于同一支线快照重试。' };
        job.updated_at = new Date().toISOString();
        this.setResumeFailure(false);
        continue;
      }
      job.status = 'succeeded';
      job.stage = 'finish';
      job.updated_at = new Date().toISOString();
      if (job.reply && !state.records.some((record) => record.id === job.reply?.record_id)) {
        const reply = job.reply;
        state.records.push({
          id: reply.record_id,
          graph_id: state.focus.graph_id,
          node_id: reply.node_id,
          revision: 1,
          kind: 'answer',
          body_md: reply.body_md,
          refs: clone(reply.refs),
          created_at: job.updated_at,
        });
        job.result = {
          record_ref: { kind: 'record', id: reply.record_id, revision: 1 },
          used_refs: clone(reply.refs),
        };
      }
    }
    if (changed) this.write(state);
  }

  private failNextResume() {
    return localStorage.getItem(SETTINGS_KEY)?.includes('"failNextResume":true') ?? false;
  }

  setResumeFailure(enabled: boolean) {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify({ failNextResume: enabled }));
  }

  getSettings() {
    return { failNextResume: this.failNextResume() };
  }

  reset() {
    this.write(initialState());
    this.setResumeFailure(false);
  }

  async getWorkspace(_graphId: string, nodeId?: string): Promise<Workspace> {
    await this.pause();
    const state = this.read();
    this.settle(state);
    const node = this.node(state, nodeId ?? state.focus.node_id);
    return {
      focus: clone(state.focus),
      graphs: [clone(fixture.textbook_flow.graph)],
      graph: clone(fixture.textbook_flow.graph),
      node: clone(node),
      nodes: clone(state.nodes),
      routes: clone(fixture.textbook_flow.routes),
      jobs: state.jobs.map((job) => this.publicJob(job)),
      candidates: [],
      milestones: [],
      completions: clone(state.completions),
      route_progress: fixture.textbook_flow.routes.map((route) => ({
        route_id: route.id,
        completed_count: route.counted_node_ids.filter((id) => state.completions.some((item) => item.node_id === id)).length,
        counted_count: route.counted_node_ids.length,
      })),
    };
  }

  async startFocus(nodeId: string, expectedFocusRevision: number, checkpoint?: Focus['checkpoint']) {
    await this.pause();
    const state = this.read();
    if (state.focus.revision !== expectedFocusRevision) {
      this.assertFocus(state, state.focus.node_id, expectedFocusRevision);
    }
    const node = this.node(state, nodeId);
    state.checkpoints[state.focus.node_id] = clone(state.focus.checkpoint);
    state.focus = {
      ...state.focus,
      node_id: nodeId,
      revision: state.focus.revision + 1,
      checkpoint: clone(checkpoint ?? state.checkpoints[nodeId] ?? { section_id: 'start' }),
    };
    this.write(state);
    return { focus: clone(state.focus), node: clone(node) };
  }

  async saveCheckpoint(checkpoint: Focus['checkpoint'], expectedFocusRevision: number) {
    await this.pause();
    const state = this.read();
    this.assertFocus(state, state.focus.node_id, expectedFocusRevision);
    state.focus.checkpoint = clone(checkpoint);
    state.checkpoints[state.focus.node_id] = clone(checkpoint);
    this.write(state);
    return clone(state.focus);
  }

  async createBranch(input: CreateBranchInput) {
    await this.pause();
    const state = this.read();
    const origin = this.node(state, state.focus.node_id);
    this.assertFocus(state, origin.id, input.expected_focus_revision);
    const suffix = state.nodes.some((node) => node.id === 'node_s') ? `_${state.sequence}` : '';
    const branch: StudyNode = {
      ...clone(fixture.textbook_flow.branch),
      id: `node_s${suffix}`,
      title: input.title,
      origin_node_ref: { kind: 'node', id: origin.id, revision: origin.revision },
      origin_refs: clone(input.origin_refs),
      origin_checkpoint: clone(input.checkpoint),
    };
    state.nodes.push(branch);
    state.origins[branch.id] = { node_id: origin.id, checkpoint: clone(input.checkpoint) };
    state.checkpoints[origin.id] = clone(input.checkpoint);
    if (input.question_md.trim()) {
      const recordId = this.nextId(state, 'rec_branch_question');
      state.records.push({
        id: recordId,
        graph_id: origin.graph_id,
        node_id: branch.id,
        revision: 1,
        kind: 'question',
        body_md: input.question_md,
        refs: clone(input.origin_refs),
        created_at: new Date().toISOString(),
      });
    }
    state.focus = {
      ...state.focus,
      node_id: branch.id,
      revision: state.focus.revision + 1,
      checkpoint: { section_id: 'start' },
    };
    this.write(state);
    return { branch: clone(branch), focus: clone(state.focus) };
  }

  async returnBranch(branchId: string, expectedFocusRevision: number) {
    await this.pause();
    const state = this.read();
    this.assertFocus(state, branchId, expectedFocusRevision);
    const origin = state.origins[branchId];
    if (!origin) throw new StudyApiError('REF_UNAVAILABLE', '找不到这条支线的出发位置。');
    state.focus = {
      ...state.focus,
      node_id: origin.node_id,
      revision: state.focus.revision + 1,
      checkpoint: clone(origin.checkpoint),
    };
    const branchRecords = state.records.filter((record) => record.node_id === branchId && record.kind !== 'question');
    const latest = branchRecords.at(-1);
    const alternate = latest?.body_md.includes('10:03') ?? false;
    const workflow = alternate ? fixture.workflows.resume_branch.alternate.expected : fixture.workflows.resume_branch.expected;
    const replyId = this.nextId(state, 'rec_resume');
    const jobId = this.nextId(state, 'job_resume');
    const refs = latest ? [{ kind: 'record', id: latest.id, revision: latest.revision } as Ref] : [];
    state.jobs.push({
      id: jobId,
      kind: 'resume_branch',
      status: 'running',
      stage: 'resume',
      updated_at: new Date().toISOString(),
      node_id: origin.node_id,
      branch_id: branchId,
      ready_at: Date.now() + 1200,
      reply: {
        node_id: origin.node_id,
        record_id: replyId,
        body_md: `${workflow.result.reply_md}\n\n**下一步**　${workflow.result.next_step_md}`,
        refs,
      },
    });
    this.write(state);
    return { focus: clone(state.focus), return_event_id: this.nextId(state, 'ret'), job_id: jobId };
  }

  async saveRecord(nodeId: string, input: SaveRecordInput) {
    await this.pause();
    const state = this.read();
    this.assertFocus(state, nodeId, input.expected_focus_revision);
    if (!input.body_md.trim()) throw new StudyApiError('INVALID_INPUT', '先写下一点内容再保存。');
    const id = this.nextId(state, nodeId.startsWith('node_s') ? 'rec_s_note' : 'rec_note');
    state.records.push({
      id,
      graph_id: state.focus.graph_id,
      node_id: nodeId,
      revision: 1,
      kind: input.kind,
      body_md: input.body_md,
      refs: clone(input.refs),
      created_at: new Date().toISOString(),
    });
    this.write(state);
    return { record_ref: { kind: 'record', id, revision: 1 } as Ref };
  }

  async askTeacher(input: TeacherMessageInput) {
    await this.pause();
    const state = this.read();
    const focusNode = this.node(state, state.focus.node_id);
    this.assertFocus(state, focusNode.id, input.expected_focus_revision);
    if (!input.message_md.trim()) throw new StudyApiError('INVALID_INPUT', '写下你的问题后再发送。');
    const questionId = this.nextId(state, 'rec_ask_from_a');
    const answerId = this.nextId(state, 'rec_answer');
    const jobId = this.nextId(state, 'job_answer');
    state.records.push({
      id: questionId,
      graph_id: focusNode.graph_id,
      node_id: focusNode.id,
      revision: 1,
      kind: 'question',
      body_md: input.message_md,
      refs: clone(input.refs),
      created_at: new Date().toISOString(),
    });
    state.jobs.push({
      id: jobId,
      kind: 'teacher_answer',
      status: 'running',
      stage: 'answer',
      updated_at: new Date().toISOString(),
      node_id: focusNode.id,
      ready_at: Date.now() + 900,
      reply: {
        node_id: focusNode.id,
        record_id: answerId,
        body_md: input.refs.length
          ? '我把你正在查看的材料放进这个问题里了。先区分“权威数据已经更新”和“递归解析器手里的缓存是否仍然有效”：它们是两个独立事件。你可以沿引用核对原文，再尝试画出两个时刻。'
          : '可以先把问题拆成“谁提供数据”和“谁向客户端作答”两步。写下你的判断后，我会按你的表达继续核对。',
        refs: clone(input.refs),
      },
    });
    this.write(state);
    return { record_ref: { kind: 'record', id: questionId, revision: 1 } as Ref, job_id: jobId };
  }

  async listRecords(nodeId: string) {
    await this.pause();
    const state = this.read();
    this.settle(state);
    return state.records.filter((record) => record.node_id === nodeId).map(clone);
  }

  async getJob(jobId: string) {
    const state = this.read();
    this.settle(state);
    const job = state.jobs.find((item) => item.id === jobId);
    if (!job) throw new StudyApiError('REF_UNAVAILABLE', '找不到这个后台任务。');
    return this.publicJob(job);
  }

  async retryJob(jobId: string) {
    await this.pause();
    const state = this.read();
    const job = state.jobs.find((item) => item.id === jobId);
    if (!job) throw new StudyApiError('REF_UNAVAILABLE', '找不到这个后台任务。');
    job.status = 'running';
    job.stage = job.kind === 'resume_branch' ? 'resume' : 'answer';
    job.ready_at = Date.now() + 900;
    job.error = undefined;
    job.updated_at = new Date().toISOString();
    this.write(state);
    return this.publicJob(job);
  }

  async getReference(ref: Ref): Promise<ReferenceContent> {
    await this.pause();
    const state = this.read();
    if (ref.kind === 'source') {
      const source = fixture.sources.find((item) => item.id === ref.id && item.revision === ref.revision);
      const section = source?.sections.find((item) => item.title === ref.locator?.section) ?? source?.sections[0];
      if (!source || !section) {
        throw new StudyApiError('REF_UNAVAILABLE', `找不到 ${ref.id} 的第 ${ref.revision} 版或对应章节。`);
      }
      return {
        ref: clone(ref),
        title: source.title,
        body_md: section.excerpt_md,
        url: source.url,
        status: 'available',
      };
    }
    if (ref.kind === 'record') {
      const record = state.records.find((item) => item.id === ref.id && item.revision === ref.revision);
      if (!record) throw new StudyApiError('REF_UNAVAILABLE', `找不到记录 ${ref.id} 的第 ${ref.revision} 版。`);
      return { ref: clone(ref), title: '当时的学习记录', body_md: record.body_md, node_id: record.node_id, status: 'available' };
    }
    if (ref.kind === 'node') {
      const node = state.nodes.find((item) => item.id === ref.id && item.revision === ref.revision);
      if (!node) throw new StudyApiError('REF_UNAVAILABLE', `找不到节点 ${ref.id} 的第 ${ref.revision} 版。`);
      return {
        ref: clone(ref),
        title: node.title,
        body_md: node.reading?.intro_md ?? node.objectives.map((objective) => objective.text).join('\n'),
        node_id: node.id,
        status: 'available',
      };
    }
    throw new StudyApiError('REF_UNAVAILABLE', '这类出处暂未在本地样例中提供。');
  }
}
