import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { AlertCircle, MapPin, Utensils } from 'lucide-react';
import api from '../../api/client';

interface FoodMenuItem {
  id: string;
  item: string;
  category: string;
  description: string | null;
  price: number;
  dietary: string;
  dietary_note: string | null;
  available: boolean;
}

interface FoodMenu {
  id: string;
  title: string;
  menu_date: string;
  published_at: string | null;
  stall: {
    id: string;
    name: string;
    location: string;
    location_text: string | null;
    room_code: string | null;
    display_name: string | null;
    opening_hours: string | null;
    description: string | null;
  };
  items: FoodMenuItem[];
}

function localDate(value: Date) {
  return `${value.getFullYear()}-${String(value.getMonth() + 1).padStart(2, '0')}-${String(value.getDate()).padStart(2, '0')}`;
}

function categoryLabel(value: string) {
  return value.charAt(0) + value.slice(1).toLowerCase();
}

export const FoodPage: React.FC = () => {
  const [date, setDate] = useState(() => localDate(new Date()));
  const [dateChoices] = useState(() => {
    const now = new Date();
    return {
      today: localDate(now),
      yesterday: localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() - 1)),
      tomorrow: localDate(new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1)),
    };
  });
  const { data: menus = [], isLoading, isError } = useQuery<FoodMenu[]>({
    queryKey: ['published-food-menus', date],
    queryFn: async () => (await api.get('/food/menus', { params: { date } })).data,
  });
  return (
    <section className="max-w-5xl space-y-5">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <div className="section-header"><Utensils size={20} className="text-amber-300" />Campus Food</div>
          <p className="mt-2 text-sm text-slate-400">Menus published by campus management for students and faculty.</p>
        </div>
        <div className="flex flex-wrap items-end gap-2">
          <div className="flex gap-2">
            {[['Yesterday', dateChoices.yesterday], ['Today', dateChoices.today], ['Tomorrow', dateChoices.tomorrow]].map(([label, value]) => (
              <button
                key={value}
                type="button"
                className={date === value ? 'btn-primary' : 'btn-secondary'}
                onClick={() => setDate(value)}
              >
                {label}
              </button>
            ))}
          </div>
          <label className="text-xs text-slate-400">Choose another date
            <input type="date" className="input-field mt-1" value={date} onChange={event => setDate(event.target.value)} />
          </label>
        </div>
      </header>

      {isError ? (
        <div role="alert" className="card flex gap-2 p-4 text-sm text-red-300"><AlertCircle size={16} />Unable to load campus food menus.</div>
      ) : isLoading ? (
        <div className="card p-6 text-sm text-slate-400">Loading published menus…</div>
      ) : menus.length === 0 ? (
        <div className="card p-10 text-center">
          <Utensils size={26} className="mx-auto mb-3 text-slate-600" />
          <p className="text-sm text-slate-300">No menu has been published for this date.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {menus.map(menu => (
            <article key={menu.id} className="card p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <h2 className="text-lg font-semibold text-white">{menu.stall.name}</h2>
                  <p className="mt-1 text-sm text-slate-400">{menu.stall.location}</p>
                  <p className="mt-2 text-xs text-slate-500">{menu.title} · {menu.menu_date}</p>
                </div>
                <span className="badge-green">Published</span>
              </div>
              {menu.stall.description && <p className="mt-3 text-sm text-slate-400">{menu.stall.description}</p>}
              {menu.stall.opening_hours && <p className="mt-2 text-xs text-slate-500">Opening hours: {menu.stall.opening_hours}</p>}
              <div className="mt-4 overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead className="text-xs text-slate-500">
                    <tr><th className="pb-2 font-medium">Item</th><th className="pb-2 font-medium">Category</th><th className="pb-2 font-medium">Price</th><th className="pb-2 font-medium">Availability</th></tr>
                  </thead>
                  <tbody className="divide-y divide-slate-800">
                    {menu.items.map(item => (
                      <tr key={item.id}>
                        <td className="py-3 pr-3">
                          <p className="font-medium text-slate-200">{item.item}</p>
                          {item.description && <p className="mt-1 text-xs text-slate-500">{item.description}</p>}
                          {(item.dietary || item.dietary_note) && <p className="mt-1 text-xs text-slate-500">{[item.dietary?.replace(/_/g, ' '), item.dietary_note].filter(Boolean).join(' · ')}</p>}
                        </td>
                        <td className="py-3 pr-3 text-slate-400">{categoryLabel(item.category)}</td>
                        <td className="whitespace-nowrap py-3 pr-3 font-semibold text-emerald-300">₹{Number(item.price).toFixed(2)}</td>
                        <td className={`whitespace-nowrap py-3 ${item.available ? 'text-emerald-300' : 'text-amber-300'}`}>{item.available ? 'Available' : 'Unavailable'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {menu.stall.room_code && (
                <Link to={`/navigator?target=${encodeURIComponent(menu.stall.room_code)}`} className="btn-secondary mt-3 inline-flex items-center gap-2">
                  <MapPin size={14} />Navigate to {menu.stall.room_code}
                </Link>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
};
