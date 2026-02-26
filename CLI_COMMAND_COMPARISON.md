# Elastic Janitor CLI - Command Comparison Matrix

**Visual comparison of documented vs implemented commands**

Legend: ✅ Implemented | ❌ Not Implemented | 📝 Documented

---

## Cluster Commands (3/3 - 100% ✅)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `cluster health` | 📝 | ✅ | cluster.py | Complete |
| `cluster nodes` | 📝 | ✅ | cluster.py | Complete |
| `cluster stats` | 📝 | ✅ | cluster.py | Complete |

---

## Dry-Run Commands (3/3 - 100% ✅)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `dry-run enable` | 📝 | ✅ | dryrun.py | Complete |
| `dry-run disable` | 📝 | ✅ | dryrun.py | Complete |
| `dry-run status` | 📝 | ✅ | dryrun.py | Complete |

---

## Index Commands (3/9 - 33% ⚠️)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `index health` | 📝 | ✅ | index.py | Complete |
| `index largest` | 📝 | ✅ | index.py | Complete |
| `index analyze-patterns` | 📝 | ✅ | index.py | Complete |
| `index shards` | 📝 | ❌ | - | **Missing** |
| `index settings` | 📝 | ❌ | - | **Missing** |
| `index duplicates` | 📝 | ❌ | - | **Missing** |
| `index alias` | 📝 | ❌ | - | **Missing** |
| `index rollover` | 📝 | ❌ | - | **Missing** |
| `index migrate` | 📝 | ❌ | - | **Missing** |
| `index optimize` | 📝 | ❌ | - | **Missing** |

---

## Data Stream Commands (2/8 - 25% ⚠️)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `datastream clean` | 📝 | ✅ | datastream.py | Complete |
| `datastream migrate` | 📝 | ✅ | datastream.py | Complete |
| `datastream preview` | 📝 | ❌ | - | **Missing** |
| `datastream stats` | 📝 | ❌ | - | **Missing** |
| `datastream lifecycle` | 📝 | ❌ | - | **Missing** |
| `datastream reindex` | 📝 | ❌ | - | **Missing** |
| `datastream clone` | 📝 | ❌ | - | **Missing** |
| `datastream rotate` | 📝 | ❌ | - | **Missing** |
| `datastream clean-standalone` | 📝 | ❌ | - | **Missing** |

---

## Template Commands (2/14 - 14% ⚠️)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `template validate` | 📝 | ✅ | template.py | Complete |
| `template performance-impact` | 📝 | ✅ | template.py | Complete |
| `template index list` | 📝 | ❌ | - | **Missing** |
| `template index view` | 📝 | ❌ | - | **Missing** |
| `template index edit` | 📝 | ❌ | - | **Missing** |
| `template index delete` | 📝 | ❌ | - | **Missing** |
| `template index export` | 📝 | ❌ | - | **Missing** |
| `template index import` | 📝 | ❌ | - | **Missing** |
| `template index rollback` | 📝 | ❌ | - | **Missing** |
| `template component list` | 📝 | ❌ | - | **Missing** |
| `template component view` | 📝 | ❌ | - | **Missing** |
| `template component edit` | 📝 | ❌ | - | **Missing** |
| `template component delete` | 📝 | ❌ | - | **Missing** |
| `template component export` | 📝 | ❌ | - | **Missing** |
| `template component import` | 📝 | ❌ | - | **Missing** |
| `template component rollback` | 📝 | ❌ | - | **Missing** |
| `template conflicts` | 📝 | ❌ | - | **Missing** |
| `template dependencies` | 📝 | ❌ | - | **Missing** |
| `template inheritance` | 📝 | ❌ | - | **Missing** |
| `template unused` | 📝 | ❌ | - | **Missing** |
| `template rollback-deps` | 📝 | ❌ | - | **Missing** |

---

## Policy Commands (2/6 - 33% ⚠️)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `policy health-check` | 📝 | ✅ | policy.py | Complete |
| `policy alignment` | 📝 | ✅ | policy.py | Complete |
| `policy ilm list` | 📝 | ❌ | - | **Missing** |
| `policy ilm view` | 📝 | ❌ | - | **Missing** |
| `policy ilm assign` | 📝 | ❌ | - | **Missing** |
| `policy ilm delete` | 📝 | ❌ | - | **Missing** |
| `policy ilm simulate` | 📝 | ❌ | - | **Missing** |
| `policy ilm effectiveness` | 📝 | ❌ | - | **Missing** |

---

## Performance Commands (1/6 - 17% ⚠️)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `perf aggregations` | 📝 | ✅ | performance.py | Complete |
| `perf slow-queries` | 📝 | ❌ | - | **Missing** |
| `perf search` | 📝 | ❌ | - | **Missing** |
| `perf indexing` | 📝 | ❌ | - | **Missing** |
| `perf nodes` | 📝 | ❌ | - | **Missing** |
| `perf hotspots` | 📝 | ❌ | - | **Missing** |
| `perf timeline` | 📝 | ❌ | - | **Missing** |

---

## Governance Commands (6/6 - 100% ✅)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `governance schema-evolution` | 📝 | ✅ | governance.py | Complete |
| `governance data-lineage` | 📝 | ✅ | governance.py | Complete |
| `governance pii-detection` | 📝 | ✅ | governance.py | Complete |
| `governance data-quality` | 📝 | ✅ | governance.py | Complete |
| `governance metadata` | 📝 | ✅ | governance.py | Complete |
| `governance data-dictionary` | 📝 | ✅ | governance.py | Complete |

---

## Tuning Commands (6/6 - 100% ✅)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `tuning auto-tune` | 📝 | ✅ | tuning.py | Complete |
| `tuning shard-optimizer` | 📝 | ✅ | tuning.py | Complete |
| `tuning refresh-interval` | 📝 | ✅ | tuning.py | Complete |
| `tuning merge-policy` | 📝 | ✅ | tuning.py | Complete |
| `tuning cache` | 📝 | ✅ | tuning.py | Complete |
| `tuning jvm` | 📝 | ✅ | tuning.py | Complete |

---

## Snapshot Commands (0/15 - 0% ❌)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `snapshot list` | 📝 | ❌ | - | **CRITICAL MISSING** |
| `snapshot delete` | 📝 | ❌ | - | **CRITICAL MISSING** |
| `snapshot analyze` | 📝 | ❌ | - | **Missing** |
| `snapshot cleanup` | 📝 | ❌ | - | **Missing** |
| `snapshot compare` | 📝 | ❌ | - | **Missing** |
| `snapshot copy` | 📝 | ❌ | - | **Missing** |
| `snapshot restore` | 📝 | ❌ | - | **CRITICAL MISSING** |
| `snapshot repo list` | 📝 | ❌ | - | **Missing** |
| `snapshot verify` | 📝 | ❌ | - | **Missing** |
| `snapshot slm list` | 📝 | ❌ | - | **Missing** |
| `snapshot slm delete` | 📝 | ❌ | - | **Missing** |

---

## Storage Commands (0/6 - 0% ❌)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `storage forecast` | 📝 | ❌ | - | **HIGH PRIORITY** |
| `storage tiers` | 📝 | ❌ | - | **Missing** |
| `storage compression` | 📝 | ❌ | - | **Missing** |
| `storage cleanup-empty` | 📝 | ❌ | - | **Missing** |
| `storage sparse` | 📝 | ❌ | - | **Missing** |
| `storage cost` | 📝 | ❌ | - | **HIGH PRIORITY** |

---

## Bulk Commands (0/6 - 0% ❌)

| Command | Documented | Implemented | File | Status |
|---------|------------|-------------|------|--------|
| `bulk index` | 📝 | ❌ | - | **Missing** |
| `bulk schedule` | 📝 | ❌ | - | **Missing** |
| `bulk history` | 📝 | ❌ | - | **Missing** |
| `bulk rollback` | 📝 | ❌ | - | **Missing** |
| `bulk config export` | 📝 | ❌ | - | **Missing** |
| `bulk config import` | 📝 | ❌ | - | **Missing** |

---

**For detailed implementation plan, see:** [CLI_COVERAGE_AUDIT.md](CLI_COVERAGE_AUDIT.md)

