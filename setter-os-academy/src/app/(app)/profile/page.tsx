"use client";
import { useState } from "react";
import { Badge, Button, Card, PageHeader, Stat } from "@/components/ui";
import { ACHIEVEMENTS } from "@/lib/engine/gamification";
import { overview } from "@/lib/derived";
import { update, useAcademy } from "@/lib/store/storage";

export default function Profile() {
  const s = useAcademy();
  const p = s.profile!;
  const o = overview(s, Date.now());
  const [name, setName] = useState(p.displayName);
  const [saved, setSaved] = useState(false);
  return (
    <div className="fade-in">
      <PageHeader eyebrow="Profil" title={p.displayName}>Lokales Profil · angelegt am {new Date(p.createdAt).toLocaleDateString("de-DE")}</PageHeader>
      <div className="grid gap-4 lg:grid-cols-3">
        <Card>
          <label className="grid gap-1.5 text-sm font-medium">
            Anzeigename
            <input value={name} maxLength={40} onChange={(e) => { setName(e.target.value); setSaved(false); }} className="min-h-12 rounded-[var(--radius-sm)] border border-line bg-surface px-3 text-base font-normal" />
          </label>
          <Button className="mt-3" disabled={!name.trim()} onClick={() => { update((st) => ({ ...st, profile: { ...st.profile!, displayName: name.trim().slice(0, 40) } })); setSaved(true); }}>Speichern</Button>
          {saved && <p role="status" className="mt-2 text-sm text-success">Gespeichert.</p>}
          <dl className="mt-5 grid gap-1 text-xs text-faint">
            <div>Sprache: Deutsch (Englisch/Spanisch technisch vorbereitet)</div>
            <div>Datenschutzhinweis: Version {p.privacyNoticeVersion}, bestätigt {new Date(p.privacyNoticeAcceptedAt).toLocaleDateString("de-DE")}</div>
          </dl>
        </Card>
        <div className="grid grid-cols-2 content-start gap-3 lg:col-span-2">
          <Stat label="Level" value={o.level.level} hint={o.level.title} />
          <Stat label="XP" value={o.xp} hint="Aktivität, nicht Kompetenz" />
          <Stat label="Lektionen" value={Object.keys(s.lessonsCompleted).length} />
          <Stat label="Erfolge" value={`${Object.keys(s.achievements).length}/${ACHIEVEMENTS.length}`} />
          <Card className="col-span-2">
            <h2 className="mb-2 font-semibold">Ranglisten</h2>
            <p className="text-sm text-muted">Ranglisten sind freiwillig (Opt-in) und erst mit Cloud-Konten möglich. Im Prototyp gibt es keine.</p>
            <Badge className="mt-2">nicht aktiv</Badge>
          </Card>
        </div>
      </div>
    </div>
  );
}
