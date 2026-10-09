import React, { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useSearchParams } from 'react-router-dom';
import api from '../../api/client';
import { AlertCircle, ArrowRight, MapPin, Search } from 'lucide-react';
import { floorLabel } from './navLocation';

interface Room {
  id: string;
  block_id: string;
  floor_id: string;
  code: string;
  display_name: string;
  resource_type: string;
  capacity: number | null;
}

interface Block {
  id: string;
  name: string;
}

interface Floor {
  id: string;
  block_id: string;
  level: number;
  name: string;
  label?: string | null;
}

interface NavigationNode {
  id: string;
  label: string;
}

interface NavigationResult {
  route: string;
  path: string;
  route_available: boolean;
  location: {
    id: string;
    block_id: string | null;
    floor_id: string | null;
    floor_level: number | null;
    code: string | null;
    display_name: string | null;
    resource_type: string | null;
    capacity: number | null;
    block: string;
    floor: string;
  };
}

function normalize(value: string): string {
  return value.toLowerCase().replace(/^room[_\s-]*/, '').replace(/[^a-z0-9]/g, '');
}

function requestError(error: unknown): string {
  if (typeof error === 'object' && error !== null && 'response' in error) {
    const response = error.response;
    if (typeof response === 'object' && response !== null && 'data' in response) {
      const data = response.data;
      if (typeof data === 'object' && data !== null && 'detail' in data && typeof data.detail === 'string') {
        return data.detail;
      }
    }
  }
  return error instanceof Error ? error.message : 'Could not load campus locations.';
}

export const NavPanel: React.FC = () => {
  const [searchParams] = useSearchParams();
  const formRef = useRef<HTMLFormElement>(null);
  const [target, setTarget] = useState(() => searchParams.get('target') || '');
  const [floorId, setFloorId] = useState('');
  const [startNodeId, setStartNodeId] = useState('');
  const [result, setResult] = useState<NavigationResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const { data: blocks = [], isError: blocksError } = useQuery<Block[]>({
    queryKey: ['navigator-blocks'],
    queryFn: async () => (await api.get<Block[]>('/blocks')).data,
  });
  const { data: floors = [], isError: floorsError } = useQuery<Floor[]>({
    queryKey: ['navigator-floors'],
    queryFn: async () => (await api.get<Floor[]>('/floors')).data,
  });
  const { data: rooms = [], isLoading: roomsLoading, isError: roomsError } = useQuery<Room[]>({
    queryKey: ['navigator-rooms', floorId],
    queryFn: async () => (await api.get<Room[]>('/rooms', {
      params: floorId ? { floor_id: floorId } : {},
    })).data,
  });
  const { data: nodes = [], isError: nodesError } = useQuery<NavigationNode[]>({
    queryKey: ['navigator-map-nodes'],
    queryFn: async () => (await api.get<NavigationNode[]>('/nav/nodes')).data,
  });

  useEffect(() => {
    const destination = searchParams.get('target');
    if (!destination) return;
    const timer = window.setTimeout(() => formRef.current?.requestSubmit(), 0);
    return () => window.clearTimeout(timer);
  }, [searchParams]);

  const navigateTo = async (destination: string, origin = startNodeId) => {
    setLoading(true);
    setError('');
    try {
      const response = await api.get<NavigationResult>('/nav/route', {
        params: {
          target: destination,
          ...(origin ? { start_node_id: origin } : {}),
        },
      });
      setResult(response.data);
    } catch (requestFailure) {
      setResult(null);
      setError(requestError(requestFailure));
    } finally {
      setLoading(false);
    }
  };

  const findDestination = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!target.trim()) return;
    await navigateTo(target.trim());
  };

  const matchingRooms = rooms.filter(room => {
    if (!target.trim()) return true;
    const query = normalize(target);
    return [room.id, room.code, room.display_name].some(value => normalize(value) === query);
  });
  const floorById = new Map(floors.map(floor => [floor.id, floor]));
  const blockById = new Map(blocks.map(block => [block.id, block]));

  return (
    <section className="card p-6 max-w-5xl space-y-5">
      <div>
        <div className="section-header">
          <MapPin size={20} className="text-cyan-400" />
          Campus Navigator
        </div>
        <p className="text-sm text-slate-400 mt-2">Search campus rooms by code or ID, or browse real rooms by floor.</p>
      </div>
      <form ref={formRef} onSubmit={findDestination} className="flex flex-col sm:flex-row gap-3">
        <input
          className="input-field"
          placeholder="Room code or ID"
          value={target}
          onChange={event => setTarget(event.target.value)}
          aria-label="Campus destination"
        />
        <button className="btn-primary flex items-center justify-center gap-2 sm:min-w-32" disabled={loading || !target.trim()}>
          <Search size={16} />
          {loading ? 'Finding…' : 'Find location'}
        </button>
      </form>

      {nodes.length > 0 && (
        <label className="block max-w-xl text-xs text-slate-400">
          Starting point for mapped directions
          <select
            className="input-field mt-1"
            value={startNodeId}
            onChange={event => setStartNodeId(event.target.value)}
            aria-label="Route starting point"
          >
            <option value="">Location only — no starting point selected</option>
            {nodes.map(node => <option key={node.id} value={node.id}>{node.label}</option>)}
          </select>
        </label>
      )}
      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-700/40 bg-red-900/20 p-3 text-sm text-red-300">
          <AlertCircle size={16} className="mt-0.5 flex-shrink-0" />
          {error}
        </div>
      )}
      {(blocksError || floorsError || roomsError || nodesError) && (
        <div role="alert" className="text-sm text-red-300">
          Campus location data could not be fully loaded.
        </div>
      )}

      <section className="border-t border-slate-800 pt-4 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="font-semibold text-slate-200">Campus locations</h2>
            <p className="text-xs text-slate-500">Showing records from the campus rooms API.</p>
          </div>
          <label className="text-xs text-slate-400">
            Filter by floor
            <select
              className="input-field mt-1 min-w-56"
              value={floorId}
              onChange={event => setFloorId(event.target.value)}
              aria-label="Filter locations by floor"
            >
              <option value="">All floors</option>
              {floors.map(floor => (
                <option key={floor.id} value={floor.id}>
                  {blockById.get(floor.block_id)?.name || 'Block'} · {floorLabel(floor)}
                </option>
              ))}
            </select>
          </label>
        </div>
        {roomsLoading ? <p className="text-sm text-slate-400">Loading campus locations…</p>
          : matchingRooms.length === 0 ? <p className="text-sm text-slate-500">No campus locations match this search and floor.</p>
            : <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {matchingRooms.map(room => {
                const floor = floorById.get(room.floor_id);
                const block = blockById.get(room.block_id);
                return (
                  <button
                    key={room.id}
                    type="button"
                    onClick={() => { setTarget(room.code); void navigateTo(room.id); }}
                    className="rounded-lg border border-slate-700 bg-slate-900/60 p-3 text-left hover:border-cyan-600"
                  >
                    <span className="flex items-center justify-between gap-2">
                      <span className="font-semibold text-white">{room.code}</span>
                      <span className="text-xs text-cyan-200">{room.resource_type}</span>
                    </span>
                    <span className="block text-xs text-slate-400 mt-1">{room.display_name}</span>
                    <span className="block text-xs text-slate-500 mt-1">
                      {block?.name || 'Block unavailable'} · {floor ? floorLabel(floor) : 'Floor unavailable'}
                      {room.capacity == null ? '' : ` · Capacity ${room.capacity}`}
                    </span>
                    <span className="sr-only">Room ID {room.id}</span>
                  </button>
                );
              })}
            </div>}
      </section>

      {result && (
        <div className="rounded-xl border border-slate-700 bg-slate-800/50 p-5 space-y-4" aria-live="polite">
          <div>
            <h2 className="text-lg font-semibold text-white">
              {result.location.code
                ? `${result.location.code} — ${result.location.display_name || 'Campus location'}`
                : result.location.display_name || result.location.id}
            </h2>
            <p className="text-sm text-slate-400 mt-1">
              {result.location.block} · {result.location.floor}
              {result.location.resource_type ? ` · ${result.location.resource_type}` : ''}
              {result.location.capacity == null ? '' : ` · Capacity ${result.location.capacity}`}
            </p>
          </div>
          <div className="border-t border-slate-700 pt-4 space-y-2">
            <h3 className="flex items-center gap-2 text-sm font-medium text-cyan-300">
              <ArrowRight size={15} /> {result.route_available ? 'Campus route' : 'Campus location'}
            </h3>
            <p className="text-sm text-slate-300">
              {result.route_available ? result.route : 'No mapped turn-by-turn route available.'}
            </p>
            {result.route_available && <p className="font-mono text-xs text-slate-500">{result.path}</p>}
          </div>
        </div>
      )}
      <p className="text-xs text-slate-600">No GPS position or walking distance is assumed.</p>
    </section>
  );
};
