"use client";
import Link from "next/link";
import { Fragment, useMemo, useState, type ReactNode } from "react";
import { Badge, Button, Card, Icon, PageHeader, cx } from "@/components/ui";
import { bookChapters, glossary, questionById, sourceById } from "@/lib/content";
import { addHighlight, removeHighlight, setNote, toggleBookmark } from "@/lib/store/state";
import { update, useAcademy } from "@/lib/store/storage";

/** Wraps highlights and glossary terms inside a paragraph (plain text in, React nodes out). */
function renderParagraph(text: string, highlights: string[], terms: string[]): ReactNode {
  const marks = [...highlights.filter((h) => text.includes(h)).map((h) => ({ t: h, kind: "hl" as const })), ...terms.filter((t) => text.includes(t)).map((t) => ({ t, kind: "term" as const }))];
  if (!marks.length) return text;
  const pattern = new RegExp(`(${marks.map((m) => m.t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "g");
  return text.split(pattern).map((part, i) => {
    const m = marks.find((x) => x.t === part);
    if (!m) return <Fragment key={i}>{part}</Fragment>;
    return m.kind === "hl" ? <mark key={i} className="hl">{part}</mark> : <span key={i} className="underline decoration-accent/50 decoration-dotted underline-offset-4" title={glossary.find((g) => g.term === part)?.definition}>{part}</span>;
  });
}

export default function BookPage() {
  const s = useAcademy();
  const chapters = useMemo(() => bookChapters(), []);
  const [q, setQ] = useState("");
  const [onlyMarked, setOnlyMarked] = useState(false);
  const [open, setOpen] = useState<string | null>(s.reader.lastChapter ?? chapters[0]?.key ?? null);
  const [tab, setTab] = useState<"read" | "glossary" | "sources">("read");
  const terms = useMemo(() => glossary.map((g) => g.term).sort((a, b) => b.length - a.length), []);
  const filtered = chapters.filter((c) => {
    if (onlyMarked && !s.reader.bookmarks.includes(c.key)) return false;
    if (!q.trim()) return true;
    const t = q.toLowerCase();
    return (c.title + " " + c.paragraphs.join(" ") + " " + (s.reader.notes[c.key] ?? "")).toLowerCase().includes(t);
  });
  const ch = chapters.find((c) => c.key === open);
  const allSources = [...new Set(chapters.flatMap((c) => c.sourceIds))];

  return (
    <div className="page-enter">
      <PageHeader eyebrow="Digitales Kursbuch" title="Das Setter-Handbuch">
        {chapters.length} Kapitel aus den verfügbaren Modulen · mit Lesezeichen, Notizen, Markierungen, Suche, Glossar und Quellen.
      </PageHeader>
      <div className="mb-4 flex gap-1 overflow-x-auto rounded-[var(--radius-sm)] border border-line p-1" role="tablist">
        {([["read", "Lesen"], ["glossary", `Fachbegriffe (${glossary.length})`], ["sources", "Quellenverzeichnis"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={cx("min-h-10 shrink-0 rounded-lg px-4 text-sm", tab === k ? "bg-surface-strong text-fg" : "text-muted")}>{l}</button>
        ))}
      </div>

      {tab === "glossary" && (
        <Card>
          <dl className="grid gap-3 sm:grid-cols-2">
            {glossary.map((g) => (
              <div key={g.term} className="rounded-[var(--radius-sm)] border border-line p-3">
                <dt className="font-semibold">{g.term}</dt>
                <dd className="mt-1 text-sm text-muted">{g.definition}</dd>
                <dd className="mt-1 text-xs"><Link className="text-accent hover:underline" href={`/learn/${g.lessonId.slice(0, 3)}/${g.lessonId}/`}>Zur Lektion</Link></dd>
              </div>
            ))}
          </dl>
        </Card>
      )}

      {tab === "sources" && (
        <Card>
          <ul className="grid gap-2 text-sm">
            {allSources.map((id) => {
              const src = sourceById(id);
              return src ? <li key={id}><span className="text-faint">{id}</span> · {src.authorOrPublisher}: <span className="italic">{src.title}</span> {src.publishedAt && `(${src.publishedAt})`} · <span className="text-xs text-faint">{src.verification.replace("_", " ")}</span></li> : null;
            })}
          </ul>
          <Link href="/sources/" className="mt-4 inline-block text-sm text-accent hover:underline">Vollständige Quellenbibliothek mit Prüfstatus</Link>
        </Card>
      )}

      {tab === "read" && (
        <div className="grid gap-4 lg:grid-cols-[300px_1fr]">
          <aside className="grid content-start gap-3">
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Im Kursbuch suchen …" aria-label="Im Kursbuch suchen" className="min-h-12 rounded-[var(--radius-sm)] border border-line bg-surface px-3" />
            <label className="flex items-center gap-2 text-sm text-muted"><input type="checkbox" checked={onlyMarked} onChange={(e) => setOnlyMarked(e.target.checked)} className="h-5 w-5 accent-[var(--accent-solid)]" /> Nur Lesezeichen</label>
            <ol className="grid max-h-[60dvh] gap-1 overflow-y-auto">
              {filtered.map((c) => (
                <li key={c.key}>
                  <button onClick={() => { setOpen(c.key); update((x) => ({ ...x, reader: { ...x.reader, lastChapter: c.key } })); }} className={cx("w-full rounded-lg px-3 py-2 text-left text-sm", open === c.key ? "bg-surface-strong" : "hover:bg-surface")}>
                    <span className="block text-[11px] text-faint">{c.chapter} · {c.moduleTitle}{s.reader.bookmarks.includes(c.key) && " · ★"}{s.reader.notes[c.key] && " · Notiz"}</span>
                    {c.title}
                  </button>
                </li>
              ))}
              {filtered.length === 0 && <li className="px-3 text-sm text-muted">Keine Treffer.</li>}
            </ol>
          </aside>
          {ch && (
            <article className="rounded-[var(--radius)] border border-line bg-elev px-5 py-6 sm:px-10 sm:py-10">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.14em] text-accent-2">{ch.chapter} · {ch.moduleTitle}</p>
                  <h2 className="font-serif-book mt-1 text-3xl font-medium">{ch.title}</h2>
                </div>
                <Button variant="secondary" className="min-h-10" onClick={() => update((x) => toggleBookmark(x, ch.key))} aria-pressed={s.reader.bookmarks.includes(ch.key)}>
                  {s.reader.bookmarks.includes(ch.key) ? "★ Lesezeichen" : "☆ Lesezeichen"}
                </Button>
              </div>
              <div className="reader-text mt-6 grid gap-5" onMouseUp={() => undefined}>
                {ch.paragraphs.map((p, i) => <p key={i}>{renderParagraph(p, s.reader.highlights[ch.key] ?? [], terms)}</p>)}
              </div>
              <div className="mt-6 flex flex-wrap items-center gap-2">
                <Button variant="secondary" className="min-h-10" onClick={() => { const t = window.getSelection()?.toString() ?? ""; update((x) => addHighlight(x, ch.key, t)); }}>Markierten Text hervorheben</Button>
                <span className="text-xs text-faint">Text auswählen, dann tippen. Gepunktet unterstrichen = Fachbegriff (Glossar).</span>
              </div>
              {(s.reader.highlights[ch.key] ?? []).length > 0 && (
                <ul className="mt-3 flex flex-wrap gap-2">{(s.reader.highlights[ch.key] ?? []).map((h) => <li key={h}><button onClick={() => update((x) => removeHighlight(x, ch.key, h))} className="rounded-full border border-line px-2 py-0.5 text-xs text-muted hover:border-danger" title="Markierung entfernen">„{h.slice(0, 40)}{h.length > 40 ? "…" : ""}“ ✕</button></li>)}</ul>
              )}
              <label className="mt-6 grid gap-1.5 text-sm font-medium">
                Deine Notizen
                <textarea defaultValue={s.reader.notes[ch.key] ?? ""} key={ch.key} onBlur={(e) => update((x) => setNote(x, ch.key, e.target.value))} rows={4} className="rounded-[var(--radius-sm)] border border-line bg-bg p-3 text-base font-normal" placeholder="Wird beim Verlassen des Feldes gespeichert." />
              </label>
              <div className="mt-6 grid gap-3 border-t border-line pt-5 sm:grid-cols-2">
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Zum Üben</p>
                  <ul className="grid gap-1 text-sm">
                    <li><Link className="text-accent hover:underline" href={`/learn/${ch.moduleId}/${ch.lessonId}/`}>Lektion „{ch.lessonTitle}“ mit Übungen</Link></li>
                    {ch.checks.length > 0 && <li><Link className="text-accent hover:underline" href={`/review/?focus=${ch.checks.join(",")}`}>{ch.checks.length} Übungsfragen zu diesem Kapitel</Link></li>}
                    {ch.skills.map((k) => <li key={k} className="text-muted"><Icon name="spark" className="mr-1 inline h-3.5 w-3.5" />Skill-Karte: {k}</li>)}
                  </ul>
                </div>
                <div>
                  <p className="mb-1 text-xs font-semibold uppercase tracking-wider text-faint">Quellen</p>
                  <ul className="grid gap-1 text-xs text-muted">{ch.sourceIds.map((id) => <li key={id}>{sourceById(id)?.title ?? id}</li>)}</ul>
                </div>
              </div>
              {ch.checks[0] && questionById(ch.checks[0]) && <p className="mt-4"><Badge tone="accent">Tipp</Badge> <span className="text-sm text-muted">Erst lesen, dann die Fragen ohne Nachsehen beantworten – Abrufen festigt stärker als Wiederlesen.</span></p>}
            </article>
          )}
        </div>
      )}
    </div>
  );
}
