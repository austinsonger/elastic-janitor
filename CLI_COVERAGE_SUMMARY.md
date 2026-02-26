# Elastic Janitor CLI - Coverage Summary

**Quick Reference** | [Full Audit Report](CLI_COVERAGE_AUDIT.md)

---

## Overall Coverage

| Metric | Value |
|--------|-------|
| **Total Documented Commands** | 113 |
| **Total Implemented Commands** | 28 |
| **Overall Coverage** | 24.8% |
| **Missing Commands** | 85 |

---

## Coverage by Category

| Category | Implemented | Documented | Coverage | Priority | Status |
|----------|-------------|------------|----------|----------|--------|
| **Cluster** | 3 | 3 | 100% | ✅ | Complete |
| **Dry-Run** | 3 | 3 | 100% | ✅ | Complete |
| **Governance** | 6 | 6 | 100% | ✅ | Complete |
| **Tuning** | 6 | 6 | 100% | ✅ | Complete |
| **Policy** | 2 | 6 | 33% | High | Partial |
| **Index** | 3 | 9 | 33% | High | Partial |
| **Data Stream** | 2 | 8 | 25% | High | Partial |
| **Performance** | 1 | 6 | 17% | Medium | Partial |
| **Template** | 2 | 14 | 14% | Critical | Partial |
| **Snapshot** | 0 | 15 | 0% | Critical | Missing |
| **Pipeline** | 0 | 11 | 0% | Critical | Missing |
| **Storage** | 0 | 6 | 0% | High | Missing |
| **Bulk** | 0 | 6 | 0% | High | Missing |
| **Cleanup** | 0 | 6 | 0% | Medium | Missing |
| **Quality** | 0 | 5 | 0% | Medium | Missing |
| **AWS** | 0 | 6 | 0% | Low | Missing |
| **Dashboard** | 0 | 5 | 0% | Low | Missing |

---

## Implementation Roadmap

### Phase 1: Critical Commands (Weeks 1-4) - 40 commands

| Week | Category | Commands | File | Effort |
|------|----------|----------|------|--------|
| 1 | Snapshot | 11 | `snapshot.py` (new) | 3-4 days |
| 2 | Pipeline | 11 | `pipeline.py` (new) | 3-4 days |
| 3-4 | Template | 14 | `template.py` (expand) | 6-8 days |

**Phase 1 Target:** 60% coverage (68/113 commands)

### Phase 2: Important Commands (Weeks 5-8) - 29 commands

| Week | Category | Commands | File | Effort |
|------|----------|----------|------|--------|
| 5 | Storage | 6 | `storage.py` (new) | 2-3 days |
| 6 | Index | 7 | `index.py` (expand) | 2-3 days |
| 7 | Data Stream | 7 | `datastream.py` (expand) | 2-3 days |
| 8 | Bulk & Policy | 10 | `bulk.py` (new), `policy.py` (expand) | 3-4 days |

**Phase 2 Target:** 86% coverage (97/113 commands)

### Phase 3: Nice to Have (Weeks 9-11) - 22 commands

| Week | Category | Commands | File | Effort |
|------|----------|----------|------|--------|
| 9 | Performance | 6 | `performance.py` (expand) | 2-3 days |
| 10 | Cleanup & Quality | 11 | `cleanup.py` (new), `quality.py` (new) | 3-4 days |
| 11 | AWS & Dashboard | 11 | `aws.py` (new), `dashboard.py` (new) | 3-4 days |

**Phase 3 Target:** 100% coverage (113/113 commands)

---

## Top 10 Most Critical Missing Commands

| Rank | Command | Category | Reason | User Impact |
|------|---------|----------|--------|-------------|
| 1 | `snapshot list` | Snapshot | Backup visibility | Critical |
| 2 | `snapshot delete` | Snapshot | Backup management | Critical |
| 3 | `snapshot restore` | Snapshot | Disaster recovery | Critical |
| 4 | `pipeline list` | Pipeline | Config visibility | High |
| 5 | `pipeline edit` | Pipeline | Config management | High |
| 6 | `template index list` | Template | Standardization | High |
| 7 | `template index edit` | Template | Config management | High |
| 8 | `storage cost` | Storage | Cost optimization | High |
| 9 | `storage forecast` | Storage | Capacity planning | High |
| 10 | `bulk schedule` | Bulk | Automation | Medium |

---

## Files to Create/Modify

### New Files (9):
1. `janitor/cli/commands/snapshot.py` - 11 commands
2. `janitor/cli/commands/pipeline.py` - 11 commands
3. `janitor/cli/commands/storage.py` - 6 commands
4. `janitor/cli/commands/bulk.py` - 6 commands
5. `janitor/cli/commands/cleanup.py` - 6 commands
6. `janitor/cli/commands/quality.py` - 5 commands
7. `janitor/cli/commands/aws.py` - 6 commands
8. `janitor/cli/commands/dashboard.py` - 5 commands

### Files to Expand (5):
1. `janitor/cli/commands/template.py` - Add 12 commands (currently 2)
2. `janitor/cli/commands/index.py` - Add 6 commands (currently 3)
3. `janitor/cli/commands/datastream.py` - Add 6 commands (currently 2)
4. `janitor/cli/commands/policy.py` - Add 4 commands (currently 2)
5. `janitor/cli/commands/performance.py` - Add 5 commands (currently 1)

---

## Effort Estimate

| Phase | Duration | Commands | Developer Days |
|-------|----------|----------|----------------|
| Phase 1 | 4 weeks | 40 | 16-20 days |
| Phase 2 | 4 weeks | 29 | 12-16 days |
| Phase 3 | 3 weeks | 22 | 10-14 days |
| **Total** | **11 weeks** | **91** | **38-50 days** |

**Assumptions:**
- 1 full-time developer
- Operations functions work correctly
- Testing infrastructure in place
- No major blockers

---

## Quick Action Items

### Immediate (This Week):
1. ✅ Review audit report
2. ⬜ Approve implementation plan
3. ⬜ Allocate development resources
4. ⬜ Set up tracking board

### Short Term (Next 2 Weeks):
1. ⬜ Implement snapshot commands (Week 1)
2. ⬜ Implement pipeline commands (Week 2)
3. ⬜ Set up CI/CD pipeline
4. ⬜ Create unit test framework

### Medium Term (Next Quarter):
1. ⬜ Complete Phase 1 (Critical commands)
2. ⬜ Complete Phase 2 (Important commands)
3. ⬜ Update documentation
4. ⬜ Release v2.0 with full CLI coverage

---

## Success Criteria

### Coverage Milestones:
- ✅ **Current:** 24.8% (28/113 commands)
- ⬜ **Phase 1:** 60% (68/113 commands)
- ⬜ **Phase 2:** 86% (97/113 commands)
- ⬜ **Phase 3:** 100% (113/113 commands)

### Quality Metrics:
- ⬜ 100% unit test coverage
- ⬜ 100% documentation coverage
- ⬜ All output formats supported
- ⬜ Dry-run mode for all destructive operations

---

**For detailed analysis, see:** [CLI_COVERAGE_AUDIT.md](CLI_COVERAGE_AUDIT.md)

**Last Updated:** 2026-02-15

