import { Check, GitBranch, Route } from 'lucide-react';
import type { RouteProgress, StudyNode, StudyRoute } from '@/types';

interface GraphNavigatorProps {
  nodes: StudyNode[];
  routes: StudyRoute[];
  progress: RouteProgress[];
  focusNodeId: string;
  viewedNodeId: string;
  selectedRouteId: string;
  onRouteChange: (routeId: string) => void;
  onBrowse: (nodeId: string) => void;
}

const positions: Record<string, { x: number; y: number }> = {
  node_a: { x: 32, y: 38 },
  node_b: { x: 118, y: 38 },
  node_c: { x: 204, y: 38 },
  node_e: { x: 204, y: 112 },
};

function nodeShortLabel(node: StudyNode, route?: StudyRoute) {
  if (node.kind === 'branch') return 'S';
  if (node.kind === 'exam') return 'T';
  const index = route?.node_ids.indexOf(node.id) ?? -1;
  return index >= 0 ? String.fromCharCode(65 + index) : '·';
}

export function GraphNavigator({ nodes, routes, progress, focusNodeId, viewedNodeId, selectedRouteId, onRouteChange, onBrowse }: GraphNavigatorProps) {
  const route = routes.find((item) => item.id === selectedRouteId) ?? routes[0];
  const routeNodes = route ? route.node_ids.map((id) => nodes.find((node) => node.id === id)).filter((node): node is StudyNode => Boolean(node)) : nodes;
  const branches = nodes.filter((node) => node.kind === 'branch');
  const visibleNodes = [...routeNodes, ...branches];
  const currentProgress = progress.find((item) => item.route_id === route?.id);

  return (
    <aside className="graph-panel" aria-label="学习图导航">
      <div className="panel-heading">
        <span><Route size={15} />学习路线</span>
        {currentProgress && <span className="progress-count">{currentProgress.completed_count}/{currentProgress.counted_count}</span>}
      </div>
      <select className="route-select" aria-label="切换学习路线" value={route?.id ?? ''} onChange={(event) => onRouteChange(event.target.value)}>
        {routes.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
      </select>

      <div className="mini-map">
        <svg viewBox="0 0 236 142" role="img" aria-label="学习节点关系图">
          {route?.edges.map((edge) => {
            const from = positions[edge.from_node_id];
            const to = positions[edge.to_node_id];
            if (!from || !to) return null;
            return <line key={`${edge.from_node_id}-${edge.to_node_id}`} x1={from.x + 13} y1={from.y} x2={to.x - 13} y2={to.y} className={`map-edge ${edge.kind}`} />;
          })}
          {branches.map((branch, index) => {
            const origin = positions[branch.origin_node_ref?.id ?? 'node_a'] ?? positions.node_a;
            const target = { x: 32 + (index % 3) * 50, y: 112 };
            return <line key={`edge-${branch.id}`} x1={origin.x} y1={origin.y + 13} x2={target.x} y2={target.y - 13} className="map-edge branch" />;
          })}
          {visibleNodes.map((node) => {
            const branchIndex = branches.findIndex((item) => item.id === node.id);
            const position = node.kind === 'branch' ? { x: 32 + (branchIndex % 3) * 50, y: 112 } : positions[node.id];
            if (!position) return null;
            const isFocus = node.id === focusNodeId;
            const isViewed = node.id === viewedNodeId;
            return (
              <g
                key={node.id}
                transform={`translate(${position.x}, ${position.y})`}
                className={`map-node ${node.kind} ${isFocus ? 'is-focus' : ''} ${isViewed ? 'is-viewed' : ''}`}
                role="button"
                tabIndex={0}
                aria-label={`查看 ${node.title}`}
                onClick={() => onBrowse(node.id)}
                onKeyDown={(event) => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); onBrowse(node.id); } }}
              >
                <circle r="14" />
                <text textAnchor="middle" dominantBaseline="central">{nodeShortLabel(node, route)}</text>
              </g>
            );
          })}
        </svg>
        <div className="map-legend"><span><i className="legend-dot focus" />当前学习</span><span><i className="legend-ring" />正在查看</span></div>
      </div>

      <nav className="node-list" aria-label="节点列表">
        {visibleNodes.map((node) => {
          const isFocus = node.id === focusNodeId;
          const isViewed = node.id === viewedNodeId;
          return (
            <button key={node.id} className={`node-list-item ${isViewed ? 'is-viewed' : ''}`} onClick={() => onBrowse(node.id)} aria-current={isViewed ? 'page' : undefined}>
              <span className={`node-letter ${node.kind}`}>{node.kind === 'branch' ? <GitBranch size={14} /> : nodeShortLabel(node, route)}</span>
              <span className="node-list-copy"><strong>{node.title}</strong><small>{node.kind === 'branch' ? '自主支线' : node.kind === 'exam' ? '综合自测' : node.objectives[0]?.text}</small></span>
              {isFocus && <span className="focus-mark" title="当前学习"><Check size={13} /></span>}
            </button>
          );
        })}
      </nav>
      {route?.edges.find((edge) => edge.kind === 'prerequisite') && (
        <div className="prerequisite-note">
          <span>前置关系</span>
          <p>{route.edges.find((edge) => edge.kind === 'prerequisite')?.reason_md}</p>
        </div>
      )}
    </aside>
  );
}
