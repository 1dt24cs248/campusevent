import React, { useState } from 'react';
import { useMutation, useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import api from '../../api/client';
import {
  Play, Save, CheckCircle, AlertTriangle, Info, ArrowRight, Zap, Clock, Building2, BarChart3,
  AlertCircle, XCircle, RefreshCw
} from 'lucide-react';

function normalizeRoom(roomId: string): string {
  return roomId.toLowerCase().replace(/^room[_\s-]*/, '').replace(/[^a-z0-9]/g, '');
}

const STRATEGIES = [
  { id: 'MIN_DISRUPTION', label: 'Min Disruption', desc: 'Minimize class reassignments' },
  { id: 'MIN_WALKING', label: 'Min Walking', desc: 'Keep rooms close together' },
];

const SCENARIO_TYPES = [
  { id: 'ROOM_UNAVAILABLE', label: 'Room Unavailable', icon: XCircle, desc: 'One or more A Block rooms closed for a day/time window' },
  { id: 'FLOOR_UNAVAILABLE', label: 'Floor Unavailable', icon: Building2, desc: 'An A Block floor closed (maintenance, event)' },
  { id: 'STRESS_TEST', label: 'Stress Test', icon: AlertTriangle, desc: 'Test system resilience under load' },
];

type Step = 1 | 2 | 3 | 4;

interface SimResult {
  scenario_id: string;
  affected_count: number;
  change_descriptions: string[];
  options: SolverOption[];
}

interface ResultRow {
  timetable_entry_id: string;
  subject_code?: string | null;
  subject_name?: string | null;
  section_code?: string | null;
  section_name?: string | null;
  academic_year?: number | null;
  faculty_name?: string | null;
  day?: string | null;
  start_time?: string | null;
  end_time?: string | null;
  original_room_code?: string | null;
  original_room_name?: string | null;
  assigned_room_code?: string | null;
  assigned_room_name?: string | null;
  class_strength?: number | null;
  room_capacity?: number | null;
  original_room_capacity?: number | null;
  room_capacity_provenance?: string | null;
  original_room_capacity_provenance?: string | null;
  required_facilities: string[];
  status: 'REASSIGNED' | 'UNCHANGED' | 'UNRESOLVED';
  reason: string;
  near_miss_rooms?: { room: string; reasons: string[] }[];
}

interface SolverOption {
  run_id?: string;
  status: string;
  option_label: string;
  strategy: string;
  assignments: Record<string, string>;
  unresolved: any[];
  result_rows?: ResultRow[];
  metrics: Record<string, any>;
  explanations: Record<string, string>;
  recovery: any[];
  solve_ms: number;
}

interface FloorRecord {
  id: string;
  level: number;
  name: string;
  label?: string | null;
}

interface BlockRecord {
  id: string;
  code: string;
  name: string;
}

interface RoomRecord {
  id: string;
  code: string;
  display_name: string;
  aliases: string[];
  resource_type: string;
  capacity: number | null;
  capacity_provenance: string | null;
  facilities: string[];
  floor_id: string;
}

interface OccupancyMetrics {
  occupied_room_periods: number;
  available_room_periods: number;
  rooms_in_use: number;
  rooms_with_unknown_capacity: number;
  by_room: { room_id: string; room_code: string; occupied_periods: number; available_periods: number; capacity: number | null; capacity_provenance: string | null }[];
}

function floorLabel(floor: FloorRecord): string {
  if (floor.level === -1) return 'Basement';
  if (floor.level === 0) return 'Ground Floor';
  const ordinal = new Map([[1, '1st Floor'], [2, '2nd Floor'], [3, '3rd Floor'], [4, '4th Floor'], [5, '5th Floor']]);
  return ordinal.get(floor.level) || floor.label || floor.name;
}

const StepIndicator = ({ current, step, label }: { current: Step; step: Step; label: string }) => {
  const done = current > step;
  const active = current === step;
  return (
    <div className={`flex items-center gap-2 ${active ? 'text-indigo-300' : done ? 'text-emerald-400' : 'text-slate-600'}`}>
      <div className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold border ${
        active ? 'border-indigo-500 bg-indigo-900/50 text-indigo-300' :
        done ? 'border-emerald-500 bg-emerald-900/50 text-emerald-300' :
        'border-slate-700 text-slate-600'
      }`}>
        {done ? <CheckCircle size={14} /> : step}
      </div>
      <span className="text-xs font-medium hidden sm:block">{label}</span>
    </div>
  );
};

export const Simulator: React.FC = () => {
  const [step, setStep] = useState<Step>(1);
  const [scenarioName, setScenarioName] = useState('Emergency Room Closure');
  const [scenarioType, setScenarioType] = useState('ROOM_UNAVAILABLE');
  const [roomsInput, setRoomsInput] = useState('A101');
  const [floorId, setFloorId] = useState('');
  const [timeFrom, setTimeFrom] = useState('08:00');
  const [timeTo, setTimeTo] = useState('18:00');
  const [closureWeekday, setClosureWeekday] = useState('ALL');
  const [fullDayClosure, setFullDayClosure] = useState(false);
  const [strategies, setStrategies] = useState(['MIN_DISRUPTION', 'MIN_WALKING']);
  const [simulationId, setSimulationId] = useState<string | null>(null);
  const [simulationResult, setSimulationResult] = useState<SimResult | null>(null);
  const [isReviewed, setIsReviewed] = useState(false);
  const [activeOptionIndex, setActiveOptionIndex] = useState(0);
  const [publishResult, setPublishResult] = useState<any>(null);
  const [error, setError] = useState('');
  const { data: blocks = [] } = useQuery<BlockRecord[]>({
    queryKey: ['campus-blocks', 'simulator'],
    queryFn: async () => (await api.get('/blocks')).data,
  });
  const aBlock = blocks.find(block => block.code.trim().toUpperCase() === 'A');
  const { data: floors = [] } = useQuery<FloorRecord[]>({
    queryKey: ['campus-floors', 'simulator', aBlock?.id],
    queryFn: async () => (await api.get(`/blocks/${encodeURIComponent(aBlock!.id)}/floors`)).data,
    enabled: Boolean(aBlock?.id),
  });
  const { data: aBlockRooms = [] } = useQuery<RoomRecord[]>({
    queryKey: ['campus-rooms', 'simulator', aBlock?.id],
    queryFn: async () => (await api.get(`/blocks/${encodeURIComponent(aBlock!.id)}/rooms`)).data,
    enabled: Boolean(aBlock?.id),
  });
  const { data: floorRooms = [] } = useQuery<RoomRecord[]>({
    queryKey: ['campus-floor-rooms', floorId],
    queryFn: async () => (await api.get(`/floors/${encodeURIComponent(floorId)}/rooms`)).data,
    enabled: scenarioType === 'FLOOR_UNAVAILABLE' && !!floorId,
  });
  const createMutation = useMutation({
    mutationFn: async (data: any) => {
      const r = await api.post('/scenarios', data);
      return r.data;
    },
  });

  const simulateMutation = useMutation({
    mutationFn: async (id: string) => {
      const r = await api.post(`/scenarios/${id}/simulate`, {
        strategies,
        time_limit_sec: 15,
      });
      return r.data;
    },
  });

  const reviewMutation = useMutation({
    mutationFn: async (id: string) => {
      const r = await api.post(`/scenarios/${id}/review`);
      return r.data;
    },
    onSuccess: () => setIsReviewed(true),
  });

  const publishMutation = useMutation({
    mutationFn: async ({ scenarioId, runId }: any) => {
      const r = await api.post(`/scenarios/${scenarioId}/approve-publish`, {
        run_id: runId,
        comment: 'Published via What-If Simulator',
      });
      return r.data;
    },
    onSuccess: (data) => {
      setPublishResult(data);
      setStep(4);
    },
  });

  const handleRunSimulation = async () => {
    setError('');
    setActiveOptionIndex(0);

    try {
      const closureWindow: Record<string, unknown> = {
        weekdays: closureWeekday === 'ALL'
          ? [0, 1, 2, 3, 4, 5]
          : [Number(closureWeekday)],
      };
      if (!fullDayClosure) {
        closureWindow.time_from = timeFrom;
        closureWindow.time_to = timeTo;
      }
      let payload: Record<string, unknown> = closureWindow;
      if (scenarioType === 'ROOM_UNAVAILABLE') {
        const roomCodes = roomsInput.split(',').map(s => s.trim()).filter(Boolean);
        if (roomCodes.length === 0) {
          setError('Please select at least one room.');
          return;
        }
        const roomIds = roomCodes.map(roomCode => {
          const target = normalizeRoom(roomCode);
          const room = aBlockRooms.find(candidate =>
            normalizeRoom(candidate.code) === target
            || normalizeRoom(candidate.display_name) === target
            || normalizeRoom(candidate.id) === target
            || candidate.aliases?.some(alias => normalizeRoom(alias) === target)
          );
          if (!room) throw new Error(`No A Block room matches “${roomCode}”.`);
          return room.id;
        });
        payload = { ...closureWindow, room_ids: roomIds };
      } else if (scenarioType === 'FLOOR_UNAVAILABLE') {
        if (!floorId) {
          setError('Please select a floor.');
          return;
        }
        payload = { ...closureWindow, floor_id: floorId };
      } else if (scenarioType === 'STRESS_TEST') {
        payload = { k: 5 };
      }

      const scenario = await createMutation.mutateAsync({
        name: scenarioName,
        category: scenarioType,
        changes: [{
          type: scenarioType,
          payload,
        }],
      });

      setSimulationId(scenario.id);
      const simResult = await simulateMutation.mutateAsync(scenario.id);
      setSimulationResult(simResult);
      setIsReviewed(false);
      setStep(3);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Simulation failed. Please try again.');
    }
  };

  const handleReview = async () => {
    if (!simulationId) {
      setError('No scenario is available to review.');
      return;
    }
    setError('');
    try {
      await reviewMutation.mutateAsync(simulationId);
    } catch (e: any) {
      setError(e?.response?.data?.detail || e?.message || 'Scenario review failed.');
    }
  };

  const handlePublish = async () => {
    const activeOption = simulationResult?.options?.[activeOptionIndex];
    const runId = activeOption?.run_id;
    if (!runId) {
      setError('No run ID found for this option.');
      return;
    }
    try {
      await publishMutation.mutateAsync({ scenarioId: simulationId, runId });
    } catch (e: any) {
      setError(e?.response?.data?.detail || 'Publish failed.');
    }
  };

  const activeOption = simulationResult?.options?.[activeOptionIndex];
  const isRunning = createMutation.isPending || simulateMutation.isPending;
  const rooms = roomsInput.split(',').map(s => s.trim()).filter(Boolean);
  const previewRooms = scenarioType === 'FLOOR_UNAVAILABLE'
    ? floorRooms.map(room => room.code)
    : scenarioType === 'ROOM_UNAVAILABLE'
      ? rooms
      : [];
  const previewWindow = fullDayClosure ? 'all teaching periods' : `${timeFrom}–${timeTo}`;
  const previewDay = closureWeekday === 'ALL'
    ? 'all weekdays'
    : ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'][Number(closureWeekday)];

  const assignmentCount = activeOption?.assignments
    ? Object.keys(activeOption.assignments).length
    : 0;

  const unresolvedCount = activeOption?.unresolved?.length || 0;
  const resultRows = activeOption?.result_rows || [];
  const reassignedCount = resultRows.filter(row => row.status === 'REASSIGNED').length;
  const unchangedCount = resultRows.filter(row => row.status === 'UNCHANGED').length;
  const completeAllocation = activeOption?.status === 'FEASIBLE'
    && (simulationResult?.affected_count ?? 0) > 0
    && unresolvedCount === 0
    && resultRows.length === simulationResult?.affected_count;
  const occupancyBefore = activeOption?.metrics?.room_occupancy_before as OccupancyMetrics | undefined;
  const occupancyAfter = activeOption?.metrics?.room_occupancy_after as OccupancyMetrics | undefined;

  // Get first explanation value
  const explanationText = activeOption?.explanations
    ? (typeof activeOption.explanations === 'object' && !Array.isArray(activeOption.explanations)
        ? Object.values(activeOption.explanations)[0] as string
        : Array.isArray(activeOption.explanations)
          ? (activeOption.explanations as string[])[0]
          : undefined)
    : undefined;

  return (
    <div className="space-y-6 max-w-6xl">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white flex items-center gap-2">
            <Zap size={22} className="text-indigo-400" />
            What-If Decision Simulator
          </h1>
          <p className="text-sm text-slate-400 mt-0.5">
            Model campus decisions before they happen · Powered by OR-Tools CP-SAT
          </p>
        </div>
      </div>

      {/* Step Indicators */}
      <div className="card p-4">
        <div className="flex items-center gap-4 overflow-x-auto">
          <StepIndicator current={step} step={1} label="Define Scenario" />
          <ArrowRight size={14} className="text-slate-700 flex-shrink-0" />
          <StepIndicator current={step} step={2} label="Configure & Run" />
          <ArrowRight size={14} className="text-slate-700 flex-shrink-0" />
          <StepIndicator current={step} step={3} label="Review Alternatives" />
          <ArrowRight size={14} className="text-slate-700 flex-shrink-0" />
          <StepIndicator current={step} step={4} label="Publish" />
        </div>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-4 bg-red-900/30 border border-red-700/50 rounded-xl text-red-300 text-sm">
          <AlertCircle size={16} className="flex-shrink-0" />
          {error}
          <button onClick={() => setError('')} className="ml-auto text-red-500 hover:text-red-300"><XCircle size={14} /></button>
        </div>
      )}

      {/* STEP 1 & 2: Setup */}
      {step <= 2 && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Config Panel */}
          <div className="card p-6 space-y-5">
            <h3 className="section-header">
              <Info size={17} className="text-indigo-400" />
              Scenario Setup
            </h3>

            <div>
              <label className="label">Scenario Name</label>
              <input
                className="input-field"
                value={scenarioName}
                onChange={e => setScenarioName(e.target.value)}
                placeholder="e.g. Emergency A101 Closure"
              />
            </div>

            <div>
              <label className="label">Scenario Type</label>
              <div className="space-y-2">
                {SCENARIO_TYPES.map(({ id, label, icon: Icon, desc }) => (
                  <button
                    key={id}
                    onClick={() => setScenarioType(id)}
                    className={`w-full p-3 rounded-lg border text-left transition-all ${
                      scenarioType === id
                        ? 'border-indigo-500 bg-indigo-900/30 text-indigo-300'
                        : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600'
                    }`}
                  >
                    <div className="flex items-center gap-2 text-sm font-medium">
                      <Icon size={14} />
                      {label}
                    </div>
                    <p className="text-xs mt-0.5 opacity-70">{desc}</p>
                  </button>
                ))}
              </div>
            </div>

            {scenarioType === 'ROOM_UNAVAILABLE' && (
              <div>
                <label className="label" htmlFor="scenario-room-input">Select Room</label>
                <input
                  id="scenario-room-input"
                  className="input-field"
                  value={roomsInput}
                  onChange={e => setRoomsInput(e.target.value)}
                  placeholder="A101, SH01"
                  list="a-block-room-codes"
                />
                <datalist id="a-block-room-codes">
                  {aBlockRooms.map(room => (
                    <option key={room.id} value={room.code}>
                      {room.display_name} · {room.resource_type} · capacity {room.capacity ?? 'not recorded'} ({room.capacity_provenance || 'provenance unavailable'})
                    </option>
                  ))}
                </datalist>
                <p className="text-xs text-slate-600 mt-1">
                  Choose existing A Block room codes; separate multiple rooms with commas.
                  {aBlock ? '' : ' A Block inventory could not be loaded.'}
                </p>
              </div>
            )}
            {scenarioType === 'FLOOR_UNAVAILABLE' && (
              <div>
                <label className="label" htmlFor="scenario-floor-select">Select Floor</label>
                <select
                  id="scenario-floor-select"
                  className="input-field"
                  value={floorId}
                  onChange={e => setFloorId(e.target.value)}
                >
                  <option value="">Choose an A Block floor</option>
                  {floors.map(floor => (
                    <option key={floor.id} value={floor.id}>{floorLabel(floor)}</option>
                  ))}
                </select>
              </div>
            )}
            {scenarioType === 'STRESS_TEST' && (
              <p className="text-sm text-slate-400">Stress condition: close the five busiest scheduled rooms.</p>
            )}

            {scenarioType !== 'STRESS_TEST' && <>
              <div>
                <label className="label" htmlFor="scenario-weekday">Affected weekday</label>
                <select id="scenario-weekday" className="input-field" value={closureWeekday} onChange={e => setClosureWeekday(e.target.value)}>
                  <option value="ALL">All weekdays</option>
                  {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'].map((day, index) => (
                    <option key={day} value={String(index)}>{day}</option>
                  ))}
                </select>
              </div>
              <label className="flex items-center gap-2 text-sm text-slate-300">
                <input type="checkbox" checked={fullDayClosure} onChange={event => setFullDayClosure(event.target.checked)} className="h-4 w-4 accent-indigo-500" />
                Close for the full day
              </label>
              {!fullDayClosure && <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">From</label>
                  <input type="time" className="input-field" value={timeFrom} onChange={e => setTimeFrom(e.target.value)} />
                </div>
                <div>
                  <label className="label">To</label>
                  <input type="time" className="input-field" value={timeTo} onChange={e => setTimeTo(e.target.value)} />
                </div>
              </div>}
            </>}

            <div>
              <label className="label">Optimization Strategies</label>
              <div className="space-y-2">
                {STRATEGIES.map(s => (
                  <label key={s.id} className="flex items-center gap-2 p-2 rounded-lg bg-slate-800/60 cursor-pointer hover:bg-slate-800">
                    <input
                      type="checkbox"
                      checked={strategies.includes(s.id)}
                      onChange={e => {
                        if (e.target.checked) setStrategies(prev => [...prev, s.id]);
                        else setStrategies(prev => prev.filter(x => x !== s.id));
                      }}
                      className="rounded border-slate-600"
                    />
                    <div>
                      <p className="text-xs font-medium text-slate-300">{s.label}</p>
                      <p className="text-xs text-slate-500">{s.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          </div>

          {/* Preview + Run */}
          <div className="lg:col-span-2 space-y-4">
            <div className="card p-6">
              <h3 className="section-header mb-4">
                <BarChart3 size={17} className="text-indigo-400" />
                Simulation Preview
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-3 gap-4 mb-6">
                <div className="bg-slate-800/60 rounded-xl p-4 text-center">
                  <p className="text-xs text-slate-500 mb-1">Scenario Type</p>
                  <p className="text-sm font-semibold text-indigo-300">{scenarioType}</p>
                </div>
                <div className="bg-slate-800/60 rounded-xl p-4 text-center">
                  <p className="text-xs text-slate-500 mb-1">Rooms Affected</p>
                  <p className="text-sm font-semibold text-amber-300">
                    {scenarioType === 'FLOOR_UNAVAILABLE' ? floorRooms.length : scenarioType === 'STRESS_TEST' ? '5 busiest' : rooms.length}
                  </p>
                </div>
                <div className="bg-slate-800/60 rounded-xl p-4 text-center">
                  <p className="text-xs text-slate-500 mb-1">Time Window</p>
                  <p className="text-sm font-semibold text-cyan-300">{previewDay} · {previewWindow}</p>
                </div>
              </div>

              <div className="space-y-2 mb-6">
                {previewRooms.map(r => (
                  <div key={r} className="flex items-center gap-2 p-2 bg-red-900/20 border border-red-800/40 rounded-lg text-sm text-red-300">
                    <XCircle size={14} />
                    <span className="font-mono">{r}</span>
                    <span className="text-red-500">→ Unavailable {previewDay} · {previewWindow}</span>
                  </div>
                ))}
              </div>

              <div className="p-4 bg-indigo-900/20 border border-indigo-700/30 rounded-xl mb-4">
                <div className="flex items-start gap-3">
                  <Zap size={16} className="text-indigo-400 mt-0.5 flex-shrink-0" />
                  <div className="text-sm text-slate-300">
                    <p className="font-medium text-indigo-300 mb-1">What will happen:</p>
                    <ul className="space-y-1 text-slate-400 text-xs">
                      <li>• CP-SAT solver finds alternative room assignments</li>
                      <li>• Hard constraints enforced: capacity, type, no double-booking</li>
                      <li>• Multiple strategies run in parallel: {strategies.join(', ') || 'none selected'}</li>
                      <li>• Results show affected classes, reassignments & impact</li>
                    </ul>
                  </div>
                </div>
              </div>

              <button
                onClick={handleRunSimulation}
                disabled={isRunning || strategies.length === 0}
                className="w-full btn-primary py-3 flex items-center justify-center gap-3 text-base"
              >
                {isRunning ? (
                  <>
                    <div className="w-5 h-5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    {createMutation.isPending ? 'Creating scenario...' : 'Running CP-SAT optimization...'}
                  </>
                ) : (
                  <>
                    <Play size={18} />
                    Run Simulation
                  </>
                )}
              </button>

              {isRunning && (
                <div className="mt-4 space-y-2">
                  <div className="flex items-center gap-2 text-xs text-slate-400">
                    <div className="w-3 h-3 border border-indigo-500 border-t-transparent rounded-full animate-spin" />
                    Analyzing campus state and constraints...
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1">
                    <div className="bg-indigo-500 h-1 rounded-full animate-pulse w-3/4" />
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* STEP 3: Results */}
      {step === 3 && simulationResult && (
        <div className="space-y-6">
          {simulationResult.options.length === 0 && (
            <div role="alert" className="rounded-lg border border-red-700/50 bg-red-900/20 p-4 text-sm text-red-200">
              The backend did not return a simulation option. No allocation can be reviewed or published.
            </div>
          )}
          {activeOption?.metrics?.stress_condition && (
            <div className="rounded-lg border border-amber-700/40 bg-amber-900/20 p-4 text-sm text-amber-200">
              Stress condition: {activeOption.metrics.stress_condition}
            </div>
          )}
          {activeOption && activeOption.status !== 'FEASIBLE' && (
            <div role="status" className="rounded-lg border border-amber-700/40 bg-amber-900/20 p-4 text-sm text-amber-200">
              This simulation is {activeOption.status.toLowerCase()}; the allocation is incomplete and cannot be published.
            </div>
          )}
          {simulationResult.affected_count === 0 && (
            <div role="status" className="rounded-lg border border-amber-700/40 bg-amber-900/20 p-4 text-sm text-amber-200">
              No scheduled timetable entries overlap this closure. No classes were reassigned or changed; check the current room assignments or choose a closure that affects scheduled classes.
            </div>
          )}
          {/* Summary stats */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div className="card p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Affected Classes</p>
              <p className="text-3xl font-bold text-red-400">{simulationResult.affected_count}</p>
            </div>
            <div className="card p-4 text-center">
            <p className="text-xs text-slate-500 mb-1">Reassigned</p>
            <p className="text-3xl font-bold text-emerald-400">{activeOption?.metrics?.reassigned_classes ?? reassignedCount}</p>
            </div>
            <div className="card p-4 text-center">
            <p className="text-xs text-slate-500 mb-1">Unchanged</p>
            <p className="text-3xl font-bold text-indigo-400">{activeOption?.metrics?.unchanged_classes ?? unchangedCount}</p>
            </div>
            <div className="card p-4 text-center">
              <p className="text-xs text-slate-500 mb-1">Unresolved</p>
              <p className={`text-3xl font-bold ${unresolvedCount > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                {unresolvedCount}
              </p>
            </div>
          </div>

          {/* Option tabs */}
          {simulationResult.options && simulationResult.options.length > 0 && (
            <div className="flex gap-2 overflow-x-auto">
              {simulationResult.options.map((opt, i) => (
                <button
                  key={i}
                  onClick={() => setActiveOptionIndex(i)}
                  className={`flex-shrink-0 px-4 py-2 rounded-lg text-sm font-medium border transition-all ${
                    activeOptionIndex === i
                      ? 'border-indigo-500 bg-indigo-900/40 text-indigo-300'
                      : 'border-slate-700 bg-slate-800/50 text-slate-400 hover:border-slate-600'
                  }`}
                >
                  Option {i + 1}
                  <span className={`ml-2 text-xs ${opt.status === 'FEASIBLE' ? 'text-emerald-400' : 'text-amber-400'}`}>
                    {opt.status}
                  </span>
                  {i === 0 && <span className="ml-1.5 badge-purple text-[10px]">Recommended</span>}
                </button>
              ))}
            </div>
          )}

          {/* Active Option Detail */}
          {activeOption && (
            <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
              {/* Assignments */}
              <div className="card p-6 lg:col-span-2">
                <div className="flex items-center justify-between mb-4">
                  <div className="section-header">
                    <CheckCircle size={17} className="text-emerald-400" />
                    Class Decisions
                  </div>
                  <div className="flex items-center gap-2 text-xs">
                    <span className="badge-blue">{activeOption.strategy}</span>
                    <Clock size={12} className="text-slate-500" />
                    <span className="text-slate-500">{activeOption.solve_ms}ms</span>
                  </div>
                </div>

                {resultRows.length > 0 ? (
                  <div className="space-y-3 max-h-[36rem] overflow-y-auto pr-2">
                    {resultRows.map(row => (
                      <article key={row.timetable_entry_id} className="rounded-lg border border-slate-700 bg-slate-800/50 p-4">
                        <div className="flex flex-wrap items-start justify-between gap-2">
                          <div>
                            <h4 className="font-semibold text-slate-100">
                              {row.subject_code && `${row.subject_code} — `}
                              {row.subject_name || row.timetable_entry_id}
                              {row.section_code && ` · ${row.section_code}`}
                            </h4>
                            <p className="text-xs text-slate-400 mt-1">
                              {row.academic_year != null && `Year ${row.academic_year}`}
                              {row.faculty_name && ` · Faculty: ${row.faculty_name}`}
                            </p>
                          </div>
                          <span className={`rounded-full px-2 py-1 text-xs font-semibold ${
                            row.status === 'REASSIGNED' ? 'bg-emerald-900/50 text-emerald-300' :
                            row.status === 'UNRESOLVED' ? 'bg-amber-900/50 text-amber-300' :
                            'bg-slate-700 text-slate-200'
                          }`}>{row.status}</span>
                        </div>
                        <p className="mt-2 text-sm text-slate-300">
                          {row.day || 'Day unavailable'} · {row.start_time || 'Time unavailable'}–{row.end_time || 'Time unavailable'}
                        </p>
                        <dl className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2 text-xs sm:grid-cols-3">
                          <div><dt className="text-slate-500">Original room</dt><dd className="text-slate-200">{row.original_room_code || row.original_room_name || 'Unavailable'} · capacity {row.original_room_capacity ?? 'not recorded'} ({row.original_room_capacity_provenance || 'provenance unavailable'})</dd></div>
                          <div><dt className="text-slate-500">Proposed room</dt><dd className="text-slate-200">{row.assigned_room_code || row.assigned_room_name || 'No feasible room'} · capacity {row.room_capacity ?? 'not recorded'} ({row.room_capacity_provenance || 'provenance unavailable'})</dd></div>
                          <div><dt className="text-slate-500">Section strength</dt><dd className="text-slate-200">{row.class_strength ?? 'Not recorded'}</dd></div>
                          <div className="sm:col-span-3"><dt className="text-slate-500">Required facilities</dt><dd className="text-slate-200">{row.required_facilities?.length ? row.required_facilities.join(', ') : 'None specified'}</dd></div>
                        </dl>
                        <p className="mt-3 text-sm text-slate-300"><span className="font-medium text-slate-400">Reason: </span>{row.reason}</p>
                        {row.near_miss_rooms && row.near_miss_rooms.length > 0 && (
                          <details className="mt-2 text-xs text-amber-200">
                            <summary className="cursor-pointer">Candidate room rejection details</summary>
                            <ul className="mt-2 space-y-1 pl-4">
                              {row.near_miss_rooms.map(candidate => (
                                <li key={candidate.room}><span className="font-medium">{candidate.room}:</span> {candidate.reasons.join('; ') || 'not eligible'}</li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </article>
                    ))}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">
                    {activeOption.assignments && Object.keys(activeOption.assignments).length > 0
                      ? 'Class details were not returned by the backend.'
                      : 'No affected class decisions in this option.'}
                  </p>
                )}

                {explanationText && resultRows.length === 0 && (
                  <div className="mt-4 p-4 bg-indigo-900/20 border border-indigo-700/30 rounded-lg">
                    <p className="text-xs font-medium text-indigo-400 mb-1 flex items-center gap-1">
                      <Info size={12} />
                      Solver Explanation
                    </p>
                    <p className="text-sm text-slate-300 italic">{explanationText}</p>
                  </div>
                )}
              </div>

              {/* Metrics + Action */}
              <div className="space-y-4">
                <div className="card p-5">
                  <div className="section-header mb-4">
                    <BarChart3 size={17} className="text-cyan-400" />
                    Impact Metrics
                  </div>
                  <div className="space-y-2">
                    {activeOption.metrics && typeof activeOption.metrics === 'object' && Object.keys(activeOption.metrics).length > 0 ? (
                      Object.entries(activeOption.metrics).filter(([, value]) => value === null || ['string', 'number', 'boolean'].includes(typeof value)).map(([key, value]) => (
                        <div key={key} className="flex justify-between items-center py-1.5 border-b border-slate-800 last:border-0">
                          <span className="text-xs text-slate-400 capitalize">{key.replace(/_/g, ' ')}</span>
                          <span className="text-xs font-semibold text-white">{String(value)}</span>
                        </div>
                      ))
                    ) : (
                      <>
                        <div className="flex justify-between py-1.5 border-b border-slate-800">
                          <span className="text-xs text-slate-400">Assignments</span>
                          <span className="text-xs font-semibold text-emerald-400">{assignmentCount}</span>
                        </div>
                        <div className="flex justify-between py-1.5 border-b border-slate-800">
                          <span className="text-xs text-slate-400">Unresolved</span>
                          <span className={`text-xs font-semibold ${unresolvedCount > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
                            {unresolvedCount}
                          </span>
                        </div>
                        <div className="flex justify-between py-1.5">
                          <span className="text-xs text-slate-400">Solve Time</span>
                          <span className="text-xs font-semibold text-slate-300">{activeOption.solve_ms}ms</span>
                        </div>
                      </>
                    )}
                  </div>
                </div>

                {(occupancyBefore || occupancyAfter) && (
                  <div className="card p-5 space-y-4">
                    <h3 className="section-header"><Building2 size={16} className="text-cyan-400" />Room occupancy</h3>
                    {[['Before', occupancyBefore], ['After proposal', occupancyAfter]].map(([label, metric]) => {
                      const value = metric as OccupancyMetrics | undefined;
                      if (!value) return null;
                      return (
                        <details key={label as string} className="rounded-lg border border-slate-800 p-3">
                          <summary className="cursor-pointer text-sm font-medium text-slate-200">
                            {label as string}: {value.occupied_room_periods} occupied room-periods / {value.available_room_periods} available
                          </summary>
                          <p className="mt-2 text-xs text-slate-400">{value.rooms_in_use} rooms in use · {value.rooms_with_unknown_capacity} eligible rooms with capacity not recorded</p>
                          <ul className="mt-2 max-h-48 space-y-1 overflow-y-auto text-xs text-slate-300">
                            {value.by_room.filter(room => room.occupied_periods > 0).map(room => (
                              <li key={room.room_id} className="flex justify-between gap-2">
                                <span>{room.room_code} · {room.occupied_periods} occupied periods</span>
                                <span>Capacity {room.capacity ?? 'not recorded'} · {room.capacity_provenance || 'provenance unavailable'}</span>
                              </li>
                            ))}
                          </ul>
                        </details>
                      );
                    })}
                  </div>
                )}

                <div className="card p-5 space-y-3">
                  <div className="section-header mb-1">
                    <Save size={16} className="text-emerald-400" />
                    Decision
                  </div>
                  <p className="text-xs text-slate-400">
                    Review the selected alternative first. Publishing creates date-specific overrides for the next occurrence of each affected class, not recurring timetable changes, and notifies affected students and faculty.
                  </p>
                  {!completeAllocation && (
                    <p className="text-xs text-amber-300">Publishing is disabled until every affected class has a valid assignment.</p>
                  )}
                  <button
                    onClick={handleReview}
                    disabled={isReviewed || reviewMutation.isPending}
                    className="w-full btn-secondary flex items-center justify-center gap-2"
                  >
                    {reviewMutation.isPending ? 'Recording review…' : isReviewed ? 'Impact reviewed' : 'Review impact'}
                  </button>
                  <button
                    onClick={handlePublish}
                    disabled={!isReviewed || !completeAllocation || publishMutation.isPending}
                    className="w-full btn-success flex items-center justify-center gap-2 disabled:opacity-50"
                  >
                    {publishMutation.isPending ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Publishing...
                      </>
                    ) : (
                      <>
                        <Save size={15} />
                        {isReviewed ? 'Approve & Publish' : 'Review before publishing'}
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => { setStep(1); setSimulationResult(null); setIsReviewed(false); setError(''); }}
                    className="w-full btn-secondary flex items-center justify-center gap-2 text-sm"
                  >
                    <RefreshCw size={14} />
                    Run Another Scenario
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* STEP 4: Published */}
      {step === 4 && publishResult && (
        <div className="card p-12 text-center max-w-lg mx-auto">
          <div className="w-16 h-16 rounded-full bg-emerald-900/40 border border-emerald-500/50 flex items-center justify-center mx-auto mb-6">
            <CheckCircle size={28} className="text-emerald-400" />
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Scenario Published!</h2>
          <p className="text-slate-400 text-sm mb-6">
            The CP-SAT optimized room assignments are now live.
          </p>

          <div className="grid grid-cols-3 gap-4 mb-6">
            <div className="bg-slate-800/60 rounded-xl p-4">
              <p className="text-2xl font-bold text-indigo-400">{publishResult.version_no}</p>
              <p className="text-xs text-slate-500 mt-1">Version</p>
            </div>
            <div className="bg-slate-800/60 rounded-xl p-4">
              <p className="text-2xl font-bold text-emerald-400">{publishResult.overrides_created}</p>
              <p className="text-xs text-slate-500 mt-1">Overrides</p>
            </div>
            <div className="bg-slate-800/60 rounded-xl p-4">
              <p className="text-2xl font-bold text-cyan-400">{publishResult.notifications_created}</p>
              <p className="text-xs text-slate-500 mt-1">Notifications</p>
            </div>
          </div>

          <p className="text-xs text-slate-500 mb-6">{publishResult.summary}</p>

          <div className="flex gap-3 justify-center">
            <Link to="/management" className="btn-primary">
              Back to Dashboard
            </Link>
            <button
              onClick={() => { setStep(1); setSimulationResult(null); setIsReviewed(false); setPublishResult(null); setError(''); }}
              className="btn-secondary"
            >
              New Scenario
            </button>
          </div>
        </div>
      )}
    </div>
  );
};
