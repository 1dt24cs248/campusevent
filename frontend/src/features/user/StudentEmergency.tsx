import React, { useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertCircle, Phone, Plus, Save, ShieldAlert, Trash2 } from 'lucide-react';
import api from '../../api/client';

interface EmergencyContact {
  id: string;
  name: string;
  relationship: string;
  phone_number: string;
}

const EMPTY_FORM = { name: '', relationship: '', phone_number: '' };

function maskPhone(phone: string): string {
  const digits = phone.replace(/\D/g, '');
  return `********${digits.slice(-3)}`;
}

export const StudentEmergency: React.FC = () => {
  const queryClient = useQueryClient();
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [status, setStatus] = useState('');
  const [error, setError] = useState('');

  const { data: contacts = [], isLoading } = useQuery<EmergencyContact[]>({
    queryKey: ['student-emergency-contacts'],
    queryFn: async () => (await api.get('/emergency-contacts')).data,
  });
  const saveMutation = useMutation({
    mutationFn: async () => editingId
      ? api.patch(`/emergency-contacts/${editingId}`, form)
      : api.post('/emergency-contacts', form),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['student-emergency-contacts'] });
      setForm(EMPTY_FORM);
      setEditingId(null);
      setError('');
    },
    onError: (requestError: any) => {
      setError(requestError?.response?.data?.detail || 'Could not save the emergency contact.');
    },
  });
  const deleteMutation = useMutation({
    mutationFn: async (contactId: string) => api.delete(`/emergency-contacts/${contactId}`),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ['student-emergency-contacts'] });
      setStatus('');
    },
    onError: (requestError: any) => {
      setError(requestError?.response?.data?.detail || 'Could not delete the emergency contact.');
    },
  });

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setError('');
    saveMutation.mutate();
  };

  const startEdit = (contact: EmergencyContact) => {
    setEditingId(contact.id);
    setForm({
      name: contact.name,
      relationship: contact.relationship,
      phone_number: contact.phone_number,
    });
  };

  return (
    <section className="card max-w-3xl space-y-6 p-6">
      <div>
        <h1 className="section-header">
          <ShieldAlert size={20} className="text-red-400" />
          Emergency Contacts & SOS
        </h1>
        <p className="mt-2 text-sm text-slate-400">
          Contacts are private to your account. SOS opens your device’s call or SMS app; you confirm the action there.
        </p>
      </div>

      {error && (
        <div role="alert" className="flex items-start gap-2 rounded-lg border border-red-700/40 bg-red-900/20 p-3 text-sm text-red-300">
          <AlertCircle size={16} className="mt-0.5" />{error}
        </div>
      )}
      {status && <p role="status" className="rounded-lg bg-amber-900/20 p-3 text-sm text-amber-200">{status}</p>}

      <form onSubmit={submit} className="grid gap-3 sm:grid-cols-3">
        <label className="text-xs text-slate-400">
          Name
          <input className="input-field mt-1" required maxLength={120} value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} />
        </label>
        <label className="text-xs text-slate-400">
          Relationship
          <input className="input-field mt-1" required maxLength={80} value={form.relationship} onChange={event => setForm({ ...form, relationship: event.target.value })} />
        </label>
        <label className="text-xs text-slate-400">
          Phone number
          <input className="input-field mt-1" required type="tel" maxLength={30} value={form.phone_number} onChange={event => setForm({ ...form, phone_number: event.target.value })} />
        </label>
        <div className="flex gap-2 sm:col-span-3">
          <button type="submit" className="btn-primary flex items-center gap-2" disabled={saveMutation.isPending}>
            {editingId ? <Save size={15} /> : <Plus size={15} />}
            {saveMutation.isPending ? 'Saving…' : editingId ? 'Save contact' : 'Add emergency contact'}
          </button>
          {editingId && (
            <button type="button" className="btn-secondary" onClick={() => { setEditingId(null); setForm(EMPTY_FORM); }}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <div className="space-y-3">
        <h2 className="text-sm font-semibold text-white">Your saved contacts</h2>
        {isLoading ? <p className="text-sm text-slate-500">Loading contacts…</p> : contacts.length === 0 ? (
          <p className="rounded-lg border border-slate-800 p-4 text-sm text-slate-500">No emergency contacts saved.</p>
        ) : contacts.map(contact => (
          <article key={contact.id} className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-700 bg-slate-800/50 p-4">
            <div>
              <p className="font-medium text-white">{contact.name} <span className="text-slate-400">· {contact.relationship}</span></p>
              <p className="mt-1 text-sm text-slate-400">{maskPhone(contact.phone_number)}</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <a
                href={`tel:${encodeURIComponent(contact.phone_number)}`}
                onClick={() => setStatus(`SOS activated for ${contact.name}. Your device will open the call action for confirmation.`)}
                className="btn-primary flex items-center gap-2"
              >
                <Phone size={14} />Call
              </a>
              <a
                href={`sms:${encodeURIComponent(contact.phone_number)}`}
                onClick={() => setStatus(`SOS activated for ${contact.name}. Your device will open the SMS action for confirmation; no message has been sent by the app.`)}
                className="btn-secondary flex items-center gap-2"
              >
                Send SMS
              </a>
              <button type="button" className="btn-secondary" onClick={() => startEdit(contact)}>Edit</button>
              <button type="button" className="btn-secondary text-red-300" disabled={deleteMutation.isPending} onClick={() => deleteMutation.mutate(contact.id)}>
                <Trash2 size={14} />Delete
              </button>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};
