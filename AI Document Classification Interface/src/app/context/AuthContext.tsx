import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { getUsers, type User } from '../services/api';

interface AuthContextType {
  user: User | null;
  users: User[];
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (userId: string) => Promise<boolean>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Load users and check for saved session
    const initAuth = async () => {
      try {
        const usersData = await getUsers();
        setUsers(usersData);

        // Check for saved session
        const savedUserId = localStorage.getItem('currentUserId');
        if (savedUserId) {
          const savedUser = usersData.find(u => u.user_id === savedUserId);
          if (savedUser) {
            setUser(savedUser);
          }
        }
      } catch (error) {
        console.error('Failed to load users:', error);
      } finally {
        setIsLoading(false);
      }
    };

    initAuth();
  }, []);

  const login = async (userId: string): Promise<boolean> => {
    const selectedUser = users.find(u => u.user_id === userId);
    if (selectedUser) {
      setUser(selectedUser);
      localStorage.setItem('currentUserId', userId);
      return true;
    }
    return false;
  };

  const logout = () => {
    setUser(null);
    localStorage.removeItem('currentUserId');
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        users,
        isAuthenticated: !!user,
        isLoading,
        login,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
