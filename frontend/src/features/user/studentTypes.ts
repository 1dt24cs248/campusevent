export interface StudentProfileData {
  full_name: string;
  usn?: string | null;
  email: string;
  phone?: string | null;
  program?: string | null;
  department?: string | null;
  semester?: number | null;
  section?: string | null;
  admission_year?: number | null;
  academic_status?: string | null;
}

export interface StudentSubject {
  id: string;
  code: string;
  name: string;
  kind?: string | null;
  faculty: string[];
  demo_data: boolean;
  credits?: number | null;
  description?: string | null;
  attendance?: {
    total_classes: number;
    present: number;
    absent: number;
    percentage?: number | null;
  } | null;
  upcoming_assessments?: number;
  resources_count?: number;
}

export interface StudentTimetableEntry {
  id: string;
  section_id: string;
  section_code?: string | null;
  subject_id?: string | null;
  subject_code?: string | null;
  subject_name?: string | null;
  faculty_name?: string | null;
  weekday: number;
  start_slot: string;
  effective_start_slot?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  duration_slots: number;
  base_room_code?: string | null;
  effective_room_code?: string | null;
  room_changed: boolean;
  change_reason?: string | null;
  is_synthetic: boolean;
  is_extra_class?: boolean;
}

export const WEEKDAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

export function localDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function timeMinutes(value?: string | null): number | null {
  const match = value?.match(/^(\d{2}):(\d{2})$/);
  return match ? Number(match[1]) * 60 + Number(match[2]) : null;
}

export function formatTime(value?: string | null): string {
  const minutes = timeMinutes(value);
  if (minutes === null) return value || 'Time not published';
  const hour = Math.floor(minutes / 60);
  const minute = minutes % 60;
  const suffix = hour >= 12 ? 'PM' : 'AM';
  return `${hour % 12 || 12}:${String(minute).padStart(2, '0')} ${suffix}`;
}

export function formatTimeRange(entry: StudentTimetableEntry): string {
  if (entry.start_time && entry.end_time) {
    return `${formatTime(entry.start_time)} – ${formatTime(entry.end_time)}`;
  }
  return entry.effective_start_slot || entry.start_slot;
}

export function sortTimetable(entries: StudentTimetableEntry[]): StudentTimetableEntry[] {
  return [...entries].sort((a, b) => {
    const startA = timeMinutes(a.start_time);
    const startB = timeMinutes(b.start_time);
    if (startA !== null && startB !== null) return startA - startB;
    return (a.effective_start_slot || a.start_slot).localeCompare(b.effective_start_slot || b.start_slot);
  });
}
