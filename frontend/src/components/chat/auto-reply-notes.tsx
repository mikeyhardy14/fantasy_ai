"use client";

import { useEffect, useState } from "react";

export function AutoReplyNotes({
  people,
  onSave,
}: {
  people: { userId: string; name: string; note: string }[];
  onSave: (userId: string, note: string) => void;
}) {
  if (!people.length) {
    return (
      <p className="mt-3 text-xs text-slate-500">Check Auto next to a manager, then add how the assistant should talk to them.</p>
    );
  }
  return (
    <ul className="mt-4 space-y-3">
      {people.map((person) => (
        <NoteRow key={person.userId} person={person} onSave={onSave} />
      ))}
    </ul>
  );
}

function NoteRow({
  person,
  onSave,
}: {
  person: { userId: string; name: string; note: string };
  onSave: (userId: string, note: string) => void;
}) {
  const [value, setValue] = useState(person.note);
  useEffect(() => setValue(person.note), [person.note]);
  return (
    <li>
      <label className="block text-xs text-slate-400" htmlFor={`auto-note-${person.userId}`}>
        How to talk to {person.name}
      </label>
      <textarea
        id={`auto-note-${person.userId}`}
        value={value}
        maxLength={1000}
        rows={3}
        placeholder="Casual, short messages. Don't bring up trades."
        className="mt-1 w-full resize-y rounded-lg border border-surface-border bg-surface px-3 py-2 text-sm text-slate-100 placeholder:text-slate-500 focus:border-brand focus:outline-none focus:ring-1 focus:ring-brand"
        onChange={(event) => setValue(event.target.value)}
        onBlur={() => {
          const next = value.trim();
          if (next !== person.note) onSave(person.userId, next);
        }}
      />
    </li>
  );
}
