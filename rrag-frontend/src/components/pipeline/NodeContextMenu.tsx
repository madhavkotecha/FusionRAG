import { useRef, useEffect } from 'react';
import { Copy, Trash2, Group, Clipboard } from 'lucide-react';
import { usePipelineEditorStore } from '../../stores/pipeline-editor.store';

export interface NodeContextMenuState {
  x: number;
  y: number;
  nodeId: string;
}

interface NodeContextMenuProps {
  state: NodeContextMenuState;
  onClose: () => void;
  onGroup?: () => void;
}

export function NodeContextMenu({ state, onClose, onGroup }: NodeContextMenuProps) {
  const menuRef = useRef<HTMLDivElement>(null);
  const { duplicateNode, removeNode } = usePipelineEditorStore();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) onClose();
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') onClose(); };
    document.addEventListener('keydown', handler);
    return () => document.removeEventListener('keydown', handler);
  }, [onClose]);

  const items = [
    { icon: Copy, label: 'Duplicate', shortcut: 'Ctrl+D', action: () => { duplicateNode(state.nodeId); onClose(); } },
    ...(onGroup ? [{ icon: Group, label: 'Group Selected', shortcut: 'Ctrl+G', action: () => { onGroup(); onClose(); } }] : []),
    { icon: Clipboard, label: 'Copy Config', action: () => {
      const node = usePipelineEditorStore.getState().nodes.find(n => n.id === state.nodeId);
      if (node) navigator.clipboard.writeText(JSON.stringify(node.data.config, null, 2));
      onClose();
    }},
    null, // separator
    { icon: Trash2, label: 'Delete', shortcut: 'Del', action: () => { removeNode(state.nodeId); onClose(); }, danger: true },
  ];

  const menuStyle: React.CSSProperties = {
    position: 'fixed',
    left: Math.min(state.x, window.innerWidth - 220),
    top: Math.min(state.y, window.innerHeight - 250),
    zIndex: 9999,
  };

  return (
    <div ref={menuRef} style={menuStyle} className="w-52 bg-surface-800 border border-border-secondary rounded-xl shadow-2xl shadow-black/50 overflow-hidden animate-scale-in py-1">
      {items.map((item, i) => {
        if (!item) return <div key={`sep-${i}`} className="my-1 border-t border-border-primary" />;
        const Icon = item.icon;
        const danger = 'danger' in item && item.danger;
        return (
          <button
            key={item.label}
            onClick={item.action}
            className={`w-full flex items-center gap-2.5 px-3 py-1.5 text-left text-xs transition-colors ${
              danger ? 'text-red-400 hover:bg-red-500/10' : 'text-text-secondary hover:bg-surface-700 hover:text-text-primary'
            }`}
          >
            <Icon className="w-3.5 h-3.5 shrink-0" />
            <span className="flex-1">{item.label}</span>
            {'shortcut' in item && item.shortcut && (
              <span className="text-[9px] text-text-muted">{item.shortcut}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}
