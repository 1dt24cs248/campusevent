import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Check, Plus, Utensils, X } from 'lucide-react';
import api from '../../api/client';

interface Stall {
  id: string;
  name: string;
  room_id: string;
  room_code: string | null;
  display_name: string | null;
  location_text: string | null;
  location: string;
  description: string | null;
  active: boolean;
}

interface MenuItem {
  id: string;
  item: string;
  category: string;
  description: string | null;
  price: number;
  dietary: string;
  dietary_note: string | null;
  available: boolean;
}

interface Menu {
  id: string;
  location_id: string;
  stall: Stall;
  title: string;
  menu_date: string;
  status: 'DRAFT' | 'PUBLISHED' | 'UNPUBLISHED';
  item_count: number;
  updated_at: string;
  items: MenuItem[];
}

interface Room {
  id: string;
  code: string;
  display_name: string;
}

interface Block {
  id: string;
  name: string;
}

interface ItemDraft {
  item: string;
  category: string;
  description: string;
  price: string;
  dietary: string;
  dietary_note: string;
  available: boolean;
}

const EMPTY_ITEM: ItemDraft = {
  item: '', category: 'OTHER', description: '', price: '0',
  dietary: 'OTHER', dietary_note: '', available: true,
};

function localDate() {
  const now = new Date();
  return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
}

export const FoodManagement: React.FC = () => {
  const queryClient = useQueryClient();
  const [error, setError] = useState('');
  const [stallName, setStallName] = useState('');
  const [roomId, setRoomId] = useState('');
  const [stallLocation, setStallLocation] = useState('');
  const [stallDescription, setStallDescription] = useState('');
  const [menuLocation, setMenuLocation] = useState('');
  const [menuDate, setMenuDate] = useState(localDate);
  const [menuTitle, setMenuTitle] = useState('');
  const [menuEdits, setMenuEdits] = useState<Record<string, { title: string; date: string }>>({});
  const [itemDrafts, setItemDrafts] = useState<Record<string, ItemDraft>>({});
  const [stallEdits, setStallEdits] = useState<Record<string, { name: string; location_text: string; description: string }>>({});
  const { data: stalls = [], isLoading: stallsLoading, isError: stallsError } = useQuery<Stall[]>({
    queryKey: ['management-food-stalls'],
    queryFn: async () => (await api.get('/food/stalls')).data,
  });
  const { data: menus = [], isLoading: menusLoading, isError: menusError } = useQuery<Menu[]>({
    queryKey: ['management-food-menus'],
    queryFn: async () => (await api.get('/food/menus')).data,
  });
  const { data: blocks = [] } = useQuery<Block[]>({
    queryKey: ['management-food-blocks'],
    queryFn: async () => (await api.get('/blocks')).data,
  });
  const { data: rooms = [] } = useQuery<Room[]>({
    queryKey: ['management-food-rooms', blocks.map(block => block.id).join(',')],
    enabled: blocks.length > 0,
    queryFn: async () => {
      const responses = await Promise.all(blocks.map(block => api.get<Room[]>(`/blocks/${encodeURIComponent(block.id)}/rooms`)));
      return responses.flatMap(response => response.data);
    },
  });
  const refresh = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['management-food-stalls'] }),
      queryClient.invalidateQueries({ queryKey: ['management-food-menus'] }),
      queryClient.invalidateQueries({ queryKey: ['published-food-menus'] }),
      queryClient.invalidateQueries({ queryKey: ['food-menu'] }),
      queryClient.invalidateQueries({ queryKey: ['food-locations'] }),
      queryClient.invalidateQueries({ queryKey: ['notifications'] }),
    ]);
  };
  const createStall = useMutation({
    mutationFn: async () => api.post('/food/stalls', {
      room_id: roomId, name: stallName.trim(),
      location_text: stallLocation.trim() || null,
      description: stallDescription.trim() || null,
    }),
    onSuccess: async () => {
      setStallName(''); setRoomId(''); setStallLocation(''); setStallDescription('');
      setError(''); await refresh();
    },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to create the food stall.'),
  });
  const updateStall = useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: Record<string, unknown> }) => api.patch(`/food/stalls/${id}`, patch),
    onSuccess: async () => { setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to update the food stall.'),
  });
  const createMenu = useMutation({
    mutationFn: async () => api.post('/food/menus', {
      location_id: menuLocation, menu_date: menuDate, title: menuTitle.trim(),
    }),
    onSuccess: async () => { setMenuTitle(''); setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to create the menu.'),
  });
  const updateMenu = useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: Record<string, unknown> }) => api.patch(`/food/menus/${id}`, patch),
    onSuccess: async () => { setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to update the menu.'),
  });
  const addItem = useMutation({
    mutationFn: async ({ menuId, draft }: { menuId: string; draft: ItemDraft }) => api.post(`/food/menus/${menuId}/items`, {
      item: draft.item.trim(), category: draft.category,
      description: draft.description.trim() || null,
      price: Number(draft.price), dietary: draft.dietary,
      dietary_note: draft.dietary_note.trim() || null, available: draft.available,
    }),
    onSuccess: async (_, variables) => {
      setItemDrafts(current => ({ ...current, [variables.menuId]: EMPTY_ITEM }));
      setError(''); await refresh();
    },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to add the menu item.'),
  });
  const updateItem = useMutation({
    mutationFn: async ({ id, patch }: { id: string; patch: Record<string, unknown> }) => api.patch(`/food/menu-items/${id}`, patch),
    onSuccess: async () => { setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to update the menu item.'),
  });
  const deleteItem = useMutation({
    mutationFn: async (itemId: string) => api.delete(`/food/menu-items/${itemId}`),
    onSuccess: async () => { setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to remove the menu item.'),
  });
  const publishMenu = useMutation({
    mutationFn: async (menuId: string) => api.post(`/food/menus/${menuId}/publish`),
    onSuccess: async () => { setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to publish the menu.'),
  });
  const unpublishMenu = useMutation({
    mutationFn: async (menuId: string) => api.post(`/food/menus/${menuId}/unpublish`),
    onSuccess: async () => { setError(''); await refresh(); },
    onError: (failure: any) => setError(failure?.response?.data?.detail || 'Unable to unpublish the menu.'),
  });

  const setItemField = (menuId: string, field: keyof ItemDraft, value: string | boolean) => {
    setItemDrafts(current => ({
      ...current,
      [menuId]: { ...(current[menuId] || EMPTY_ITEM), [field]: value },
    }));
  };
  const editMenu = (menu: Menu) => menuEdits[menu.id] || { title: menu.title, date: menu.menu_date };
  const editStall = (stall: Stall) => stallEdits[stall.id] || {
    name: stall.name, location_text: stall.location_text || '', description: stall.description || '',
  };
  const menuGroups: Array<[string, Menu[]]> = [
    ["Today's Menus", menus.filter(menu => menu.menu_date === localDate() && menu.status === 'PUBLISHED')],
    ['Draft Menus', menus.filter(menu => menu.status === 'DRAFT')],
    ['Published Menus', menus.filter(menu => menu.status === 'PUBLISHED' && menu.menu_date !== localDate())],
    ['Unpublished / Previous Menus', menus.filter(menu => menu.status === 'UNPUBLISHED' || (menu.status === 'PUBLISHED' && menu.menu_date < localDate()))],
  ];

  return (
    <section className="max-w-6xl space-y-5">
      <header>
        <h1 className="section-header"><Utensils size={20} className="text-amber-300" />Food &amp; Canteen Management</h1>
        <p className="mt-2 text-sm text-slate-400">Manage stalls and publish date-specific menus for students and faculty.</p>
      </header>
      {error && <p role="alert" className="card flex items-start gap-2 p-4 text-sm text-red-300"><AlertCircle size={16} />{error}</p>}
      {(stallsError || menusError) && <p role="alert" className="card p-4 text-sm text-red-300">Food management data could not be loaded.</p>}

      <section className="card space-y-4 p-5">
        <div>
          <h2 className="font-semibold text-white">Food Stalls</h2>
          <p className="mt-1 text-xs text-slate-500">Locations must be connected to an existing active campus room. No synthetic locations are preloaded.</p>
        </div>
        <form onSubmit={event => { event.preventDefault(); createStall.mutate(); }} className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <label className="text-xs text-slate-400">Stall name<input className="input-field mt-1" value={stallName} onChange={event => setStallName(event.target.value)} maxLength={120} required /></label>
          <label className="text-xs text-slate-400">Campus room<select className="input-field mt-1" value={roomId} onChange={event => setRoomId(event.target.value)} required><option value="">Choose active room</option>{rooms.map(room => <option key={room.id} value={room.id}>{room.code} · {room.display_name}</option>)}</select></label>
          <label className="text-xs text-slate-400">Location description<input className="input-field mt-1" value={stallLocation} onChange={event => setStallLocation(event.target.value)} maxLength={240} placeholder="Optional text location" /></label>
          <label className="text-xs text-slate-400">Description<input className="input-field mt-1" value={stallDescription} onChange={event => setStallDescription(event.target.value)} maxLength={1000} placeholder="Optional" /></label>
          <div className="sm:col-span-2 xl:col-span-4"><button className="btn-primary inline-flex items-center gap-2" disabled={createStall.isPending}><Plus size={15} />{createStall.isPending ? 'Creating…' : 'Create stall'}</button></div>
        </form>
        {stallsLoading ? <p className="text-sm text-slate-400">Loading stalls…</p> : stalls.length === 0 ? (
          <p className="rounded-lg border border-slate-800 p-4 text-sm text-slate-400">No food stalls have been configured.</p>
        ) : (
          <div className="grid gap-3 lg:grid-cols-2">
            {stalls.map(stall => {
              const edit = editStall(stall);
              return (
                <article key={stall.id} className="rounded-lg border border-slate-800 p-4">
                  <div className="mb-3 flex items-center justify-between gap-2">
                    <div><h3 className="font-medium text-white">{stall.name}</h3><p className="text-xs text-slate-500">{stall.room_code || 'Room unavailable'} · {stall.active ? 'Active' : 'Inactive'}</p></div>
                    <button type="button" className="btn-secondary" disabled={updateStall.isPending} onClick={() => {
                      if (stall.active && !window.confirm(`Deactivate ${stall.name}? Its menus will no longer appear to students or faculty.`)) return;
                      updateStall.mutate({ id: stall.id, patch: { active: !stall.active } });
                    }}>{stall.active ? 'Deactivate' : 'Activate'}</button>
                  </div>
                  <div className="grid gap-2 sm:grid-cols-3">
                    <label className="text-xs text-slate-400">Name<input className="input-field mt-1" value={edit.name} onChange={event => setStallEdits(current => ({ ...current, [stall.id]: { ...edit, name: event.target.value } }))} /></label>
                    <label className="text-xs text-slate-400">Location text<input className="input-field mt-1" value={edit.location_text} onChange={event => setStallEdits(current => ({ ...current, [stall.id]: { ...edit, location_text: event.target.value } }))} /></label>
                    <label className="text-xs text-slate-400">Description<input className="input-field mt-1" value={edit.description} onChange={event => setStallEdits(current => ({ ...current, [stall.id]: { ...edit, description: event.target.value } }))} /></label>
                  </div>
                  <button type="button" className="btn-secondary mt-3" disabled={updateStall.isPending} onClick={() => updateStall.mutate({ id: stall.id, patch: { name: edit.name, location_text: edit.location_text || null, description: edit.description || null } })}>Save stall changes</button>
                </article>
              );
            })}
          </div>
        )}
      </section>

      <section className="card space-y-4 p-5">
        <div><h2 className="font-semibold text-white">Create Menu</h2><p className="mt-1 text-xs text-slate-500">New menus start as drafts and are visible only to management.</p></div>
        <form onSubmit={event => { event.preventDefault(); createMenu.mutate(); }} className="grid grid-cols-1 gap-3 sm:grid-cols-4">
          <label className="text-xs text-slate-400">Food stall<select className="input-field mt-1" value={menuLocation} onChange={event => setMenuLocation(event.target.value)} required><option value="">Select active stall</option>{stalls.filter(stall => stall.active).map(stall => <option key={stall.id} value={stall.id}>{stall.name}</option>)}</select></label>
          <label className="text-xs text-slate-400">Menu date<input className="input-field mt-1" type="date" value={menuDate} onChange={event => setMenuDate(event.target.value)} required /></label>
          <label className="text-xs text-slate-400">Title / meal period<input className="input-field mt-1" value={menuTitle} onChange={event => setMenuTitle(event.target.value)} maxLength={120} required placeholder="Breakfast, Lunch…" /></label>
          <div className="flex items-end"><button className="btn-primary inline-flex items-center gap-2" disabled={createMenu.isPending}><Plus size={15} />Create draft</button></div>
        </form>
      </section>

      <section className="space-y-4">
        {menusLoading ? <div className="card p-5 text-sm text-slate-400">Loading menus…</div> : menus.length === 0 ? (
          <div className="card p-5 text-sm text-slate-400">No menus have been created.</div>
        ) : menuGroups.map(([heading, group]) => group.length > 0 && (
          <div key={heading} className="space-y-3">
            <h2 className="text-base font-semibold text-white">{heading}</h2>
            {group.map(menu => {
              const edit = editMenu(menu);
              const draft = itemDrafts[menu.id] || EMPTY_ITEM;
              const canEdit = menu.status !== 'PUBLISHED';
              return (
                <article key={menu.id} className="card space-y-4 p-5">
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div className="flex-1">
                      <div className="flex flex-wrap items-center gap-2"><h3 className="font-semibold text-white">{menu.stall.name} · {menu.title}</h3><span className={menu.status === 'PUBLISHED' ? 'badge-green' : menu.status === 'DRAFT' ? 'badge-amber' : 'badge-blue'}>{menu.status}</span></div>
                      <p className="mt-1 text-xs text-slate-400">{menu.menu_date} · {menu.item_count} items · Updated {menu.updated_at ? new Date(menu.updated_at).toLocaleString() : 'date unavailable'}</p>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {menu.status === 'PUBLISHED' ? (
                        <button type="button" className="btn-secondary inline-flex items-center gap-2 text-amber-200" disabled={unpublishMenu.isPending} onClick={() => {
                          if (window.confirm(`Unpublish "${menu.title}"? It will disappear from student and faculty food pages.`)) unpublishMenu.mutate(menu.id);
                        }}><X size={14} />Unpublish</button>
                      ) : (
                        <button type="button" className="btn-primary inline-flex items-center gap-2" disabled={publishMenu.isPending || menu.item_count === 0 || !menu.stall.active} onClick={() => publishMenu.mutate(menu.id)}><Check size={14} />Publish</button>
                      )}
                    </div>
                  </div>
                  {canEdit && (
                    <div className="grid gap-2 sm:grid-cols-[1fr_220px_auto]">
                      <label className="text-xs text-slate-400">Edit menu title<input className="input-field mt-1" value={edit.title} onChange={event => setMenuEdits(current => ({ ...current, [menu.id]: { ...edit, title: event.target.value } }))} /></label>
                      <label className="text-xs text-slate-400">Menu date<input type="date" className="input-field mt-1" value={edit.date} onChange={event => setMenuEdits(current => ({ ...current, [menu.id]: { ...edit, date: event.target.value } }))} /></label>
                      <div className="flex items-end"><button type="button" className="btn-secondary" onClick={() => updateMenu.mutate({ id: menu.id, patch: { title: edit.title, menu_date: edit.date } })}>Save menu</button></div>
                    </div>
                  )}
                  {menu.items.length > 0 && (
                    <div className="divide-y divide-slate-800 rounded-lg border border-slate-800">
                      {menu.items.map(item => (
                        <div key={item.id} className="flex flex-col gap-2 p-3 sm:flex-row sm:items-center sm:justify-between">
                          <div><p className="text-sm font-medium text-slate-200">{item.item} · ₹{Number(item.price).toFixed(2)}</p><p className="text-xs text-slate-500">{item.category} · {item.available ? 'Available' : 'Unavailable'}{item.description ? ` · ${item.description}` : ''}</p></div>
                          {canEdit && <div className="flex gap-2">
                            <button type="button" className="btn-secondary" onClick={() => updateItem.mutate({ id: item.id, patch: { available: !item.available } })}>{item.available ? 'Mark unavailable' : 'Mark available'}</button>
                            <button type="button" aria-label={`Remove ${item.item}`} className="btn-secondary text-red-300" onClick={() => {
                              if (window.confirm(`Remove "${item.item}" from this menu?`)) deleteItem.mutate(item.id);
                            }}>Remove</button>
                          </div>}
                        </div>
                      ))}
                    </div>
                  )}
                  {canEdit && (
                    <form onSubmit={event => { event.preventDefault(); addItem.mutate({ menuId: menu.id, draft }); }} className="grid grid-cols-1 gap-2 border-t border-slate-800 pt-4 sm:grid-cols-2 xl:grid-cols-4">
                      <label className="text-xs text-slate-400">Item name<input className="input-field mt-1" value={draft.item} onChange={event => setItemField(menu.id, 'item', event.target.value)} required /></label>
                      <label className="text-xs text-slate-400">Category<select className="input-field mt-1" value={draft.category} onChange={event => setItemField(menu.id, 'category', event.target.value)}>{['BREAKFAST', 'LUNCH', 'SNACK', 'BEVERAGE', 'OTHER'].map(category => <option key={category}>{category}</option>)}</select></label>
                      <label className="text-xs text-slate-400">Price (₹)<input className="input-field mt-1" type="number" min="0" step="0.01" value={draft.price} onChange={event => setItemField(menu.id, 'price', event.target.value)} required /></label>
                      <label className="text-xs text-slate-400">Dietary<select className="input-field mt-1" value={draft.dietary} onChange={event => setItemField(menu.id, 'dietary', event.target.value)}>{['VEGETARIAN', 'NON_VEGETARIAN', 'VEGAN', 'OTHER'].map(diet => <option key={diet}>{diet}</option>)}</select></label>
                      <label className="text-xs text-slate-400">Description<input className="input-field mt-1" value={draft.description} onChange={event => setItemField(menu.id, 'description', event.target.value)} /></label>
                      <label className="text-xs text-slate-400">Dietary / allergen note<input className="input-field mt-1" value={draft.dietary_note} onChange={event => setItemField(menu.id, 'dietary_note', event.target.value)} /></label>
                      <label className="flex items-center gap-2 self-end pb-2 text-xs text-slate-400"><input type="checkbox" checked={draft.available} onChange={event => setItemField(menu.id, 'available', event.target.checked)} />Available</label>
                      <div className="flex items-end"><button type="submit" className="btn-secondary inline-flex items-center gap-2" disabled={addItem.isPending}><Plus size={14} />Add item</button></div>
                    </form>
                  )}
                </article>
              );
            })}
          </div>
        ))}
      </section>
    </section>
  );
};
