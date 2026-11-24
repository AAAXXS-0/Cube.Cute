import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { BookOpen, Compass, FlaskConical, Network, RotateCcw } from 'lucide-react';
import { NavLink, Navigate, Outlet, Route, Routes } from 'react-router-dom';
import { apiMode, mockApi } from '@/api';
import { GraphsPage } from '@/pages/GraphsPage';
import { PreparationPage } from '@/pages/PreparationPage';
import { WorkspacePage } from '@/pages/WorkspacePage';

function MockControls() {
  const queryClient = useQueryClient();
  const api = mockApi;
  const [failNext, setFailNext] = useState(api?.getSettings().failNextResume ?? false);
  if (!api) return null;
  const toggleFailure = (enabled: boolean) => { api.setResumeFailure(enabled); setFailNext(enabled); };
  const reset = () => {
    Object.keys(localStorage).filter((key) => key.startsWith('xuxue.draft.')).forEach((key) => localStorage.removeItem(key));
    api.reset();
    void queryClient.resetQueries();
    window.location.assign('/workspace/g_network');
  };
  return (
    <details className="mock-controls">
      <summary><FlaskConical size={14} />Mock</summary>
      <div className="mock-popover">
        <strong>本地联调控制</strong>
        <label><input type="checkbox" checked={failNext} onChange={(event) => toggleFailure(event.target.checked)} />下次续学返回失败</label>
        <button onClick={reset}><RotateCcw size={14} />重置 A/B/S 样例</button>
        <span>数据仅保存在当前浏览器。</span>
      </div>
    </details>
  );
}

function AppShell() {
  return (
    <div className="app-shell">
      <header className="app-header">
        <NavLink to="/graphs" className="brand" aria-label="续学首页"><span className="brand-symbol">续</span><span><strong>续学</strong><small>STUDY ATLAS</small></span></NavLink>
        <nav className="main-nav" aria-label="主导航">
          <NavLink to="/graphs"><Network size={16} />学习图</NavLink>
          <NavLink to="/prepare/textbook"><BookOpen size={16} />教材准备</NavLink>
          <NavLink to="/prepare/goal"><Compass size={16} />目标准备</NavLink>
        </nav>
        <div className="header-meta"><span className={`mode-badge ${apiMode}`}>{apiMode === 'mock' ? 'LOCAL MOCK' : 'API'}</span><MockControls /><span className="version">v0.1.0</span></div>
      </header>
      <Outlet />
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<Navigate to="/graphs" replace />} />
        <Route path="/graphs" element={<GraphsPage />} />
        <Route path="/workspace/:graphId" element={<WorkspacePage />} />
        <Route path="/prepare/textbook" element={<PreparationPage mode="textbook" />} />
        <Route path="/prepare/goal" element={<PreparationPage mode="goal" />} />
        <Route path="*" element={<Navigate to="/graphs" replace />} />
      </Route>
    </Routes>
  );
}
