import type {
  CreateBranchInput,
  Focus,
  Job,
  Ref,
  ReferenceContent,
  SaveRecordInput,
  StudyNode,
  StudyRecord,
  TeacherMessageInput,
  Workspace,
} from '@/types';
import { StudyApiError } from './studyApi';
import type { StudyApi } from './studyApi';

interface Envelope<T> { data: T }

export class HttpStudyApi implements StudyApi {
  constructor(private readonly baseUrl: string) {}

  private async request<T>(path: string, init: RequestInit = {}, idempotent = false): Promise<T> {
    const headers = new Headers(init.headers);
    if (init.body && !headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
    if (idempotent && !headers.has('Idempotency-Key')) headers.set('Idempotency-Key', crypto.randomUUID());
    const response = await fetch(`${this.baseUrl}${path}`, { ...init, headers });
    const payload = await response.json().catch(() => null) as Envelope<T> | { error?: { code?: string; message?: string; details?: Record<string, unknown> } } | null;
    if (!response.ok) {
      const error = payload && 'error' in payload ? payload.error : undefined;
      throw new StudyApiError(error?.code ?? 'HTTP_ERROR', error?.message ?? `请求失败（${response.status}）`, error?.details);
    }
    if (!payload || !('data' in payload)) throw new StudyApiError('INVALID_RESPONSE', '服务端没有返回约定的 data 字段。');
    return payload.data;
  }

  private async rawWorkspace(graphId: string, nodeId?: string) {
    const query = new URLSearchParams({ graph_id: graphId });
    if (nodeId) query.set('node_id', nodeId);
    return this.request<Omit<Workspace, 'nodes'> & { nodes?: StudyNode[] }>(`/workspace?${query}`);
  }

  async getWorkspace(graphId: string, nodeId?: string): Promise<Workspace> {
    const workspace = await this.rawWorkspace(graphId, nodeId);
    if (workspace.nodes) return { ...workspace, nodes: workspace.nodes };
    const ids = new Set(workspace.routes.flatMap((route) => route.node_ids));
    ids.add(workspace.focus.node_id);
    if (nodeId) ids.add(nodeId);
    const nodes = new Map<string, StudyNode>();
    if (workspace.node) nodes.set(workspace.node.id, workspace.node);
    await Promise.all([...ids].filter((id) => !nodes.has(id)).map(async (id) => {
      const result = await this.rawWorkspace(graphId, id);
      nodes.set(id, result.node);
    }));
    return { ...workspace, nodes: [...nodes.values()] };
  }

  startFocus(nodeId: string, expectedFocusRevision: number, checkpoint?: Focus['checkpoint']) {
    return this.request<{ focus: Focus; node: StudyNode }>('/focus/start', {
      method: 'POST', body: JSON.stringify({ node_id: nodeId, expected_focus_revision: expectedFocusRevision, checkpoint }),
    }, true);
  }

  saveCheckpoint(checkpoint: Focus['checkpoint'], expectedFocusRevision: number) {
    return this.request<Focus>('/focus/checkpoint', {
      method: 'PATCH', body: JSON.stringify({ checkpoint, expected_focus_revision: expectedFocusRevision }),
    });
  }

  createBranch(input: CreateBranchInput) {
    return this.request<{ branch: StudyNode; focus: Focus }>('/branches', { method: 'POST', body: JSON.stringify(input) }, true);
  }

  returnBranch(branchId: string, expectedFocusRevision: number) {
    return this.request<{ focus: Focus; return_event_id: string; job_id: string }>(`/branches/${branchId}/return`, {
      method: 'POST', body: JSON.stringify({ expected_focus_revision: expectedFocusRevision }),
    }, true);
  }

  saveRecord(nodeId: string, input: SaveRecordInput) {
    return this.request<{ record_ref: Ref; job_id?: string }>(`/nodes/${nodeId}/records`, { method: 'POST', body: JSON.stringify(input) }, true);
  }

  askTeacher(input: TeacherMessageInput) {
    return this.request<{ record_ref: Ref; job_id: string }>('/teacher/messages', { method: 'POST', body: JSON.stringify(input) }, true);
  }

  async listRecords(nodeId: string) {
    const result = await this.request<StudyRecord[] | { records: StudyRecord[] }>(`/nodes/${nodeId}/records`);
    return Array.isArray(result) ? result : result.records;
  }

  getJob(jobId: string) {
    return this.request<Job>(`/jobs/${jobId}`);
  }

  async retryJob(jobId: string) {
    const result = await this.request<Job | { job: Job }>(`/jobs/${jobId}/retry`, { method: 'POST' }, true);
    return 'job' in result ? result.job : result;
  }

  getReference(ref: Ref) {
    const query = new URLSearchParams({ kind: ref.kind, id: ref.id, revision: String(ref.revision) });
    if (ref.locator?.section) query.set('section', ref.locator.section);
    if (ref.locator?.page) query.set('page', String(ref.locator.page));
    return this.request<ReferenceContent>(`/refs?${query}`);
  }
}
