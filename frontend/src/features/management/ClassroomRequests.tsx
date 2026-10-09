import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Building2, Check, X } from 'lucide-react';
import api from '../../api/client';
import { formatTime } from '../faculty/facultyTypes';
import type { ClassroomRequest } from '../faculty/facultyTypes';

interface RequestRoom {
  id: string;
  code: string;
  display_name: string;
  floor_id: string;
  capacity: number | null;
  resource_type: string;
  status: string;
  allocatable_for_classes: boolean;
}

export const ClassroomRequests: React.FC = () => {
  const queryClient = useQueryClient();
  const [selectedRooms, setSelectedRooms] = useState<Record<string, string>>({});
  const [rejectionReasons, setRejectionReasons] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const { data: requests = [], isLoading, isError } = useQuery<ClassroomRequest[]>({
    queryKey: ['management-classroom-requests'],
    queryFn: async () => (await api.get('/management/classroom-requests')).data,
  });
  const { data: rooms = [] } = useQuery<RequestRoom[]>({
    queryKey: ['management-classroom-request-rooms'],
    queryFn: async () => (await api.get('/management/classroom-requests/rooms')).data,
  });
  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ['management-classroom-requests'] });
    queryClient.invalidateQueries({ queryKey: ['faculty-classroom-requests'] });
    queryClient.invalidateQueries({ queryKey: ['faculty-extra-classes'] });
    queryClient.invalidateQueries({ queryKey: ['notifications'] });
  };
  const approve = useMutation({
    mutationFn: async ({ requestId, roomId }: { requestId: string; roomId: string }) => (
      await api.post(`/management/classroom-requests/${requestId}/approve`, { room_id: roomId })
    ).data,
    onSuccess: () => { setError(''); refresh(); },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'The request could not be approved.'),
  });
  const reject = useMutation({
    mutationFn: async ({ requestId, reason }: { requestId: string; reason: string }) => (
      await api.post(`/management/classroom-requests/${requestId}/reject`, { reason })
    ).data,
    onSuccess: () => { setError(''); refresh(); },
    onError: (mutationError: any) => setError(mutationError.response?.data?.detail || 'The request could not be rejected.'),
  });

  return (
    <section className="space-y-5">
      <header>
        <h1 className="section-header"><Building2 size={20} className="text-indigo-300" />Classroom / Resource Requests</h1>
        <p className="text-sm text-slate-400 mt-2">Review faculty requests. Approval checks classroom capacity, status, availability, timetable conflicts, and class requirements.</p>
      </header>
      {error && <p role="alert" className="card p-4 text-sm text-red-300 flex gap-2"><AlertCircle size={16} />{error}</p>}
      {isLoading ? <div className="card p-5 text-sm text-slate-400">Loading classroom requests…</div>
        : isError ? <div role="alert" className="card p-5 text-sm text-red-300">Classroom requests could not be loaded.</div>
          : requests.length === 0 ? <div className="card p-6 text-sm text-slate-400">No classroom requests have been submitted.</div>
            : <div className="space-y-4">{requests.map(request => {
              const eligibleRooms = rooms.filter(room => (
                room.status === 'ACTIVE'
                && room.allocatable_for_classes
                && room.capacity !== null
                && room.capacity >= request.expected_strength
                && (request.preferred_floor_id ? room.floor_id === request.preferred_floor_id : true)
              ));
              const preferredRoomIsEligible = eligibleRooms.some(room => room.id === request.preferred_room_id);
              const chosenRoom = selectedRooms[request.id]
                || (preferredRoomIsEligible ? request.preferred_room_id : '')
                || eligibleRooms[0]?.id
                || '';
              return (
                <article key={request.id} className="card p-5">
                  <div className="flex flex-col lg:flex-row lg:items-start lg:justify-between gap-4">
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h2 className="font-semibold text-white">{request.subject_code} · {request.section_code}</h2>
                        <span className={request.status === 'PENDING' ? 'badge-amber' : request.status === 'APPROVED' ? 'badge-green' : request.status === 'REJECTED' ? 'badge-red' : 'badge-blue'}>{request.status}</span>
                      </div>
                      <p className="text-sm text-slate-300 mt-2">{request.faculty_name} · {request.employee_id || 'Employee ID unavailable'}</p>
                      <p className="text-sm text-slate-300 mt-1">{request.requested_date} · {formatTime(request.start_time)} – {formatTime(request.end_time)} · Strength {request.expected_strength}</p>
                      <p className="text-sm text-slate-400 mt-3">{request.reason}</p>
                      {(request.preferred_room_code || request.preferred_floor_id) && <p className="text-xs text-slate-500 mt-2">Preference: {request.preferred_room_code || 'Room not specified'}{request.preferred_floor_id ? ' · requested floor' : ''}</p>}
                      {request.status === 'APPROVED' && <p className="text-sm text-emerald-200 mt-3">Approved room: {request.approved_room_code || 'Not recorded'}</p>}
                      {request.status === 'REJECTED' && <p className="text-sm text-red-300 mt-3">Reason: {request.decision_reason}</p>}
                    </div>
                    {request.status === 'PENDING' && (
                      <div className="w-full lg:w-80 space-y-3">
                        <label className="block text-xs text-slate-400">Confirm classroom
                          <select className="input-field mt-2" value={chosenRoom} onChange={event => setSelectedRooms(current => ({ ...current, [request.id]: event.target.value }))}>
                            <option value="">Select a room</option>
                            {rooms.map(room => <option key={room.id} value={room.id} disabled={room.status !== 'ACTIVE' || !room.allocatable_for_classes || room.capacity === null || room.capacity < request.expected_strength}>{room.code} · capacity {room.capacity ?? 'unknown'} · {room.status}</option>)}
                          </select>
                        </label>
                        <button type="button" className="btn-primary w-full inline-flex justify-center items-center gap-2" disabled={!chosenRoom || approve.isPending} onClick={() => approve.mutate({ requestId: request.id, roomId: chosenRoom })}><Check size={15} />Approve with room</button>
                        <label className="block text-xs text-slate-400">Rejection reason
                          <input className="input-field mt-2" minLength={3} maxLength={1000} value={rejectionReasons[request.id] || ''} onChange={event => setRejectionReasons(current => ({ ...current, [request.id]: event.target.value }))} placeholder="Explain the decision" />
                        </label>
                        <button type="button" className="btn-secondary w-full inline-flex justify-center items-center gap-2 text-red-300" disabled={(rejectionReasons[request.id] || '').trim().length < 3 || reject.isPending} onClick={() => reject.mutate({ requestId: request.id, reason: rejectionReasons[request.id].trim() })}><X size={15} />Reject request</button>
                      </div>
                    )}
                  </div>
                </article>
              );
            })}</div>}
    </section>
  );
};
