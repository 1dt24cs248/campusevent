import React from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import api from '../../api/client';
import { AlertCircle, Bell, Check, Clock } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

interface Notification {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  created_at?: string | null;
  read: boolean;
}

export const NotificationsPage: React.FC = () => {
  const queryClient = useQueryClient();
  const { user } = useAuth();
  const { data: notifications = [], isLoading, isError } = useQuery<Notification[]>({
    queryKey: ['notifications', user?.id],
    queryFn: async () => (await api.get('/notifications')).data,
  });
  const markRead = useMutation({
    mutationFn: async (id: string) => api.post(`/notifications/${encodeURIComponent(id)}/read`),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['notifications'] }),
  });

  return (
    <section className="max-w-4xl space-y-5">
      <header>
        <div className="section-header"><Bell size={20} className="text-amber-400" />Notifications</div>
        <p className="text-sm text-slate-400 mt-2">Campus updates and published room changes.</p>
      </header>
      {isLoading ? <div className="card p-6 text-sm text-slate-400">Loading notifications…</div>
        : isError ? <div role="alert" className="card p-6 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />Notifications could not be loaded. Please try again.</div>
          : notifications.length === 0 ? (
            <div className="card p-10 text-center">
              <Bell size={24} className="text-slate-600 mx-auto mb-3" />
              <p className="text-sm text-slate-300">You’re all caught up.</p>
              <p className="text-xs text-slate-500 mt-1">New campus notifications will appear here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {notifications.map(notification => (
                <article key={notification.id} className={`card p-4 flex items-start gap-3 ${notification.read ? 'opacity-75' : 'border-indigo-700/50'}`}>
                  <div className={`stat-icon ${notification.read ? 'bg-slate-700' : 'bg-indigo-800'}`}>
                    {notification.read ? <Check size={17} className="text-slate-300" /> : <Bell size={17} className="text-indigo-200" />}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <h2 className="font-medium text-white">{notification.title}</h2>
                      <span className="badge-blue">{notification.type}</span>
                      {!notification.read && <span className="badge-amber">Unread</span>}
                    </div>
                    {notification.body && <p className="text-sm text-slate-400 mt-1">{notification.body}</p>}
                    {notification.created_at && <p className="text-xs text-slate-600 mt-2 flex items-center gap-1"><Clock size={12} />{new Date(notification.created_at).toLocaleString()}</p>}
                  </div>
                  {!notification.read && (
                    <button
                      onClick={() => markRead.mutate(notification.id)}
                      disabled={markRead.isPending}
                      className="btn-secondary text-xs flex-shrink-0"
                    >
                      Mark read
                    </button>
                  )}
                </article>
              ))}
            </div>
          )}
      {markRead.isError && <p role="alert" className="text-sm text-red-300">Could not mark the notification as read.</p>}
    </section>
  );
};
