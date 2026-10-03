# Builds the day plans for stages 2–7 of content/program.json from the modules that actually exist.
# A stage becomes "available" only when ALL its modules have content – no empty days, no placeholders.
# Rhythm per module (5 days): 4 days × 2 lessons (+ review on alternate days), then quiz + simulation (+ transfer).
# Remaining days of a stage: mixed review + rotating simulations; last day: stage check.
# Stage 7 (days 78–90) is pure consolidation across all modules and opens only when M01–M12 exist.
import json, glob, os
R = lambda p: json.load(open(p))
prog = R("content/program.json")
mods = {os.path.basename(p)[:-5]: R(p) for p in glob.glob("content/modules/M*.json")}
scen = [R(p) for p in sorted(glob.glob("content/scenarios/SIM-*.json"))]
def scen_module(s):
    links = (s.get("ai") or {}).get("lessonLinks") or []
    return links[0].split("-")[0] if links else None
mod_scen = {}
for s in scen:
    m = scen_module(s)
    if m: mod_scen.setdefault(m, []).append(s["id"])
ALL = [f"M{i:02d}" for i in range(1, 13)]

def spread(ids, n):
    if len(ids) <= n: return list(ids)
    step = len(ids) / n
    return [ids[int(i * step)] for i in range(n)]

def module_days(mid):
    m = mods[mid]; L = [l for l in m["lessons"]]
    days = []
    for i in range(0, len(L), 2):
        chunk = L[i:i + 2]
        items = [{"type": "lesson", "ref": l["id"]} for l in chunk]
        if (i // 2) % 2 == 1: items.append({"type": "review"})
        days.append({"title": " · ".join(l["title"] for l in chunk), "items": items})
    last = [{"type": "quiz", "ref": mid}]
    for sid in mod_scen.get(mid, [])[:1]: last.append({"type": "simulation", "ref": sid})
    last.append({"type": "review"})
    if m.get("transferTask"): last.append({"type": "transfer", "ref": mid, "optional": True})
    days.append({"title": f"Modulquiz {m['number']}: {m['title']}", "items": last})
    return days

for st in prog:
    if st["id"] == "ST1": continue
    need = ALL if st["id"] == "ST7" else st["moduleIds"]
    if not all(m in mods for m in need):
        st["available"] = False; st["days"] = []
        continue
    n = st["dayTo"] - st["dayFrom"] + 1
    plan = [] if st["id"] == "ST7" else [d for m in st["moduleIds"] for d in module_days(m)]
    pool = [s for m in (need if st["id"] != "ST7" else ALL) for s in mod_scen.get(m, [])] or [s["id"] for s in scen]
    quiz_cycle = ALL[:]  # stage 7 re-checks one module per day
    k = 0
    while len(plan) < n - 1:
        items = [{"type": "review"}, {"type": "simulation", "ref": pool[k % len(pool)]}]
        title = "Gemischte Wiederholung und Praxis"
        if st["id"] == "ST7":
            mid = quiz_cycle[k % len(quiz_cycle)]
            items.append({"type": "quiz", "ref": mid, "fresh": True})
            title = f"Festigen: {mods[mid]['title']}"
        plan.append({"title": title, "items": items}); k += 1
    if len(plan) > n - 1: raise SystemExit(f"{st['id']}: {len(plan)} Tage Inhalt für {n} Tage")
    plan.append({"title": f"Stufen-Check {st['number']}", "items": [{"type": "review"}, {"type": "quiz", "ref": st["id"]}]})
    st["days"] = [{"day": st["dayFrom"] + i, **d} for i, d in enumerate(plan)]
    per = 2 if st["id"] == "ST7" else 12
    qids = [q for m in need for q in spread(mods[m]["examQuestionIds"], per)]
    sims = [s for m in (st["moduleIds"] if st["id"] != "ST7" else []) for s in mod_scen.get(m, [])[:1]]
    if st["id"] == "ST7": sims = pool[-2:]
    st["check"] = {"id": st["id"], "title": f"Stufen-Check {st['number']}: {st['title']}", "questionIds": qids, "passThreshold": 0.8, "requiredSimulations": sims}
    st["available"] = True
    if st["id"] == "ST7": st["moduleIds"] = []  # consolidation stage: no new lessons
open("content/program.json", "w").write(json.dumps(prog, ensure_ascii=False, indent=2) + "\n")
print([(s["id"], s["available"], len(s["days"])) for s in prog])
