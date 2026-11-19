import { useEffect } from 'react';
import { X } from 'lucide-react';
import { useUser } from '../context/UserContext';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export function UserSessionModal({ isOpen, onClose }: Props) {
  const { activeUser, workspaceId, filterByUserOnly, setFilterByUserOnly, signOut } = useUser();

  useEffect(() => {
    if (!isOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', closeOnEscape);
    return () => window.removeEventListener('keydown', closeOnEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div role="dialog" aria-modal="true" aria-labelledby="workspace-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4 backdrop-blur-sm"
      onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
      <div className="w-full max-w-md space-y-5 rounded-2xl bg-white p-6 shadow-2xl dark:bg-slate-900">
        <div className="flex items-center justify-between">
          <h2 id="workspace-title" className="text-sm font-bold">Workspace account</h2>
          <button onClick={onClose} aria-label="Close" className="rounded-lg p-1"><X className="h-4 w-4" /></button>
        </div>
        <div className="text-sm">
          <p className="font-semibold">{activeUser.name} · {activeUser.role}</p>
          <p className="mt-1 break-all text-xs text-slate-500">{workspaceId}</p>
        </div>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={filterByUserOnly}
            onChange={(event) => setFilterByUserOnly(event.target.checked)} />
          Show only my recordings
        </label>
        <button onClick={signOut}
          className="rounded-lg border border-slate-300 px-3 py-2 text-sm dark:border-slate-700">Sign out</button>
      </div>
    </div>
  );
}
