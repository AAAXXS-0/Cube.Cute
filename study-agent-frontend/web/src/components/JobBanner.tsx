import { AlertCircle, RotateCcw } from 'lucide-react';
import type { Job } from '@/types';

export function JobBanner({ job, retrying, onRetry }: { job: Job; retrying: boolean; onRetry: () => void }) {
  if (job.status === 'succeeded') return null;
  if (job.status === 'failed' || job.status === 'needs_source') {
    return (
      <div className="job-banner failed" role="alert">
        <AlertCircle size={18} />
        <div><strong>{job.kind === 'resume_branch' ? '续学暂时没有完成' : '回答暂时没有完成'}</strong><p>{job.error?.message ?? '服务返回了需要处理的状态。'}</p></div>
        <button className="button secondary compact" onClick={onRetry} disabled={retrying}><RotateCcw size={14} />{retrying ? '重试中' : '重试这次接续'}</button>
      </div>
    );
  }
  return (
    <div className="job-banner" role="status">
      <span className="spinner" />
      <div><strong>{job.kind === 'resume_branch' ? '正在接续' : 'Teacher 正在整理回答'}</strong><p>{job.kind === 'resume_branch' ? '原处已恢复，正在读取这次支线的实际成果。你可以继续浏览。' : '回答会留在发起时的学习节点，不会因浏览位置改变而丢失。'}</p></div>
    </div>
  );
}
