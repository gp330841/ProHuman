import React, { createContext, useContext, useState, useEffect } from 'react';

export interface UserProfile {
  id: string;
  name: string;
  email: string;
  role: string;
  deviceId: string;
  gradient: string;
}

const DEFAULT_USERS: UserProfile[] = [
  {
    id: 'user_yogeshwar',
    name: 'Yogeshwar Patel',
    email: 'yogeshwar@prohuman.ai',
    role: 'Owner & Tech Lead',
    deviceId: 'neo1-badge-01',
    gradient: 'from-sky-500 to-indigo-600',
  },
  {
    id: 'user_alex',
    name: 'Alex Sharma',
    email: 'alex@prohuman.ai',
    role: 'Product Manager',
    deviceId: 'prohuman-desk-02',
    gradient: 'from-emerald-500 to-teal-600',
  },
  {
    id: 'user_priya',
    name: 'Priya Verma',
    email: 'priya@prohuman.ai',
    role: 'AI Architect',
    deviceId: 'mobile-companion-03',
    gradient: 'from-violet-500 to-purple-600',
  },
  {
    id: 'user_guest',
    name: 'Guest User',
    email: 'guest@prohuman.ai',
    role: 'Visitor',
    deviceId: 'browser-mic-gadget',
    gradient: 'from-slate-600 to-slate-800',
  },
];

interface UserContextType {
  activeUser: UserProfile;
  users: UserProfile[];
  filterByUserOnly: boolean;
  setFilterByUserOnly: (val: boolean) => void;
  switchUser: (user: UserProfile) => void;
  addUserProfile: (profile: Omit<UserProfile, 'id' | 'gradient'>) => void;
}

const UserContext = createContext<UserContextType | undefined>(undefined);

export const UserProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [users, setUsers] = useState<UserProfile[]>(() => {
    try {
      const saved = localStorage.getItem('prohuman_user_profiles');
      return saved ? JSON.parse(saved) : DEFAULT_USERS;
    } catch {
      return DEFAULT_USERS;
    }
  });

  const [activeUser, setActiveUser] = useState<UserProfile>(() => {
    try {
      const savedId = localStorage.getItem('prohuman_active_user_id');
      const found = users.find((u) => u.id === savedId);
      return found || users[0] || DEFAULT_USERS[0];
    } catch {
      return DEFAULT_USERS[0];
    }
  });

  const [filterByUserOnly, setFilterByUserOnly] = useState<boolean>(() => {
    return localStorage.getItem('prohuman_filter_user_only') === 'true';
  });

  useEffect(() => {
    localStorage.setItem('prohuman_user_profiles', JSON.stringify(users));
  }, [users]);

  useEffect(() => {
    localStorage.setItem('prohuman_active_user_id', activeUser.id);
  }, [activeUser]);

  useEffect(() => {
    localStorage.setItem('prohuman_filter_user_only', String(filterByUserOnly));
  }, [filterByUserOnly]);

  const switchUser = (user: UserProfile) => {
    setActiveUser(user);
  };

  const addUserProfile = (profile: Omit<UserProfile, 'id' | 'gradient'>) => {
    const id = `user_${Date.now()}`;
    const gradients = [
      'from-rose-500 to-pink-600',
      'from-amber-500 to-orange-600',
      'from-cyan-500 to-blue-600',
      'from-fuchsia-500 to-purple-600',
    ];
    const gradient = gradients[users.length % gradients.length];
    const newUser: UserProfile = { ...profile, id, gradient };
    setUsers((prev) => [...prev, newUser]);
    setActiveUser(newUser);
  };

  return (
    <UserContext.Provider
      value={{
        activeUser,
        users,
        filterByUserOnly,
        setFilterByUserOnly,
        switchUser,
        addUserProfile,
      }}
    >
      {children}
    </UserContext.Provider>
  );
};

export const useUser = (): UserContextType => {
  const context = useContext(UserContext);
  if (!context) {
    throw new Error('useUser must be used within a UserProvider');
  }
  return context;
};
