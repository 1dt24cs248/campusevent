import React, { useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import api from '../../api/client';
import { AlertCircle, ArrowLeft, CheckCircle, ShieldAlert, Siren, Wrench } from 'lucide-react';

type ActionType = 'EMERGENCY' | 'SAFETY' | 'MAINTENANCE' | 'GENERAL';

interface Room {
  id: string;
  code: string;
  display_name: string;
  floor_id: string;
}

interface Block {
  id: string;
  name: string;
}

const OPTIONS: Record<ActionType, { title: string; categoryLabel: string; categories: string[]; descriptionLabel: string }> = {
  EMERGENCY: {
    title: 'Emergency Assistance',
    categoryLabel: 'What type of emergency are you reporting?',
    categories: ['Medical Emergency', 'Fire', 'Security Emergency', 'Accident', 'Threat / Violence', 'Other'],
    descriptionLabel: 'Describe what is happening and what assistance is needed',
  },
  SAFETY: {
    title: 'Safety & Harassment',
    categoryLabel: 'Choose a safety concern',
    categories: ['Harassment', 'Bullying', 'Threat', 'Unsafe Area', 'Suspicious Activity', 'Violence', 'Discrimination', 'Other Safety Concern'],
    descriptionLabel: 'Describe the concern. Share only information needed to review it.',
  },
  MAINTENANCE: {
    title: 'Report Campus Issue',
    categoryLabel: 'Issue category',
    categories: ['Classroom', 'Electrical', 'Plumbing', 'Furniture', 'Projector / Smart Board', 'Wi-Fi / Network', 'Cleaning', 'Washroom', 'Laboratory', 'Security', 'Parking', 'Water', 'Other'],
    descriptionLabel: 'Describe the problem',
  },
  GENERAL: {
    title: 'Other Campus Report',
    categoryLabel: 'Report category',
    categories: ['Other'],
    descriptionLabel: 'Describe the campus issue',
  },
};

function selectedType(query: string | null): ActionType {
  if (query === 'EMERGENCY' || query === 'SAFETY' || query === 'GENERAL') return query;
  return 'MAINTENANCE';
}

export const CampusActionForm: React.FC = () => {
  const [searchParams] = useSearchParams();
  const type = selectedType(searchParams.get('type'));
  const options = OPTIONS[type];
  const [category, setCategory] = useState('');
  const [roomId, setRoomId] = useState('');
  const [locationText, setLocationText] = useState('');
  const [description, setDescription] = useState('');
  const [anonymous, setAnonymous] = useState(false);
  const [confirmEmergency, setConfirmEmergency] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [created, setCreated] = useState<{ code: string; location: string } | null>(null);

  const { data: blocks = [], isLoading: blocksLoading } = useQuery<Block[]>({
    queryKey: ['action-form-blocks'],
    queryFn: async () => (await api.get('/blocks')).data,
  });
  const { data: rooms = [], isLoading: roomsLoading, isError: roomsError } = useQuery<Room[]>({
    queryKey: ['action-form-rooms', blocks.map(block => block.id).join(',')],
    enabled: blocks.length > 0,
    queryFn: async () => {
      const responses = await Promise.all(blocks.map(block => api.get<Room[]>(`/blocks/${encodeURIComponent(block.id)}/rooms`)));
      return responses.flatMap(response => response.data);
    },
  });
  const selectedRoom = useMemo(() => rooms.find(room => room.id === roomId), [rooms, roomId]);
  const Icon = type === 'EMERGENCY' ? Siren : type === 'SAFETY' ? ShieldAlert : Wrench;

  const submitReport = async () => {
    setSubmitting(true);
    setError('');
    try {
      const payload = {
        category,
        description: description.trim(),
        room_id: roomId || null,
        location_text: locationText.trim() || null,
        ...(type === 'SAFETY' ? { report_type: 'SAFETY', anonymous } : { report_type: type }),
      };
      const response = type === 'EMERGENCY'
        ? await api.post('/emergency', payload)
        : await api.post('/reports', payload);
      setCreated({ code: response.data.code, location: response.data.location });
      setConfirmEmergency(false);
      setDescription('');
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || requestError?.message || 'Unable to submit the report. Please try again.');
      setConfirmEmergency(false);
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    if (!category) {
      setError('Choose a report category to continue.');
      return;
    }
    if (description.trim().length < 3) {
      setError('Add a short description so campus staff can respond.');
      return;
    }
    if (type === 'EMERGENCY' && !roomId && !locationText.trim()) {
      setError('Select a campus room or enter a location for the emergency.');
      return;
    }
    if (type === 'MAINTENANCE' && !roomId) {
      setError('Select the room where the issue is located.');
      return;
    }
    if (type === 'EMERGENCY') {
      setConfirmEmergency(true);
      return;
    }
    void submitReport();
  };

  if (created) {
    return (
      <section className="card p-8 max-w-2xl">
        <div className="w-12 h-12 rounded-full bg-emerald-900/50 flex items-center justify-center mb-4">
          <CheckCircle className="text-emerald-300" size={24} />
        </div>
        <h1 className="text-xl font-bold text-white">{type === 'EMERGENCY' ? 'Emergency reported successfully.' : 'Report submitted.'}</h1>
        <p className="text-sm text-slate-300 mt-2">{created.code} · {category} · {created.location}</p>
        <p className="text-sm text-slate-400 mt-3">
          {type === 'EMERGENCY'
            ? 'Emergency report submitted to management. This application does not automatically contact emergency services.'
            : type === 'SAFETY'
              ? anonymous ? 'Your confidential report was received. Your identity is hidden in normal report views.' : 'Your confidential report was received by the authorized campus team.'
              : 'You can follow updates and status changes in My Reports.'}
        </p>
        <div className="flex flex-wrap gap-3 mt-6">
          <Link to="/reports" className="btn-primary">View My Reports</Link>
          <Link to={type === 'EMERGENCY' ? '/student' : '/'} className="btn-secondary">Return to dashboard</Link>
        </div>
      </section>
    );
  }

  return (
    <section className="max-w-2xl space-y-5">
      <Link to="/" className="text-sm text-slate-400 hover:text-white inline-flex items-center gap-2">
        <ArrowLeft size={15} /> Back to dashboard
      </Link>
      <header className={`card p-5 ${type === 'EMERGENCY' ? 'border-red-700/50 bg-red-950/20' : ''}`}>
        <div className="flex items-start gap-3">
          <div className={`stat-icon ${type === 'EMERGENCY' ? 'bg-red-900' : type === 'SAFETY' ? 'bg-amber-900' : 'bg-indigo-900'}`}>
            <Icon size={20} className={type === 'EMERGENCY' ? 'text-red-300' : type === 'SAFETY' ? 'text-amber-300' : 'text-indigo-300'} />
          </div>
          <div>
            <h1 className="text-xl font-bold text-white">{options.title}</h1>
            <p className="text-sm text-slate-400 mt-1">
              {type === 'EMERGENCY' ? 'Submit an urgent campus report for management. This does not contact external emergency services.' :
                type === 'SAFETY' ? 'This report is private and visible only to you and authorized safety management.' :
                  'Reports are saved and routed to campus management for follow-up.'}
            </p>
          </div>
        </div>
      </header>

      {type === 'SAFETY' && (
        <div className="rounded-lg border border-amber-700/40 bg-amber-900/20 p-4 text-sm text-amber-200">
          If you are in immediate danger, use <Link to="/report?type=EMERGENCY" className="font-semibold underline">Emergency / SOS</Link>.
        </div>
      )}

      <form onSubmit={handleSubmit} className="card p-5 sm:p-6 space-y-5">
        <div>
          <label className="label" htmlFor="action-category">{options.categoryLabel}</label>
          <select id="action-category" className="input-field" value={category} onChange={event => setCategory(event.target.value)} required>
            <option value="">Select a category</option>
            {options.categories.map(item => <option key={item} value={item}>{item}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="action-room">Campus room / location</label>
          <select id="action-room" className="input-field" value={roomId} onChange={event => setRoomId(event.target.value)} disabled={blocksLoading || roomsLoading || roomsError}>
            <option value="">{type === 'SAFETY' || type === 'GENERAL' ? 'Optional — no room selected' : 'Select a room'}</option>
            {rooms.map(room => <option key={room.id} value={room.id}>{room.code} — {room.display_name}</option>)}
          </select>
          {roomsError && <p role="alert" className="text-xs text-red-300 mt-1">Campus rooms could not be loaded. Try again before submitting.</p>}
          <label className="label mt-3" htmlFor="action-location-text">Additional location details (optional)</label>
          <input id="action-location-text" className="input-field" maxLength={300} value={locationText} onChange={event => setLocationText(event.target.value)} placeholder="e.g. near the second-floor corridor" />
          {selectedRoom && <p className="text-xs text-slate-500 mt-1">Selected: {selectedRoom.code} · {selectedRoom.display_name}</p>}
        </div>
        <div>
          <label className="label" htmlFor="action-description">{options.descriptionLabel}</label>
          <textarea id="action-description" className="input-field min-h-32 resize-y" value={description} onChange={event => setDescription(event.target.value)} maxLength={type === 'EMERGENCY' ? 4000 : 8000} required />
        </div>
        {type === 'SAFETY' && (
          <label className="flex items-start gap-3 p-3 rounded-lg border border-slate-700 bg-slate-800/40 cursor-pointer">
            <input type="checkbox" checked={anonymous} onChange={event => setAnonymous(event.target.checked)} className="mt-1 accent-indigo-500" />
            <span><span className="text-sm font-medium text-slate-200">Submit anonymously</span><span className="block text-xs text-slate-500 mt-1">Your account is used only to let you view private status updates. Management views you as Anonymous Reporter.</span></span>
          </label>
        )}
        {error && <p role="alert" className="rounded-lg border border-red-700/40 bg-red-900/20 p-3 text-sm text-red-300 flex items-start gap-2"><AlertCircle size={16} className="mt-0.5 flex-shrink-0" />{error}</p>}
        <button type="submit" disabled={submitting || roomsLoading} className={`w-full ${type === 'EMERGENCY' ? 'btn-danger' : 'btn-primary'} py-3`}>
          {submitting ? 'Submitting…' : type === 'EMERGENCY' ? 'Continue to emergency confirmation' : 'Submit report'}
        </button>
      </form>

      {confirmEmergency && (
        <div role="dialog" aria-modal="true" aria-labelledby="emergency-confirm-title" className="fixed inset-0 z-50 bg-black/70 p-4 flex items-center justify-center">
          <div className="card p-6 w-full max-w-md border-red-700/50">
            <h2 id="emergency-confirm-title" className="text-lg font-bold text-white">Confirm emergency report</h2>
            <p className="text-sm text-slate-300 mt-3">{category} · {selectedRoom?.code || locationText}</p>
            <p className="text-xs text-slate-400 mt-2">This sends a CRITICAL report to campus management. This application does not contact police, ambulance, or fire services.</p>
            <div className="flex gap-3 mt-6">
              <button className="btn-secondary flex-1" onClick={() => setConfirmEmergency(false)} disabled={submitting}>Cancel</button>
              <button className="btn-danger flex-1" onClick={() => void submitReport()} disabled={submitting}>{submitting ? 'Submitting…' : 'Confirm and submit'}</button>
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
