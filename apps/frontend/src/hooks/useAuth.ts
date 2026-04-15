"""Hook for authentication context and token management."""
import { useEffect, useState } from 'react';

interface User {
  user_id: string;
  username: string;
  email?: string;
}

interface AuthContext {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
}

export function useAuth(): AuthContext {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Get token from localStorage or session
    const storedToken = localStorage.getItem('auth_token') || sessionStorage.getItem('auth_token');

    if (storedToken) {
      setToken(storedToken);
      // Try to get user info from localStorage
      const storedUser = localStorage.getItem('user');
      if (storedUser) {
        try {
          setUser(JSON.parse(storedUser));
        } catch {
          // Invalid stored user data
        }
      }
    }

    setIsLoading(false);
  }, []);

  return {
    user,
    token,
    isLoading,
    isAuthenticated: !!token && !!user,
  };
}
