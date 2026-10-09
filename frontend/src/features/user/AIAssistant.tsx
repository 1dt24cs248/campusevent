import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import api from '../../api/client';
import { useAuth } from '../../context/AuthContext';
import { AlertCircle, Bot, MapPin, Send, UserRound } from 'lucide-react';

interface ChatMessage {
  role: 'user' | 'ai';
  text: string;
}

interface Room {
  id: string;
  block_id: string;
  floor_id: string;
  code: string;
  display_name: string;
  capacity: number | null;
  aliases: string[];
}

interface TimetableEntry {
  id: string;
  subject_name?: string | null;
  section_code?: string | null;
  faculty_name?: string | null;
  weekday: number;
  start_slot: string;
  base_room_code?: string | null;
  effective_room_code?: string | null;
  room_changed: boolean;
  change_reason?: string | null;
}

interface Scenario {
  id: string;
  name: string;
  status: string;
  changes: Array<{ type?: string; payload?: { room_ids?: string[] } }>;
}

const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday'];
const PERIODS: Record<string, [number, number]> = {
  P1: [9 * 60 + 30, 10 * 60 + 25],
  P2: [10 * 60 + 25, 11 * 60 + 20],
  P3: [11 * 60 + 35, 12 * 60 + 30],
  P4: [12 * 60 + 30, 13 * 60 + 25],
  P5: [14 * 60 + 15, 15 * 60 + 10],
  P6: [15 * 60 + 10, 16 * 60 + 5],
  P7: [16 * 60 + 5, 17 * 60],
};
const normalize = (value: string) => value.toLowerCase().replace(/^room[_\s-]*/, '').replace(/[^a-z0-9]/g, '');

function formatSlot(slot: string): string {
  const match = slot.match(/^(\d{1,2}):(\d{2})$/);
  if (match) return `${String(Number(match[1])).padStart(2, '0')}:${match[2]}`;
  const period = PERIODS[slot];
  if (!period) return slot;
  const formatTime = (minutes: number) => `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
  return `${formatTime(period[0])}–${formatTime(period[1])}`;
}

function localDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

function roomCodeFrom(text: string): string | null {
  return text.match(/\b(?:room[_\s-]*|classroom\s+)?([a-z]\s*-?\s*\d{3,4})\b/i)?.[1]?.replace(/\s+/g, '') || null;
}

function findRoomIntent(text: string): boolean {
  return /\b(where|location|find|navigate|directions?)\b/i.test(text) && roomCodeFrom(text) !== null;
}

function formatRoomCode(roomId: string | null | undefined): string {
  return roomId ? roomId.replace(/^room_/, '') : 'Room not assigned';
}

async function lookupRoom(input: string): Promise<Room> {
  const query = input.replace(/^room[_\s-]*/i, '').replace(/[^a-z0-9]/gi, '');
  const response = await api.get<Room[]>('/rooms/search', { params: { q: query } });
  const target = normalize(input);
  const room = response.data.find(candidate =>
    normalize(candidate.code) === target
    || normalize(candidate.display_name) === target
    || normalize(candidate.id) === target
    || candidate.aliases?.some(alias => normalize(alias) === target)
  );
  if (!room) throw new Error(`I couldn’t find a campus room matching “${input}”. Check the room code and try again.`);
  return room;
}

async function answerQuestion(question: string, role: string): Promise<string> {
  const text = question.toLowerCase();
  const targetCode = roomCodeFrom(question);

  const reportCode = question.match(/\b(?:ISS|SR|ER)-[A-Z0-9]{6,12}\b/i)?.[0]?.toUpperCase();
  if (reportCode) {
    const response = await api.get(`/reports/${encodeURIComponent(reportCode)}`);
    const report = response.data;
    return `${report.code} — ${report.category}. Status: ${report.status.replace(/_/g, ' ')}. Location: ${report.location}. Priority/severity: ${report.severity || report.priority}.${report.assigned_to ? ` Assigned to ${report.assigned_to}.` : ''}`;
  }

  if (/\b(what reports|my reports|reports have i submitted|reports did i submit)\b/i.test(text)) {
    const response = await api.get<Array<{ code: string; category: string; status: string; location: string }>>('/reports', { params: { mine: true } });
    const reports = response.data;
    if (reports.length === 0) return 'You have not submitted any campus reports yet.';
    return `Your latest reports: ${reports.slice(0, 8).map(report => `${report.code} (${report.category}) — ${report.status.replace(/_/g, ' ')}, ${report.location}`).join('; ')}.`;
  }

  if (/\bhow (do|can) i report\b|\bhow to report\b/i.test(text) && /\b(harass|safety|bully|threat|projector|maintenance|issue|campus)\b/i.test(text)) {
    if (/\b(harass|safety|bully|threat)\b/i.test(text)) {
      return 'Use the confidential Safety & Harassment form, choose the closest category, add any useful location details, and submit. Reports are reviewed by authorized campus staff; the assistant does not assess whether a report is true. If you are in immediate danger, use Emergency / SOS. Open Safety & Harassment.';
    }
    return 'Open Report Campus Issue, choose the matching category (for example Projector / Smart Board), select the real room, describe the problem, and submit. You can follow progress in My Reports. Open Report Campus Issue.';
  }

  if (/\b(canteen|cafeteria|food location|main canteen)\b/i.test(text) && /\b(where|location|menu|food|find|navigate)\b/i.test(text)) {
    const locationsResponse = await api.get<Array<{ name: string; room_code: string; display_name: string; opening_hours?: string | null }>>('/food/locations');
    const matched = locationsResponse.data.find(location => text.includes(location.name.toLowerCase()));
    if (!matched) {
      return locationsResponse.data.length
        ? `Published campus food locations: ${locationsResponse.data.map(location => `${location.name} (${location.room_code})`).join('; ')}. Open Campus Food for today's published menu.`
        : 'No campus food locations or menu have been published in the campus data yet. Open Campus Food to see updates when management publishes verified information.';
    }
    const route = await api.get('/nav/route', { params: { target: matched.room_code } });
    return `${matched.name} is at ${matched.room_code} — ${matched.display_name}.${matched.opening_hours ? ` Opening hours: ${matched.opening_hours}.` : ''} ${String(route.data.route).replace(/\broom_([a-zA-Z0-9-]+)\b/g, '$1')} Open Campus Food.`;
  }

  if (/\bwhat happens if\b|\bif\b.*\bunavailable\b|\bscenario\b|\bwhat.if\b/i.test(text) && targetCode) {
    const room = await lookupRoom(targetCode);
    const scenariosResponse = await api.get<Scenario[]>('/scenarios');
    const scenario = scenariosResponse.data.find(item =>
      item.changes?.some(change =>
        change.payload?.room_ids?.some(id => normalize(id) === normalize(room.id) || normalize(id) === normalize(room.code))
      ) && ['SIMULATED', 'REVIEWED', 'APPROVED', 'PUBLISHED'].includes(item.status)
    );
    if (scenario) {
      const resultResponse = await api.get(`/scenarios/${encodeURIComponent(scenario.id)}/result`);
      const result = resultResponse.data;
      const option = result.options?.[0];
      return `${scenario.name} has a saved ${scenario.status.toLowerCase()} simulation for ${room.code}. It affected ${result.affected_count} class(es); the selected option is ${option?.status || 'not reported'} with ${Object.keys(option?.assignments || {}).length} assignment(s) and ${(option?.unresolved || []).length} unresolved.`;
    }

    const scheduleResponse = await api.get<TimetableEntry[]>('/timetable/me', {
      params: { date: localDateString(new Date()) },
    });
    const affected = scheduleResponse.data.filter(entry =>
      normalize(entry.effective_room_code || entry.base_room_code || '') === normalize(room.code)
    );
    if (affected.length === 0) return `${room.code} is a real campus room. I found no classes assigned to it in your timetable. No saved campus-wide simulation is available yet${role === 'MANAGEMENT' ? '; run the What-If Simulator to assess the impact.' : '; management can run the What-If Simulator to assess the impact.'}`;
    return `Your timetable has ${affected.length} class(es) currently assigned to ${room.code}: ${affected.map(entry => `${entry.subject_name || 'Class'}${entry.section_code ? ` (${entry.section_code})` : ''}, ${WEEKDAYS[entry.weekday] || 'scheduled day'} at ${formatSlot(entry.start_slot)}`).join('; ')}. This is your schedule only, not a campus-wide simulation.`;
  }

  if (/\b(classroom|room)\b.*\b(change|changed|move|moved|override)\b|\b(did|has|was)\b.*\b(change|changed|move|moved)\b/i.test(text)) {
    const today = localDateString(new Date());
    const [scheduleResponse, notificationsResponse] = await Promise.all([
      api.get<TimetableEntry[]>('/timetable/me', { params: { date: today } }),
      api.get<{ type: string; title: string; body?: string | null }[]>('/notifications'),
    ]);
    const changes = scheduleResponse.data.filter(entry => entry.room_changed);
    if (changes.length === 0) {
      const latestNotification = notificationsResponse.data.find(notification => notification.type === 'ROOM_CHANGED' && notification.body);
      if (latestNotification) {
        return `Your timetable reports no active room override for today. Your latest room-change notification says: ${latestNotification.body}`;
      }
      return 'There are no active room changes in your timetable or room-change notifications for today.';
    }
    return `Room changes in your timetable today: ${changes.map(entry => `${entry.subject_name || 'Class'}${entry.section_code ? ` (${entry.section_code})` : ''}: ${formatRoomCode(entry.base_room_code)} → ${formatRoomCode(entry.effective_room_code)}${entry.change_reason ? ` (${entry.change_reason})` : ''}`).join('; ')}.`;
  }

  if (/\b(next class|upcoming class|next lecture)\b/i.test(text)) {
    const response = await api.get<TimetableEntry[]>('/timetable/me');
    const today = (new Date().getDay() + 6) % 7;
    const ordered = response.data
      .map(entry => ({ entry, dayOffset: (entry.weekday - today + 7) % 7 }))
      .filter(item => item.dayOffset < 7)
      .sort((a, b) => a.dayOffset - b.dayOffset || a.entry.start_slot.localeCompare(b.entry.start_slot));
    const nowMinutes = new Date().getHours() * 60 + new Date().getMinutes();
    const upcoming = ordered.find(({ entry, dayOffset }) => {
      if (dayOffset > 0) return true;
      const match = entry.start_slot.match(/^(\d{1,2}):(\d{2})$/);
      const start = match ? Number(match[1]) * 60 + Number(match[2]) : PERIODS[entry.start_slot]?.[0];
      return start == null || start >= nowMinutes;
    });
    if (!upcoming) return 'I couldn’t find another class in your timetable.';
    const { entry, dayOffset } = upcoming;
    return `Your next class is ${entry.subject_name || 'a scheduled class'}${entry.section_code ? ` (${entry.section_code})` : ''}, ${dayOffset === 0 ? 'today' : WEEKDAYS[entry.weekday]} at ${formatSlot(entry.start_slot)} in ${formatRoomCode(entry.effective_room_code)}${entry.faculty_name ? ` with ${entry.faculty_name}` : ''}.`;
  }

  if (findRoomIntent(question) && targetCode) {
    const room = await lookupRoom(targetCode);
    const [blocksResponse, floorsResponse, routeResponse] = await Promise.all([
      api.get('/blocks'),
      api.get(`/blocks/${encodeURIComponent(room.block_id)}/floors`),
      api.get('/nav/route', { params: { target: room.id } }),
    ]);
    const block = blocksResponse.data.find((item: { id: string }) => item.id === room.block_id);
    const floor = floorsResponse.data.find((item: { id: string }) => item.id === room.floor_id);
    const route = String(routeResponse.data.route).replace(/\broom_([a-zA-Z0-9-]+)\b/g, '$1');
    return `${room.code} — ${room.display_name}. ${block?.name || 'Campus block'}${floor ? ` · ${floor.level === 1 ? '1st' : `${floor.level}th`} Floor` : ''}. Capacity: ${room.capacity ?? 'not listed'}. ${route}`;
  }

  const response = await api.post('/ai/chat', { message: question });
  return String(response.data.response || 'The campus assistant returned no response.')
    .replace(/\btt_[a-zA-Z0-9_-]+\b/g, 'affected timetable entry')
    .replace(/\broom_([a-zA-Z0-9-]+)\b/g, '$1');
}

export const AIAssistant: React.FC = () => {
  const { user } = useAuth();
  const [query, setQuery] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);

  const askMutation = useMutation({
    mutationFn: async (question: string) => answerQuestion(question, user?.role || ''),
    onSuccess: answer => setMessages(previous => [...previous, { role: 'ai', text: answer }]),
    onError: (error: any) => setMessages(previous => [...previous, {
      role: 'ai',
      text: error?.response?.data?.detail || error?.message || 'The campus assistant could not retrieve the requested information.',
    }]),
  });

  const askAI = (event?: React.FormEvent) => {
    event?.preventDefault();
    const question = query.trim();
    if (!question || askMutation.isPending) return;
    setMessages(previous => [...previous, { role: 'user', text: question }]);
    setQuery('');
    askMutation.mutate(question);
  };

  return (
    <section className="card max-w-3xl h-[min(680px,calc(100vh-8rem))] min-h-[420px] flex flex-col overflow-hidden">
      <header className="border-b border-slate-800 p-5">
        <div className="flex items-center gap-3">
          <div className="stat-icon bg-indigo-900"><Bot size={19} className="text-indigo-300" /></div>
          <div>
            <h1 className="font-semibold text-white">Campus AI Assistant</h1>
            <p className="text-xs text-slate-400 mt-1">
              Signed in as {user?.full_name || user?.email}
              {user?.role === 'STUDENT' ? ` · ${user.usn || 'USN not provisioned'} · ${user.section || 'Section not provisioned'}` : ` · ${user?.role || 'User'}`}
              . Answers use data scoped to your authenticated account.
            </p>
          </div>
        </div>
      </header>
      <div className="flex-1 overflow-y-auto p-5 space-y-4">
        {messages.length === 0 && (
          <div className="max-w-lg mx-auto py-8">
            <p className="text-center text-sm text-slate-300">Ask about campus locations, your schedule, room changes, or What-If impact.</p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-5">
              {['Where is A101?', 'What is my next class?', 'Did my classroom change?', 'What happens if A101 is unavailable?'].map(prompt => (
                <button key={prompt} onClick={() => setQuery(prompt)} className="text-left text-xs text-slate-300 p-3 rounded-lg border border-slate-800 hover:border-indigo-600 bg-slate-800/40">
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex gap-2 ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {message.role === 'ai' && <Bot size={17} className="text-indigo-300 mt-2 flex-shrink-0" />}
            <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-3 text-sm leading-relaxed ${message.role === 'user' ? 'bg-indigo-600 text-white' : 'bg-slate-800 text-slate-200'}`}>
              {message.text}
              {message.role === 'ai' && /What-If Simulator/.test(message.text) && (
                <Link className="flex items-center gap-1 text-indigo-300 text-xs mt-2" to="/simulator">Open What-If Simulator <MapPin size={12} /></Link>
              )}
              {message.role === 'ai' && /Open Safety & Harassment/.test(message.text) && (
                <Link className="flex items-center gap-1 text-indigo-300 text-xs mt-2" to="/report?type=SAFETY">Open Safety & Harassment <MapPin size={12} /></Link>
              )}
              {message.role === 'ai' && /Open Report Campus Issue/.test(message.text) && (
                <Link className="flex items-center gap-1 text-indigo-300 text-xs mt-2" to="/report?type=MAINTENANCE">Open Report Campus Issue <MapPin size={12} /></Link>
              )}
              {message.role === 'ai' && /Open Campus Food/.test(message.text) && (
                <Link className="flex items-center gap-1 text-indigo-300 text-xs mt-2" to="/food">Open Campus Food <MapPin size={12} /></Link>
              )}
              {message.role === 'ai' && /Emergency \/ SOS/.test(message.text) && (
                <Link className="flex items-center gap-1 text-red-300 text-xs mt-2" to="/report?type=EMERGENCY">Open Emergency / SOS <MapPin size={12} /></Link>
              )}
            </div>
            {message.role === 'user' && <UserRound size={17} className="text-slate-400 mt-2 flex-shrink-0" />}
          </div>
        ))}
        {askMutation.isPending && <p className="text-xs text-slate-500 flex items-center gap-2"><Bot size={14} /> Checking campus data…</p>}
        {askMutation.isError && <p role="status" className="text-xs text-amber-300 flex items-center gap-2"><AlertCircle size={14} /> The live data request failed.</p>}
      </div>
      <form onSubmit={askAI} className="border-t border-slate-800 p-4 flex gap-2">
        <input
          className="input-field"
          placeholder="Ask about A101, your next class, or room changes…"
          value={query}
          onChange={event => setQuery(event.target.value)}
          aria-label="Ask Campus AI"
        />
        <button type="submit" disabled={!query.trim() || askMutation.isPending} className="btn-primary px-3" aria-label="Send question">
          <Send size={17} />
        </button>
      </form>
    </section>
  );
};
