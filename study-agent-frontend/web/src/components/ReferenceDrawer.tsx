import { useEffect, useRef } from 'react';
import { useQuery } from '@tanstack/react-query';
import { ExternalLink, FileText, X } from 'lucide-react';
import { studyApi } from '@/api';
import type { Ref } from '@/types';
import { Markdown } from './Markdown';

export function ReferenceDrawer({ reference, onClose }: { reference: Ref | null; onClose: () => void }) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const query = useQuery({
    queryKey: ['reference', reference],
    queryFn: () => studyApi.getReference(reference!),
    enabled: Boolean(reference),
    retry: false,
  });

  useEffect(() => {
    if (!reference) return;
    closeRef.current?.focus();
    const onKeyDown = (event: KeyboardEvent) => { if (event.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [reference, onClose]);

  if (!reference) return null;
  const locator = reference.locator?.section ?? (reference.locator?.page ? `第 ${reference.locator.page} 页` : '原文记录');

  return (
    <div className="drawer-layer" onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <aside className="reference-drawer" role="dialog" aria-modal="true" aria-labelledby="reference-title">
        <div className="drawer-topline"><span><FileText size={15} />出处回查</span><button ref={closeRef} className="icon-button" onClick={onClose} aria-label="关闭出处"><X size={19} /></button></div>
        {query.isPending && <div className="reference-loading"><span className="spinner" />正在读取第 {reference.revision} 版原文…</div>}
        {query.isError && <div className="reference-error"><span>REF_UNAVAILABLE</span><h2>暂时读不到这份出处</h2><p>{query.error.message}</p><button className="button secondary" onClick={() => void query.refetch()}>重新读取</button></div>}
        {query.data && (
          <div className="reference-content">
            <div className="reference-kicker">{query.data.ref.kind.toUpperCase()} · REV {query.data.ref.revision}</div>
            <h2 id="reference-title">{query.data.title}</h2>
            <div className="reference-meta"><span>{locator}</span><span>冻结版本 v{query.data.ref.revision}</span></div>
            <blockquote className="original-quote"><Markdown>{query.data.body_md}</Markdown></blockquote>
            <p className="reference-assurance">此处展示引用登记时的版本，打开出处不会改变当前学习焦点。</p>
            {query.data.url && <a className="button secondary" href={query.data.url} target="_blank" rel="noreferrer">打开原始来源<ExternalLink size={15} /></a>}
          </div>
        )}
      </aside>
    </div>
  );
}
