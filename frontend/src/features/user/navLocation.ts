export interface FloorLabelSource {
  level: number;
  label?: string | null;
  name: string;
}

export function floorLabel(floor: FloorLabelSource): string {
  if (floor.level === -1) return 'Basement';
  if (floor.label?.trim()) return floor.label;
  if (floor.level === 0) return 'Ground Floor';
  const suffix = floor.level % 100 >= 11 && floor.level % 100 <= 13
    ? 'th'
    : ({ 1: 'st', 2: 'nd', 3: 'rd' } as Record<number, string>)[floor.level % 10] || 'th';
  return `${floor.level}${suffix} Floor`;
}
