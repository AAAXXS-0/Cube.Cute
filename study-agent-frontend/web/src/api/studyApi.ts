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

export class StudyApiError extends Error {
  constructor(
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = 'StudyApiError';
  }
}

export interface StudyApi {
  getWorkspace(graphId: string, nodeId?: string): Promise<Workspace>;
  startFocus(nodeId: string, expectedFocusRevision: number, checkpoint?: Focus['checkpoint']): Promise<{ focus: Focus; node: StudyNode }>;
  saveCheckpoint(checkpoint: Focus['checkpoint'], expectedFocusRevision: number): Promise<Focus>;
  createBranch(input: CreateBranchInput): Promise<{ branch: StudyNode; focus: Focus }>;
  returnBranch(branchId: string, expectedFocusRevision: number): Promise<{ focus: Focus; return_event_id: string; job_id: string }>;
  saveRecord(nodeId: string, input: SaveRecordInput): Promise<{ record_ref: Ref; job_id?: string }>;
  askTeacher(input: TeacherMessageInput): Promise<{ record_ref: Ref; job_id: string }>;
  listRecords(nodeId: string): Promise<StudyRecord[]>;
  getJob(jobId: string): Promise<Job>;
  retryJob(jobId: string): Promise<Job>;
  getReference(ref: Ref): Promise<ReferenceContent>;
}
