import { useQuery } from '@tanstack/react-query';
import { ArrowRight, BookOpen, Compass, Network } from 'lucide-react';
import { Link } from 'react-router-dom';
import { studyApi } from '@/api';

export function GraphsPage() {
  const workspace = useQuery({ queryKey: ['workspace', 'g_network', 'focus'], queryFn: () => studyApi.getWorkspace('g_network') });
  return (
    <main className="graphs-page page-enter">
      <section className="graphs-hero">
        <div className="hero-index">STUDY ATLAS / 01</div>
        <h1>让每一次偏离，<br /><em>都能回到原处。</em></h1>
        <p>主线、兴趣支线与旧记录不再彼此割裂。你可以自由查看，始终知道学习发生在哪里。</p>
      </section>
      <section className="graph-collection" aria-label="我的学习图">
        <div className="section-heading"><span>我的学习图</span><span>1 张进行中的图</span></div>
        <Link to="/workspace/g_network" className="graph-card">
          <div className="graph-card-icon"><Network size={25} /></div>
          <div className="graph-card-copy"><span className="status-pill">教材主线 · 已开放</span><h2>{workspace.data?.graph.title ?? '计算机网络示例'}</h2><p>{workspace.data?.graph.goal}</p><div className="graph-card-meta"><span>3 个主线节点</span><span>2 条路线</span><span>本地可恢复</span></div></div>
          <span className="graph-card-action">进入工作台<ArrowRight size={18} /></span>
        </Link>
        <div className="entry-grid">
          <Link to="/prepare/textbook" className="entry-card"><BookOpen size={22} /><div><h3>从教材开始</h3><p>确认目标与范围，整门课备齐后开放。</p></div><span>v0.2.0</span></Link>
          <Link to="/prepare/goal" className="entry-card"><Compass size={22} /><div><h3>从目标开始</h3><p>先定里程碑，再采纳有出处的候选。</p></div><span>v0.2.0</span></Link>
        </div>
      </section>
    </main>
  );
}
