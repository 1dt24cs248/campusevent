export interface FacultyTimetableEntry {
  id: string;
  section_id: string;
  section_code?: string | null;
  section_name?: string | null;
  subject_id?: string | null;
  subject_code?: string | null;
  subject_name?: string | null;
  faculty_name?: string | null;
  weekday: number;
  start_slot: string;
  start_time?: string | null;
  end_time?: string | null;
  kind: string;
  effective_room_code?: string | null;
  base_room_code?: string | null;
  room_changed: boolean;
  change_reason?: string | null;
  is_synthetic: boolean;
  is_extra_class?: boolean;
}

export interface ClassroomRequest {
  id: string;
  faculty_id: string;
  faculty_name: string;
  employee_id?: string | null;
  subject_id: string;
  subject_code: string;
  subject_name: string;
  section_id: string;
  section_code: string;
  requested_date: string;
  start_time: string;
  end_time: string;
  expected_strength: number;
  preferred_floor_id?: string | null;
  preferred_room_id?: string | null;
  preferred_room_code?: string | null;
  reason: string;
  status: 'PENDING' | 'APPROVED' | 'REJECTED' | 'CANCELLED';
  approved_room_id?: string | null;
  approved_room_code?: string | null;
  decision_reason?: string | null;
}

export interface FacultySubject {
  id: string;
  code: string;
  name: string;
  kind?: string | null;
  sections: string[];
  semesters: number[];
  demo_data: boolean;
}

export interface FacultySection {
  id: string;
  code: string;
  name: string;
  department?: string | null;
  year: number;
  strength: number;
  subjects: string[];
  demo_data: boolean;
}

export function localDateString(date: Date): string {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function formatTime(value?: string | null): string {
  if (!value) return 'Time not available';
  const [hourText, minute] = value.split(':');
  const hour = Number(hourText);
  return `${hour % 12 || 12}:${minute} ${hour >= 12 ? 'PM' : 'AM'}`;
}

export function entryStart(entry: FacultyTimetableEntry): number | null {
  if (!entry.start_time) return null;
  const [hours, minutes] = entry.start_time.split(':').map(Number);
  return hours * 60 + minutes;
}

export function entryEnd(entry: FacultyTimetableEntry): number | null {
  if (!entry.end_time) return null;
  const [hours, minutes] = entry.end_time.split(':').map(Number);
  return hours * 60 + minutes;
}

export function localMinutes(now: Date): number {
  return now.getHours() * 60 + now.getMinutes();
}
