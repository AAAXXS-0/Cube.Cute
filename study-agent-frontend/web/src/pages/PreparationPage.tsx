import { ArrowLeft, BookOpen, Compass } from 'lucide-react';
import { Link } from 'react-router-dom';

export function PreparationPage({ mode }: { mode: 'textbook' | 'goal' }) {
  const textbook = mode === 'textbook';
  return (
    <main className="preparation-page page-enter">
      <Link to="/graphs" className="back-link"><ArrowLeft size={16} />返回学习图</Link>
      <div className="preparation-icon">{textbook ? <BookOpen size={32} /> : <Compass size={32} />}</div>
      <span className="hero-index">{textbook ? 'TEXTBOOK INTAKE' : 'GOAL INTAKE'} / v0.2.0</span>
      <h1>{textbook ? '从一本教材，建立完整主线。' : '从一个目标，开始自由探索。'}</h1>
      <p>{textbook ? '将在这里确认学习目的、期限与范围，上传教材并跟踪解析、编排、验收和发布状态。' : '将在这里编辑近期里程碑，查看 Teacher 准备的候选、推荐理由与公开来源，再决定是否采纳。'}</p>
      <div className="version-notice"><strong>当前版本先专注核心学习链路</strong><span>教材与目标准备将在 v0.2.0 接入；v0.1.0 请从样例学习图进入工作台。</span></div>
      <Link to="/workspace/g_network" className="button primary">进入样例工作台</Link>
    </main>
  );
}
