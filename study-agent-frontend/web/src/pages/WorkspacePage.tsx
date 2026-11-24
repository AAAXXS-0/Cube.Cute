import { useCallback, useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  ArrowLeft,
  ArrowRight,
  BookMarked,
  Check,
  CornerDownRight,
  FileText,
  GitBranch,
  Link2,
  MessageCircle,
  PenLine,
  Send,
  Sparkles,
} from 'lucide-react';
import { useParams, useSearchParams } from 'react-router-dom';
import { studyApi, StudyApiError } from '@/api';
import { GraphNavigator } from '@/components/GraphNavigator';
import { JobBanner } from '@/components/JobBanner';
import { Markdown } from '@/components/Markdown';
import { ReferenceDrawer } from '@/components/ReferenceDrawer';
import type { Job, RecordKind, Ref, SaveRecordInput, StudyNode, StudyRecord } from '@/types';

function useLocalDraft(key: string) {
  const storageKey = `xuxue.draft.${key}`;
  const [values, setValues] = useState<Record<string, string>>({});
  const [saved, setSaved] = useState(true);
  const value = values[storageKey] ?? localStorage.getItem(storageKey) ?? '';

  const updateValue = (next: string) => {
    localStorage.setItem(storageKey, next);
    setValues((current) => ({ ...current, [storageKey]: next }));
    setSaved(false);
  };

  useEffect(() => {
    if (saved) return;
    const timer = window.setTimeout(() => {
      setSaved(true);
    }, 250);
    return () => window.clearTimeout(timer);
  }, [storageKey, value, saved]);

  return { value, setValue: updateValue, saved, storageKey };
}

function refLabel(ref: Ref, nodes: StudyNode[]) {
  if (ref.kind === 'source') return ref.locator?.section ?? `教材 ${ref.id}`;
  if (ref.kind === 'node') return nodes.find((node) => node.id === ref.id)?.title ?? `节点 ${ref.id}`;
  if (ref.kind === 'record') return `原记录 ${ref.id.replace(/^rec_/, '')}`;
  return `${ref.kind} ${ref.id}`;
}

function ReferenceLinks({ refs, nodes, onOpen }: { refs: Ref[]; nodes: StudyNode[]; onOpen: (ref: Ref) => void }) {
  if (!refs.length) return null;
  return (
    <div className="reference-links" aria-label="本条记录的引用">
      {refs.map((ref) => <button key={`${ref.kind}-${ref.id}-${ref.revision}-${ref.locator?.section ?? ''}`} onClick={() => onOpen(ref)}><Link2 size={12} />{refLabel(ref, nodes)}<span>v{ref.revision}</span></button>)}
    </div>
  );
}

function RecordTimeline({ records, nodes, onOpenRef }: { records: StudyRecord[]; nodes: StudyNode[]; onOpenRef: (ref: Ref) => void }) {
  if (!records.length) {
    return <div className="timeline-empty"><MessageCircle size={25} /><strong>从你的第一个问题开始</strong><p>浏览其他节点不会移动学习焦点。你的提问、表达和 Teacher 回复都会留在这里。</p></div>;
  }
  return (
    <div className="record-timeline">
      {records.map((record) => {
        const isAnswer = record.kind === 'answer';
        const label: Record<RecordKind, string> = {
          note: '学习笔记', question: '你的问题', answer: 'Teacher', explanation: '完整表达', exercise: '练习', feedback: '理解反馈',
          branch_summary: '支线成果', merge_summary: '整理', exam_review: '复盘',
        };
        return (
          <article key={`${record.id}-${record.revision}`} className={`record-item ${isAnswer ? 'teacher-record' : ''}`}>
            <div className={`record-avatar ${isAnswer ? 'teacher' : ''}`}>{isAnswer ? <Sparkles size={15} /> : <PenLine size={14} />}</div>
            <div className="record-body">
              <div className="record-meta"><strong>{label[record.kind]}</strong><span>{new Intl.DateTimeFormat('zh-CN', { hour: '2-digit', minute: '2-digit' }).format(new Date(record.created_at))}</span><span>v{record.revision}</span></div>
              <Markdown>{record.body_md}</Markdown>
              <ReferenceLinks refs={record.refs} nodes={nodes} onOpen={onOpenRef} />
            </div>
          </article>
        );
      })}
    </div>
  );
}

export function WorkspacePage() {
  const { graphId = 'g_network' } = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const requestedNodeId = searchParams.get('node') ?? undefined;
  const queryClient = useQueryClient();
  const [routeId, setRouteId] = useState('route_net_full');
  const [reference, setReference] = useState<Ref | null>(null);
  const [activeJobId, setActiveJobId] = useState<string>();
  const [branchOpen, setBranchOpen] = useState(false);
  const [branchTitle, setBranchTitle] = useState('');
  const [branchQuestion, setBranchQuestion] = useState('');
  const [toast, setToast] = useState('');
  const closeReference = useCallback(() => setReference(null), []);

  const workspaceQuery = useQuery({
    queryKey: ['workspace', graphId, requestedNodeId ?? 'focus'],
    queryFn: () => studyApi.getWorkspace(graphId, requestedNodeId),
  });
  const workspace = workspaceQuery.data;
  const focusNode = workspace?.nodes.find((node) => node.id === workspace.focus.node_id);
  const viewedNode = workspace?.node;
  const focusId = focusNode?.id ?? 'loading';
  const questionDraft = useLocalDraft(`question:${focusId}`);
  const noteDraft = useLocalDraft(`note:${focusId}`);

  const recordsQuery = useQuery({
    queryKey: ['records', focusId],
    queryFn: () => studyApi.listRecords(focusId),
    enabled: Boolean(focusNode),
  });

  const latestAvailableJob = useMemo(() => {
    if (!workspace || !focusNode) return undefined;
    return workspace.jobs.filter((job) => job.node_id === focusNode.id && job.status !== 'succeeded').at(-1);
  }, [workspace, focusNode]);
  const jobId = activeJobId ?? latestAvailableJob?.id;
  const jobQuery = useQuery({
    queryKey: ['job', jobId],
    queryFn: () => studyApi.getJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => query.state.data?.status === 'running' || query.state.data?.status === 'queued' ? 250 : false,
  });
  const visibleJob: Job | undefined = jobQuery.data ?? latestAvailableJob;

  useEffect(() => {
    if (visibleJob?.status === 'succeeded') {
      void queryClient.invalidateQueries({ queryKey: ['records', focusId] });
      void queryClient.invalidateQueries({ queryKey: ['workspace'] });
    }
  }, [visibleJob?.status, focusId, queryClient]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(''), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const invalidateWorkspace = async () => {
    await queryClient.invalidateQueries({ queryKey: ['workspace'] });
    await queryClient.invalidateQueries({ queryKey: ['records'] });
  };

  const browse = (nodeId: string) => {
    setSearchParams(nodeId === focusId ? {} : { node: nodeId });
  };

  const focusMutation = useMutation({
    mutationFn: (nodeId: string) => studyApi.startFocus(nodeId, workspace!.focus.revision),
    onSuccess: async ({ focus }) => {
      setActiveJobId(undefined);
      browse(focus.node_id);
      await invalidateWorkspace();
      setToast('学习焦点已切换，原节点的草稿与记录仍已保留。');
    },
  });

  const askMutation = useMutation({
    mutationFn: () => {
      const refs = viewedNode && focusNode && viewedNode.id !== focusNode.id
        ? [{ kind: 'node', id: viewedNode.id, revision: viewedNode.revision } as Ref, ...viewedNode.source_refs]
        : [];
      return studyApi.askTeacher({
        message_md: questionDraft.value,
        expected_focus_revision: workspace!.focus.revision,
        refs,
        intent: 'ask',
      });
    },
    onSuccess: async ({ job_id }) => {
      setActiveJobId(job_id);
      questionDraft.setValue('');
      localStorage.removeItem(questionDraft.storageKey);
      await queryClient.invalidateQueries({ queryKey: ['records', focusId] });
      await queryClient.invalidateQueries({ queryKey: ['workspace'] });
    },
  });

  const saveNoteMutation = useMutation({
    mutationFn: (action: SaveRecordInput['action']) => studyApi.saveRecord(focusId, {
      kind: action === 'save_draft' ? 'note' : 'explanation',
      body_md: noteDraft.value,
      refs: viewedNode && viewedNode.id !== focusId ? viewedNode.source_refs : focusNode?.source_refs ?? [],
      action,
      expected_focus_revision: workspace!.focus.revision,
    }),
    onSuccess: async ({ record_ref }, action) => {
      await queryClient.invalidateQueries({ queryKey: ['records', focusId] });
      setToast(action === 'save_draft' ? `草稿已保存为 v${record_ref.revision}` : `这段表达已保存为 v${record_ref.revision}，可在记录中回查。`);
    },
  });

  const branchMutation = useMutation({
    mutationFn: () => {
      const records = recordsQuery.data ?? [];
      const lastQuestion = [...records].reverse().find((record) => record.kind === 'question');
      const originRefs = lastQuestion
        ? [{ kind: 'record', id: lastQuestion.id, revision: lastQuestion.revision } as Ref]
        : [{ kind: 'node', id: focusId, revision: focusNode!.revision } as Ref];
      return studyApi.createBranch({
        expected_focus_revision: workspace!.focus.revision,
        title: branchTitle,
        question_md: branchQuestion,
        origin_refs: originRefs,
        checkpoint: {
          section_id: workspace!.focus.checkpoint.section_id ?? 'reading',
          ...(lastQuestion ? { record_ref: { kind: 'record', id: lastQuestion.id, revision: lastQuestion.revision } as Ref } : {}),
        },
      });
    },
    onSuccess: async ({ branch }) => {
      setBranchOpen(false);
      setActiveJobId(undefined);
      setSearchParams({ node: branch.id });
      await invalidateWorkspace();
      setToast('已进入支线。返回时会恢复这里的原问题与阅读位置。');
    },
  });

  const returnMutation = useMutation({
    mutationFn: () => studyApi.returnBranch(focusId, workspace!.focus.revision),
    onSuccess: async ({ job_id }) => {
      setActiveJobId(job_id);
      setSearchParams({});
      await invalidateWorkspace();
      setToast('已恢复原学习位置，正在接续这次支线成果。');
    },
  });

  const retryMutation = useMutation({
    mutationFn: (id: string) => studyApi.retryJob(id),
    onSuccess: async (job) => {
      setActiveJobId(job.id);
      await queryClient.invalidateQueries({ queryKey: ['job', job.id] });
    },
  });

  const openBranchDialog = () => {
    if (!focusNode) return;
    const lastQuestion = [...(recordsQuery.data ?? [])].reverse().find((record) => record.kind === 'question');
    setBranchTitle(`深入：${focusNode.title}`);
    setBranchQuestion(questionDraft.value || lastQuestion?.body_md || noteDraft.value);
    setBranchOpen(true);
  };

  const submitQuestion = (event: FormEvent) => {
    event.preventDefault();
    askMutation.mutate();
  };

  if (workspaceQuery.isPending) {
    return <main className="workspace-loading"><span className="loading-mark">续</span><span className="spinner" /><p>正在恢复你的学习位置…</p></main>;
  }
  if (workspaceQuery.isError || !workspace || !focusNode || !viewedNode) {
    return <main className="workspace-loading"><h1>工作台暂时没有打开</h1><p>{workspaceQuery.error?.message ?? '样例节点不完整。'}</p><button className="button primary" onClick={() => void workspaceQuery.refetch()}>重新加载</button></main>;
  }

  const isBrowsingElsewhere = viewedNode.id !== focusNode.id;
  const isBranch = focusNode.kind === 'branch';
  const currentRefs = isBrowsingElsewhere ? viewedNode.source_refs : [];
  const actionError = askMutation.error ?? saveNoteMutation.error ?? focusMutation.error ?? branchMutation.error ?? returnMutation.error;
  const savedBranchWork = (recordsQuery.data ?? []).some((record) => record.node_id === focusId && record.kind === 'explanation');

  return (
    <main className="workspace-page page-enter">
      <section className="focus-strip" aria-label="学习与浏览状态">
        <div className="focus-state current"><span><i />当前学习</span><strong>{focusNode.title}</strong><small>焦点版本 v{workspace.focus.revision}</small></div>
        <CornerDownRight size={19} className="focus-arrow" />
        <div className={`focus-state viewing ${isBrowsingElsewhere ? 'different' : ''}`}><span>正在查看</span><strong>{viewedNode.title}</strong><small>{isBrowsingElsewhere ? `提问记在 ${focusNode.title} · 引用 ${viewedNode.title}` : '阅读与提问在同一节点'}</small></div>
        <div className="focus-actions">
          {isBranch ? <button className="button return-button" onClick={() => returnMutation.mutate()} disabled={returnMutation.isPending || !savedBranchWork} title={!savedBranchWork ? '先保存一段支线成果' : '返回出发节点'}><ArrowLeft size={16} />{returnMutation.isPending ? '正在返回' : `返回 ${workspace.nodes.find((node) => node.id === focusNode.origin_node_ref?.id)?.title ?? '原处'}`}</button> : <button className="button branch-button" onClick={openBranchDialog}><GitBranch size={16} />由此开支线</button>}
          {isBrowsingElsewhere && viewedNode.id !== focusNode.origin_node_ref?.id && <button className="button primary compact" onClick={() => focusMutation.mutate(viewedNode.id)} disabled={focusMutation.isPending}>在此学习<ArrowRight size={15} /></button>}
        </div>
      </section>

      {visibleJob && <JobBanner job={visibleJob} retrying={retryMutation.isPending} onRetry={() => retryMutation.mutate(visibleJob.id)} />}
      {actionError && <div className="action-error" role="alert"><strong>{actionError instanceof StudyApiError ? actionError.code : 'ACTION_FAILED'}</strong><span>{actionError.message}</span><button onClick={() => { askMutation.reset(); saveNoteMutation.reset(); focusMutation.reset(); branchMutation.reset(); returnMutation.reset(); }}>知道了</button></div>}

      <div className="workspace-grid">
        <GraphNavigator nodes={workspace.nodes} routes={workspace.routes} progress={workspace.route_progress} focusNodeId={focusNode.id} viewedNodeId={viewedNode.id} selectedRouteId={routeId} onRouteChange={setRouteId} onBrowse={browse} />

        <section className="reading-panel" aria-labelledby="reading-title">
          <div className="reading-scroll">
            <div className="reading-kicker"><span>{viewedNode.kind === 'branch' ? 'BRANCH EXPLORATION' : 'GUIDED READING'}</span><span>节点版本 v{viewedNode.revision}</span></div>
            <h1 id="reading-title">{viewedNode.title}</h1>
            <p className="reading-goal">{viewedNode.objectives[0]?.text}</p>

            {viewedNode.reading ? (
              <>
                <div className="reading-intro"><BookMarked size={20} /><Markdown>{viewedNode.reading.intro_md}</Markdown></div>
                <section className="reading-section"><h2>从这里开始</h2><ol className="reading-steps">{viewedNode.reading.steps.map((step) => <li key={step}>{step}</li>)}</ol></section>
                <section className="key-point"><span>本段关键</span>{viewedNode.reading.key_points.map((point) => <p key={point}>{point}</p>)}</section>
                {viewedNode.source_refs.map((ref) => <button className="source-card" key={`${ref.id}-${ref.locator?.section}`} onClick={() => setReference(ref)}><span className="source-icon"><FileText size={20} /></span><span><small>精确出处 · v{ref.revision}</small><strong>{ref.locator?.section ?? '教材原文'}</strong><em>打开引用不会切换学习焦点</em></span><ArrowRight size={17} /></button>)}
              </>
            ) : (
              <div className="branch-origin"><GitBranch size={22} /><span>这条支线从你的主动追问开始</span><h2>{focusNode.origin_node_ref ? `来路：${workspace.nodes.find((node) => node.id === focusNode.origin_node_ref?.id)?.title}` : '自由探索'}</h2><p>先写下自己的判断、推导或仍未解决的问题。保存一段成果后，就可以返回原处续学。</p></div>
            )}

            {viewedNode.activities.map((activity) => <section className="activity-card" key={activity.id}><span>CHECKPOINT</span><h2>试着说清楚</h2><Markdown>{activity.prompt_md}</Markdown></section>)}

            <section className="expression-card">
              <div className="expression-heading"><div><span>YOUR EXPRESSION</span><h2>{isBranch ? '留下这次支线的成果' : '用自己的话写一段'}</h2></div><span className="draft-status"><i className={noteDraft.saved ? 'saved' : ''} />{noteDraft.saved ? '草稿已保存在本机' : '正在保存草稿'}</span></div>
              <textarea aria-label="学习理解编辑器" value={noteDraft.value} onChange={(event) => noteDraft.setValue(event.target.value)} placeholder={isBranch ? '例如：解析器 10:00:00 取得旧地址，TTL 为 120 秒……' : '写下你的理解、推导或还没有想清楚的一步。支持 Markdown。'} />
              <div className="expression-footer"><span>不会在输入过程中自动补全或打断。</span><div><button className="button ghost" onClick={() => saveNoteMutation.mutate('save_draft')} disabled={saveNoteMutation.isPending || !noteDraft.value.trim()}>保存草稿</button><button className="button primary" onClick={() => saveNoteMutation.mutate('finish_expression')} disabled={saveNoteMutation.isPending || !noteDraft.value.trim()}><Check size={15} />{isBranch ? '保存支线成果' : '这段写完了'}</button></div></div>
            </section>
          </div>
        </section>

        <aside className="teacher-panel" aria-label="Teacher 与学习记录">
          <div className="teacher-heading"><div><span className="teacher-title"><Sparkles size={16} />Teacher</span><strong>记录在「{focusNode.title}」</strong></div><span className="online-dot">本地就绪</span></div>
          <div className="records-scroll">
            <RecordTimeline records={recordsQuery.data ?? []} nodes={workspace.nodes} onOpenRef={setReference} />
          </div>
          <form className="question-composer" onSubmit={submitQuestion}>
            {isBrowsingElsewhere && <div className="question-context"><span>提问记在 <strong>{focusNode.title}</strong></span><button type="button" onClick={() => currentRefs[0] && setReference(currentRefs[0])}><Link2 size={12} />引用 {viewedNode.title}</button></div>}
            <textarea aria-label="向 Teacher 提问" value={questionDraft.value} onChange={(event) => questionDraft.setValue(event.target.value)} placeholder={isBrowsingElsewhere ? `就「${viewedNode.title}」问一点什么…` : '把疑问留给 Teacher…'} onKeyDown={(event) => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') { event.preventDefault(); if (questionDraft.value.trim()) askMutation.mutate(); } }} />
            <div className="composer-footer"><span>{questionDraft.saved ? '草稿已保留' : '保存中'} · Ctrl ↵</span><button className="send-button" type="submit" aria-label="发送问题" disabled={askMutation.isPending || !questionDraft.value.trim()}>{askMutation.isPending ? <span className="spinner" /> : <Send size={17} />}</button></div>
          </form>
        </aside>
      </div>

      {branchOpen && <div className="dialog-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) setBranchOpen(false); }}><section className="branch-dialog" role="dialog" aria-modal="true" aria-labelledby="branch-dialog-title"><div className="dialog-icon"><GitBranch size={23} /></div><span className="reading-kicker">NEW BRANCH</span><h2 id="branch-dialog-title">从「{focusNode.title}」开一条支线</h2><p>会保存当前问题与出发断点。支线不是新的课程，返回后仍从这里接续。</p><label>支线名称<input autoFocus value={branchTitle} onChange={(event) => setBranchTitle(event.target.value)} /></label><label>想弄清什么<textarea value={branchQuestion} onChange={(event) => setBranchQuestion(event.target.value)} /></label><div className="dialog-actions"><button className="button ghost" onClick={() => setBranchOpen(false)}>留在原处</button><button className="button primary" onClick={() => branchMutation.mutate()} disabled={branchMutation.isPending || !branchTitle.trim() || !branchQuestion.trim()}><GitBranch size={15} />{branchMutation.isPending ? '正在创建' : '创建并进入支线'}</button></div></section></div>}
      <ReferenceDrawer reference={reference} onClose={closeReference} />
      {toast && <div className="toast" role="status"><Check size={16} />{toast}</div>}
    </main>
  );
}
