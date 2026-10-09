import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { Shield, GraduationCap, BookOpen, Building2, AlertCircle, Eye, EyeOff } from 'lucide-react';

const DEMO_ACCOUNTS = [
  {
    role: 'Management',
    email: 'manager@demo.local',
    password: 'Demo@1234',
    icon: Shield,
    description: 'What-If Simulator & Campus Control',
    accent: 'indigo',
    iconBg: 'bg-indigo-900/60',
    iconColor: 'text-indigo-400',
    border: 'border-indigo-500/40',
    hoverBorder: 'hover:border-indigo-400',
  },
  {
    role: 'Faculty',
    email: 'faculty@demo.local',
    password: 'Demo@1234',
    icon: BookOpen,
    description: 'Teaching Schedule & Room Updates',
    accent: 'cyan',
    iconBg: 'bg-cyan-900/60',
    iconColor: 'text-cyan-400',
    border: 'border-cyan-500/40',
    hoverBorder: 'hover:border-cyan-400',
  },
  {
    role: 'Student',
    email: 'student@demo.local',
    password: 'Demo@1234',
    icon: GraduationCap,
    description: 'My Schedule, Rooms & Notifications',
    accent: 'emerald',
    iconBg: 'bg-emerald-900/60',
    iconColor: 'text-emerald-400',
    border: 'border-emerald-500/40',
    hoverBorder: 'hover:border-emerald-400',
  },
];

export const LoginPage: React.FC = () => {
  const { login } = useAuth();
  const [identifier, setIdentifier] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);
    try {
      await login(identifier, password);
    } catch {
      setError('Invalid credentials. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  const fillDemo = (acc: typeof DEMO_ACCOUNTS[0]) => {
    setIdentifier(acc.email);
    setPassword(acc.password);
    setError('');
  };

  return (
    <div className="min-h-screen bg-slate-950 flex">
      {/* Left panel - Branding */}
      <div className="hidden lg:flex lg:w-1/2 flex-col justify-between p-12 bg-gradient-to-br from-slate-900 via-slate-950 to-indigo-950 relative overflow-hidden">
        {/* Background grid pattern */}
        <div className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: 'linear-gradient(rgba(99,102,241,0.3) 1px, transparent 1px), linear-gradient(90deg, rgba(99,102,241,0.3) 1px, transparent 1px)',
            backgroundSize: '40px 40px'
          }}
        />
        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-16">
            <div className="w-10 h-10 rounded-xl bg-indigo-600 flex items-center justify-center">
              <Building2 className="text-white" size={22} />
            </div>
            <span className="text-xl font-bold text-white">Campus Intelligence</span>
          </div>
          <div>
            <h1 className="text-5xl font-bold text-white leading-tight mb-4">
              One Campus.<br />
              <span className="bg-gradient-to-r from-indigo-400 to-cyan-400 bg-clip-text text-transparent">
                Three Users.
              </span><br />
              Smarter Decisions.
            </h1>
            <p className="text-slate-400 text-lg mt-6 leading-relaxed">
              AI-powered What-If Decision Simulator that lets management ask <em>"what happens if..."</em> before making any campus changes.
            </p>
          </div>
        </div>
        <div className="relative z-10 space-y-4">
          <div className="flex items-center gap-3 text-slate-400 text-sm">
            <div className="w-2 h-2 rounded-full bg-indigo-500" />
            <span>OR-Tools CP-SAT Optimization Engine</span>
          </div>
          <div className="flex items-center gap-3 text-slate-400 text-sm">
            <div className="w-2 h-2 rounded-full bg-cyan-500" />
            <span>Real-time Impact Analysis & Alternatives</span>
          </div>
          <div className="flex items-center gap-3 text-slate-400 text-sm">
            <div className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Role-aware AI Assistant & Campus Navigator</span>
          </div>
        </div>
      </div>

      {/* Right panel - Login */}
      <div className="flex-1 flex items-center justify-center p-6 lg:p-12">
        <div className="w-full max-w-md">
          {/* Mobile logo */}
          <div className="lg:hidden flex items-center gap-3 mb-8">
            <div className="w-9 h-9 rounded-xl bg-indigo-600 flex items-center justify-center">
              <Building2 className="text-white" size={18} />
            </div>
            <span className="text-lg font-bold text-white">Campus Intelligence</span>
          </div>

          <h2 className="text-2xl font-bold text-white mb-2">Sign in</h2>
          <p className="text-slate-400 text-sm mb-8">Access your campus management portal</p>

          {/* Demo Role Cards */}
          <div className="mb-6">
            <p className="text-xs font-medium text-slate-500 uppercase tracking-wider mb-3">Quick Demo Access</p>
            <div className="grid grid-cols-3 gap-2">
              {DEMO_ACCOUNTS.map((acc) => {
                const Icon = acc.icon;
                return (
                  <button
                    key={acc.role}
                    onClick={() => fillDemo(acc)}
                    className={`p-3 rounded-xl border ${acc.border} ${acc.hoverBorder} bg-slate-900/80 transition-all duration-200 group text-left`}
                  >
                    <div className={`w-8 h-8 rounded-lg ${acc.iconBg} flex items-center justify-center mb-2`}>
                      <Icon size={16} className={acc.iconColor} />
                    </div>
                    <p className="text-xs font-semibold text-slate-200">{acc.role}</p>
                    <p className="text-[10px] text-slate-500 mt-0.5 leading-tight">{acc.description}</p>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="label">USN, Employee ID, or College Email</label>
              <input
                type="text"
                className="input-field"
                value={identifier}
                onChange={e => { setIdentifier(e.target.value); setError(''); }}
                placeholder="USN, employee ID, or you@campus.edu"
                required
                autoComplete="username"
              />
            </div>
            <div>
              <label className="label">Password</label>
              <div className="relative">
                <input
                  type={showPassword ? 'text' : 'password'}
                  className="input-field pr-10"
                  value={password}
                  onChange={e => { setPassword(e.target.value); setError(''); }}
                  placeholder="••••••••"
                  required
                  autoComplete="current-password"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors"
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            {error && (
              <div className="flex items-center gap-2 p-3 bg-red-900/30 border border-red-700/50 rounded-lg text-red-300 text-sm">
                <AlertCircle size={15} className="flex-shrink-0" />
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={loading}
              className="w-full btn-primary py-3 text-sm flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Authenticating...
                </>
              ) : 'Sign In'}
            </button>
          </form>

          <p className="text-xs text-center text-slate-600 mt-8">
            Block A Pilot · Campus Intelligence &amp; Action Platform v0.2
          </p>
        </div>
      </div>
    </div>
  );
};
