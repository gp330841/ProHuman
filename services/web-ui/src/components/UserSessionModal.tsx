import React, { useEffect, useState } from 'react';
import { Users, Plus, Check, Shield, Smartphone, X } from 'lucide-react';
import { useUser } from '../context/UserContext';

interface Props {
  isOpen: boolean;
  onClose: () => void;
}

export const UserSessionModal: React.FC<Props> = ({ isOpen, onClose }) => {
  const { activeUser, users, switchUser, addUserProfile, filterByUserOnly, setFilterByUserOnly } = useUser();
  const [showAddForm, setShowAddForm] = useState(false);
  const [newName, setNewName] = useState('');
  const [newEmail, setNewEmail] = useState('');
  const [newRole, setNewRole] = useState('Team Member');
  const [newDeviceId, setNewDeviceId] = useState('neo1-badge-01');

  useEffect(() => {
    if (!isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  const handleAddUser = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newName.trim()) return;
    addUserProfile({
      name: newName.trim(),
      email: newEmail.trim() || `${newName.toLowerCase().replace(/\s+/g, '')}@prohuman.ai`,
      role: newRole,
      deviceId: newDeviceId || 'neo1-badge-01',
    });
    setNewName('');
    setNewEmail('');
    setShowAddForm(false);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="user-session-modal-title"
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl w-full max-w-md overflow-hidden shadow-2xl animate-in fade-in zoom-in-95 duration-200">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-sky-50 dark:bg-sky-500/10 text-sky-600 dark:text-sky-400 flex items-center justify-center border border-sky-200 dark:border-sky-500/20">
              <Users className="w-4 h-4" />
            </div>
            <div>
              <h3 id="user-session-modal-title" className="text-sm font-bold text-slate-900 dark:text-white">User Session Management</h3>
              <p className="text-[11px] text-slate-500 dark:text-slate-400">Switch user profile or manage gadget sessions</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-600 dark:hover:text-white p-1 rounded-lg transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-6 space-y-5 max-h-[75vh] overflow-y-auto">
          {/* Active User Highlight Card */}
          <div className="p-4 rounded-xl bg-slate-50 dark:bg-slate-950 border border-sky-200 dark:border-sky-500/30 relative overflow-hidden">
            <div className="flex items-center gap-3">
              <div
                className={`w-11 h-11 rounded-xl bg-gradient-to-tr ${activeUser.gradient} flex items-center justify-center text-white font-bold text-base shadow-sm`}
              >
                {activeUser.name.charAt(0)}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-900 dark:text-white truncate">{activeUser.name}</span>
                  <span className="text-[10px] bg-sky-100 dark:bg-sky-500/20 text-sky-700 dark:text-sky-300 px-2 py-0.5 rounded-full border border-sky-200 dark:border-sky-500/30 font-medium">
                    Active
                  </span>
                </div>
                <p className="text-xs text-slate-500 dark:text-slate-400">{activeUser.email}</p>
                <div className="flex items-center gap-2 mt-1 text-[11px] text-slate-500 font-mono">
                  <span className="flex items-center gap-1">
                    <Shield className="w-3 h-3 text-sky-500 dark:text-sky-400" /> {activeUser.role}
                  </span>
                  <span>•</span>
                  <span className="flex items-center gap-1">
                    <Smartphone className="w-3 h-3 text-slate-400" /> {activeUser.deviceId}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* User Filtering Toggle */}
          <div className="flex items-center justify-between p-3 rounded-xl bg-slate-50 dark:bg-slate-950/70 border border-slate-200 dark:border-slate-800 text-xs">
            <div>
              <span className="font-semibold text-slate-800 dark:text-slate-200">Filter Sessions by Active User</span>
              <p className="text-[11px] text-slate-500">Only show meetings & recordings tagged to {activeUser.name}</p>
            </div>
            <button
              onClick={() => setFilterByUserOnly(!filterByUserOnly)}
              className={`w-11 h-6 rounded-full transition p-1 relative flex items-center cursor-pointer ${
                filterByUserOnly ? 'bg-sky-600' : 'bg-slate-300 dark:bg-slate-800'
              }`}
            >
              <div
                className={`w-4 h-4 rounded-full bg-white transition transform ${
                  filterByUserOnly ? 'translate-x-5' : 'translate-x-0'
                }`}
              />
            </button>
          </div>

          {/* User Profiles List */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs font-semibold text-slate-600 dark:text-slate-300 uppercase tracking-wider">Available Profiles</span>
              <button
                onClick={() => setShowAddForm(!showAddForm)}
                className="text-xs text-sky-600 dark:text-sky-400 hover:text-sky-500 dark:hover:text-sky-300 font-medium flex items-center gap-1 transition cursor-pointer"
              >
                <Plus className="w-3.5 h-3.5" /> {showAddForm ? 'Cancel' : 'Add Profile'}
              </button>
            </div>

            {showAddForm && (
              <form onSubmit={handleAddUser} className="p-3 mb-3 bg-slate-50 dark:bg-slate-950 rounded-xl border border-slate-200 dark:border-slate-800 space-y-2.5">
                <div>
                  <label className="text-[11px] text-slate-500 dark:text-slate-400 block mb-1">Full Name</label>
                  <input
                    type="text"
                    required
                    value={newName}
                    onChange={(e) => setNewName(e.target.value)}
                    placeholder="e.g. Ramesh Kumar"
                    className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500"
                  />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-[11px] text-slate-500 dark:text-slate-400 block mb-1">Role</label>
                    <input
                      type="text"
                      value={newRole}
                      onChange={(e) => setNewRole(e.target.value)}
                      placeholder="e.g. Lead Engineer"
                      className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500"
                    />
                  </div>
                  <div>
                    <label className="text-[11px] text-slate-500 dark:text-slate-400 block mb-1">Gadget ID</label>
                    <input
                      type="text"
                      value={newDeviceId}
                      onChange={(e) => setNewDeviceId(e.target.value)}
                      placeholder="e.g. neo1-badge-02"
                      className="w-full bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-lg px-3 py-1.5 text-xs text-slate-900 dark:text-white placeholder-slate-400 dark:placeholder-slate-500 focus:outline-none focus:border-sky-500 font-mono"
                    />
                  </div>
                </div>
                <button
                  type="submit"
                  className="w-full py-1.5 bg-sky-600 hover:bg-sky-500 text-white rounded-lg text-xs font-semibold transition cursor-pointer"
                >
                  Create & Switch Profile
                </button>
              </form>
            )}

            <div className="space-y-1.5">
              {users.map((u) => {
                const isSelected = u.id === activeUser.id;
                return (
                  <button
                    key={u.id}
                    onClick={() => {
                      switchUser(u);
                      onClose();
                    }}
                    className={`w-full p-2.5 rounded-xl border text-left flex items-center justify-between gap-3 transition cursor-pointer ${
                      isSelected
                        ? 'bg-sky-50 dark:bg-sky-500/10 border-sky-300 dark:border-sky-500/40 text-slate-900 dark:text-white'
                        : 'bg-white dark:bg-slate-950/40 border-slate-200 dark:border-slate-800/80 text-slate-700 dark:text-slate-300 hover:border-slate-300 dark:hover:border-slate-700'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0">
                      <div
                        className={`w-8 h-8 rounded-lg bg-gradient-to-tr ${u.gradient} flex items-center justify-center text-white font-bold text-xs shrink-0`}
                      >
                        {u.name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-medium text-slate-900 dark:text-white truncate">{u.name}</p>
                        <p className="text-[10px] text-slate-500 truncate">{u.role} • {u.deviceId}</p>
                      </div>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-sky-600 dark:text-sky-400 shrink-0" />}
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-200 dark:border-slate-800 bg-slate-50 dark:bg-slate-950/80 flex items-center justify-between text-xs text-slate-500">
          <span>Active Session ID: <b className="font-mono text-slate-700 dark:text-slate-400">{activeUser.id}</b></span>
          <button
            onClick={onClose}
            className="px-3.5 py-1 bg-slate-200 dark:bg-slate-800 hover:bg-slate-300 dark:hover:bg-slate-700 text-slate-800 dark:text-slate-200 rounded-lg transition cursor-pointer"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
};
