export type Id = string;

export type RefKind = 'source' | 'node' | 'route' | 'record' | 'exam_item';

export interface Ref {
  kind: RefKind;
  id: Id;
  revision: number;
  locator?: {
    section?: string;
    page?: number;
    label?: string;
    quote?: string;
    line_start?: number;
    line_end?: number;
    activity_id?: string;
  };
}

export interface LearningObjective {
  id: Id;
  text: string;
}

export interface Activity {
  id: Id;
  kind: string;
  objective_ids: Id[];
  prompt_md: string;
  source_refs: Ref[];
  solution_md?: string;
}

export interface Reading {
  intro_md: string;
  steps: string[];
  key_points: string[];
  source_refs: Ref[];
}

export type NodeKind = 'mainline' | 'branch' | 'predicted' | 'exam' | 'summary';

export interface StudyNode {
  id: Id;
  graph_id: Id;
  revision: number;
  kind: NodeKind;
  title: string;
  objectives: LearningObjective[];
  reading: Reading | null;
  activities: Activity[];
  source_refs: Ref[];
  origin_node_ref?: Ref;
  origin_refs?: Ref[];
  origin_checkpoint?: Checkpoint;
}

export interface StudyGraph {
  id: Id;
  mode: 'textbook' | 'goal';
  title: string;
  goal: string;
  status: 'preparing' | 'sparse' | 'ready';
}

export interface RouteEdge {
  kind: 'prerequisite' | 'related';
  from_node_id: Id;
  to_node_id: Id;
  target_objective_id?: Id;
  reason_md?: string;
}

export interface StudyRoute {
  id: Id;
  revision: number;
  graph_id: Id;
  kind: 'full' | 'core' | 'limited';
  title: string;
  node_ids: Id[];
  counted_node_ids: Id[];
  edges: RouteEdge[];
}

export interface Checkpoint {
  section_id?: string;
  record_ref?: Ref;
  [key: string]: unknown;
}

export interface Focus {
  graph_id: Id;
  node_id: Id;
  revision: number;
  checkpoint: Checkpoint;
  lock: null | { kind: 'exam'; attempt_id: Id };
}

export type RecordKind =
  | 'note'
  | 'question'
  | 'answer'
  | 'explanation'
  | 'exercise'
  | 'feedback'
  | 'branch_summary'
  | 'merge_summary'
  | 'exam_review';

export interface StudyRecord {
  id: Id;
  graph_id: Id;
  node_id: Id;
  revision: number;
  kind: RecordKind;
  body_md: string;
  refs: Ref[];
  created_at: string;
}

export interface Job {
  id: Id;
  kind: string;
  status: 'queued' | 'running' | 'succeeded' | 'needs_source' | 'failed';
  stage: string;
  result?: {
    record_ref?: Ref;
    used_refs?: Ref[];
    [key: string]: unknown;
  };
  error?: { code: string; message: string };
  updated_at: string;
  node_id?: Id;
}

export interface RouteProgress {
  route_id: Id;
  completed_count: number;
  counted_count: number;
}

export interface Workspace {
  focus: Focus;
  graphs: StudyGraph[];
  graph: StudyGraph;
  node: StudyNode;
  nodes: StudyNode[];
  routes: StudyRoute[];
  jobs: Job[];
  candidates: unknown[];
  milestones: unknown[];
  completions: { node_id: Id; marked_at: string }[];
  route_progress: RouteProgress[];
}

export interface SourceSection {
  title: string;
  excerpt_md: string;
}

export interface Source {
  id: Id;
  revision: number;
  media_type: string;
  title: string;
  url?: string;
  accessed_at?: string;
  sections: SourceSection[];
}

export interface ReferenceContent {
  ref: Ref;
  title: string;
  body_md: string;
  url?: string;
  node_id?: Id;
  status?: 'available' | 'revised' | 'unavailable';
}

export interface SaveRecordInput {
  kind: RecordKind;
  body_md: string;
  refs: Ref[];
  action: 'save_draft' | 'save' | 'finish_expression';
  expected_focus_revision: number;
}

export interface CreateBranchInput {
  expected_focus_revision: number;
  title: string;
  question_md: string;
  origin_refs: Ref[];
  checkpoint: Checkpoint;
}

export interface TeacherMessageInput {
  message_md: string;
  expected_focus_revision: number;
  refs: Ref[];
  intent?: 'ask' | 'check' | 'practice' | 'suggest_next';
}
