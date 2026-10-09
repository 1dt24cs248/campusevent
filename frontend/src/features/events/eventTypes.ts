export interface CampusEvent {
  id: string;
  title: string;
  category: string;
  description: string;
  start_dt: string;
  end_dt: string;
  location?: string | null;
  organizer?: string | null;
  audience: string;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
  created_by?: string | null;
  created_by_name?: string | null;
  decision_reason?: string | null;
  notes?: string | null;
  decided_by?: string | null;
  decided_at?: string | null;
}

export const EVENT_CATEGORIES = [
  ['HACKATHON', 'Hackathon'],
  ['TECHNICAL_EVENT', 'Technical Event'],
  ['WORKSHOP', 'Workshop'],
  ['SEMINAR', 'Seminar'],
  ['CONFERENCE', 'Conference'],
  ['GUEST_LECTURE', 'Guest Lecture'],
  ['PLACEMENT', 'Placement'],
  ['CLUB_ACTIVITY', 'Club Activity'],
  ['CULTURAL', 'Cultural'],
  ['SPORTS', 'Sports'],
  ['WEBINAR', 'Webinar'],
  ['CO_CURRICULAR', 'Co-curricular'],
  ['MEETING', 'Meeting'],
  ['OTHER', 'Other'],
] as const;

export function formatEventAudience(audience: string): string {
  if (audience === 'STUDENTS') return 'Students';
  if (audience === 'FACULTY') return 'Faculty';
  return 'Students + Faculty';
}

export function formatEventCategory(category: string): string {
  return EVENT_CATEGORIES.find(([value]) => value === category)?.[1] || category;
}
