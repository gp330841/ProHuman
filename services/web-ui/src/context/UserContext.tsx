import { createContext, type FormEvent, type PropsWithChildren, useContext, useEffect, useState } from 'react';
import { fetchIdentity, getAccessToken, setAccessToken, type WorkspaceIdentity } from '../api/client';

interface UserContextType {
  activeUser: { id: string; name: string; role: string; gradient: string };
  workspaceId: string;
  filterByUserOnly: boolean;
  setFilterByUserOnly: (value: boolean) => void;
  signOut: () => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export function UserProvider({ children }: PropsWithChildren) {
  const [identity, setIdentity] = useState<WorkspaceIdentity | null>(null);
  const [filterByUserOnly, setFilterByUserOnly] = useState(false);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(() => Boolean(getAccessToken()));
  const [error, setError] = useState('');

  useEffect(() => {
    const token = getAccessToken();
    if (!token) return;
    let active = true;
    fetchIdentity(token).then((user) => {
      if (active) setIdentity(user);
    }).catch((failure: Error) => {
      if (active) setError(failure.message);
    }).finally(() => {
      if (active) setBusy(false);
    });
    return () => { active = false; };
  }, []);

  async function signIn(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const token = input.trim();
      const user = await fetchIdentity(token);
      setAccessToken(token);
      setIdentity(user);
      setInput('');
    } catch (failure) {
      setError(failure instanceof Error ? failure.message : 'Sign-in failed');
    } finally {
      setBusy(false);
    }
  }

  if (!identity) {
    return (
      <main className="min-h-screen grid place-items-center p-6 bg-slate-50 dark:bg-slate-950">
        <form onSubmit={signIn} className="w-full max-w-sm space-y-5 rounded-2xl border border-slate-200 bg-white p-7 shadow-sm dark:border-slate-800 dark:bg-slate-900">
          <h1 className="text-2xl font-semibold text-slate-900 dark:text-white">Sign in to ProHuman</h1>
          <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">
            Workspace access token
            <input type="password" required value={input} onChange={(event) => setInput(event.target.value)}
              className="mt-2 w-full rounded-lg border border-slate-300 bg-transparent p-2 dark:border-slate-700" />
          </label>
          {error && <p role="alert" className="text-sm text-rose-600 dark:text-rose-400">{error}</p>}
          <button disabled={busy} className="w-full rounded-lg bg-sky-700 px-4 py-2 text-white disabled:opacity-60">
            {busy ? 'Signing in…' : 'Sign in'}
          </button>
        </form>
      </main>
    );
  }

  return (
    <UserContext.Provider value={{
      activeUser: {
        id: identity.user_id,
        name: identity.user_id,
        role: identity.role,
        gradient: 'from-sky-500 to-indigo-600',
      },
      workspaceId: identity.workspace_id,
      filterByUserOnly,
      setFilterByUserOnly,
      signOut: () => {
        setAccessToken('');
        setFilterByUserOnly(false);
        setIdentity(null);
      },
    }}>
      {children}
    </UserContext.Provider>
  );
}

export function useUser(): UserContextType {
  const context = useContext(UserContext);
  if (!context) throw new Error('useUser must be used within a UserProvider');
  return context;
}
