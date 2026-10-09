import React, { createContext, useContext, useState, useEffect } from 'react';
import api from '../api/client';

type Role = 'STUDENT' | 'FACULTY' | 'MANAGEMENT' | 'MAINTENANCE' | 'SAFETY';

interface User {
  id: string;
  email: string;
  role: Role;
  full_name: string;
  display_name?: string;
  student_id?: string | null;
  usn?: string | null;
  phone?: string | null;
  department_id?: string | null;
  department?: string | null;
  program?: string | null;
  semester?: number | null;
  section_id?: string | null;
  section?: string | null;
  admission_year?: number | null;
  academic_status?: string | null;
  profile?: Record<string, string> | null;
  faculty_id?: string | null;
  employee_id?: string | null;
  designation?: string | null;
}

type ApiUser = Omit<User, 'full_name'>;

interface AuthContextType {
  user: User | null;
  login: (identifier: string, password: string) => Promise<void>;
  logout: () => void;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

function getRedirectPath(role: Role): string {
  switch (role) {
    case 'MANAGEMENT': return '/management';
    case 'FACULTY': return '/faculty';
    case 'STUDENT': return '/student';
    default: return '/login';
  }
}

function mapUser(data: ApiUser): User {
  return {
    id: data.id,
    email: data.email,
    role: data.role,
    full_name: data.display_name || data.email,
    display_name: data.display_name,
    student_id: data.student_id,
    usn: data.usn,
    phone: data.phone,
    department_id: data.department_id,
    department: data.department,
    program: data.program,
    semester: data.semester,
    section_id: data.section_id,
    section: data.section,
    admission_year: data.admission_year,
    academic_status: data.academic_status,
    profile: data.profile,
    faculty_id: data.faculty_id,
    employee_id: data.employee_id,
    designation: data.designation,
  };
}

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const initAuth = async () => {
      if (!localStorage.getItem('auth_token')) {
        setUser(null);
        setLoading(false);
        return;
      }
      try {
        const r = await api.get<ApiUser>('/auth/me');
        setUser(mapUser(r.data));
      } catch {
        localStorage.removeItem('auth_token');
        setUser(null);
      } finally {
        setLoading(false);
      }
    };
    initAuth();
  }, []);

  const login = async (identifier: string, password: string) => {
    const r = await api.post('/auth/login', { identifier, password });
    localStorage.setItem('auth_token', r.data.access_token);
    const me = await api.get<ApiUser>('/auth/me');
    const userData = mapUser(me.data);
    setUser(userData);
    // Role-based redirect
    window.location.href = getRedirectPath(userData.role);
  };

  const logout = () => {
    localStorage.removeItem('auth_token');
    setUser(null);
    window.location.href = '/login';
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};
