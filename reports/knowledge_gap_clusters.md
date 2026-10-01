# Knowledge gap clusters (development golden, analysis only)

57 answer options with **no** sufficiently similar claim in the knowledge base. These are knowledge gaps, not matching problems. They are grouped so that whole law sections can be added systematically from the official text, **not** question by question. Only ids and single terms are listed. This report is not read by the engine.

## By gap type

| Gap type | Count |
|---|---|
| missing_statement | 36 |
| missing_concept | 16 |
| missing_numeric_condition | 4 |
| missing_exception | 2 |
| missing_relation | 1 |

## By topic

| Topic | Count |
|---|---|
| 05_priority | 11 |
| 09_manoeuvres | 9 |
| 06_signs | 8 |
| 13_vehicle_technology | 6 |
| 11_special | 5 |
| 07_road_users | 5 |
| 10_parking | 3 |
| 02_human_risk | 3 |
| 08_speed_distance | 3 |
| 12_learning | 2 |
| 14_trailers | 1 |
| 01_personal | 1 |

## By law section (closest official norm)

| Law section | Count | Topics | Gap types | Terms missing in the KB | Items |
|---|---|---|---|---|---|
| keine Norm eindeutig | 28 | 01_personal, 05_priority, 06_signs, 07_road_users, 08_speed_distance, 09_manoeuvres, 10_parking, 11_special, 13_vehicle_technology, 14_trailers | missing_statement 15, missing_concept 10, missing_numeric_condition 3, missing_exception 1, missing_relation 1 | normal, gleichermass, tage, genau, cexpectx, zeichen, blick, innenspiegel | G029#3, G034#3, G039#1, G039#2, G042#2, G046#1, G051#3, G056#3 … |
| FeV/StVG/BKatV (kein amtlicher Text) | 5 | 02_human_risk, 12_learning | missing_statement 3, missing_concept 2 | langer, besser, konzentratio | G073#3, H076#1, H076#2, H078#1, H078#2 |
| stvo_2013 § 11 | 2 | 05_priority | missing_statement 2 | - | G024#1, G024#2 |
| stvo_2013 Anlage 2 Nr. 16 | 2 | 07_road_users, 11_special | missing_statement 1, missing_concept 1 | erledig | G068#2, H055#2 |
| stvo_2013 § 20 | 2 | 05_priority | missing_statement 2 | - | H018#1, H018#2 |
| stvo_2013 § 8 | 1 | 05_priority | missing_statement 1 | - | G011#2 |
| stvo_2013 Anlage 2 Nr. 2.2 | 1 | 05_priority | missing_concept 1 | herausfahr | G012#3 |
| stvo_2013 § 37 | 1 | 05_priority | missing_statement 1 | - | G017#3 |
| stvo_2013 Anlage 2 Nr. 3 | 1 | 06_signs | missing_concept 1 | trotzd | G028#1 |
| stvo_2013 Anlage 2 Nr. 50 | 1 | 06_signs | missing_numeric_condition 1 | - | G029#1 |
| stvo_2013 Anlage 2 Nr. 53 | 1 | 06_signs | missing_statement 1 | - | G033#3 |
| stvo_2013 Anlage 2 Nr. 69 | 1 | 06_signs | missing_statement 1 | - | G037#2 |
| stvo_2013 Anlage 3 Nr. 38 | 1 | 09_manoeuvres | missing_statement 1 | - | G038#1 |
| stvo_2013 § 7 | 1 | 09_manoeuvres | missing_statement 1 | - | G042#1 |
| stvo_2013 § 15a | 1 | 11_special | missing_statement 1 | - | G056#1 |
| stvo_2013 § 22 | 1 | 13_vehicle_technology | missing_concept 1 | ladungsend | G060#1 |
| stvo_2013 Anlage 1 Nr. 2 | 1 | 05_priority | missing_statement 1 | - | H009#1 |
| stvo_2013 Anlage 2 Nr. 54.4 | 1 | 06_signs | missing_statement 1 | - | H034#2 |
| stvo_2013 § 6 | 1 | 09_manoeuvres | missing_statement 1 | - | H039#2 |
| stvo_2013 § 34 | 1 | 11_special | missing_statement 1 | - | H052#1 |
| ekfv § 12 | 1 | 11_special | missing_statement 1 | - | H052#2 |
| stvo_2013 § 17 | 1 | 13_vehicle_technology | missing_statement 1 | - | H057#1 |
| stvo_2013 § 21a | 1 | 07_road_users | missing_exception 1 | - | H069#1 |

## Recommended systematic steps

1. For every law section above, check the whole section of the official text for statements without a claim, not only the listed items.
2. `missing_relation`: add the action concept and its contradictions to the lexicon / contradiction index (valid only if the law text supports it).
3. `missing_numeric_rule` / `missing_numeric_condition`: add the numeric rule with its conditions (numeric condition model).
4. `FeV/StVG/BKatV`: only after a manual official-source import (`knowledge/sources/manual/`).
