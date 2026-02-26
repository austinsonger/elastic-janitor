# Elastic Janitor CLI - Implementation Plan

**Concrete action plan for completing CLI command coverage**

---

## Current Status

- ✅ **Implemented:** 28 commands (24.8%)
- ⬜ **Remaining:** 85 commands (75.2%)
- 🎯 **Target:** 113 commands (100%)

---

## Week 1: Snapshot Commands (CRITICAL)

### File to Create: `janitor/cli/commands/snapshot.py`

### Commands to Implement (11):

```python
@click.group()
def snapshot():
    """Snapshot and backup management commands."""
    pass

# 1. snapshot list
@snapshot.command()
@click.option('--repository', '-r', help='Repository name')
@click.option('--pattern', '-p', default='*', help='Snapshot pattern')
@common_options
@handle_errors
@pass_es_client
def list(es, repository, pattern, output, verbose, quiet):
    """List snapshots in repository."""
    from ...operations.snapshots import option_list_snapshots
    option_list_snapshots(es)

# 2. snapshot delete
@snapshot.command()
@click.option('--repository', '-r', required=True, help='Repository name')
@click.option('--snapshot', '-s', help='Snapshot name or pattern')
@click.option('--older-than', '-o', help='Delete older than (e.g., 30d)')
@dry_run_option
@common_options
@handle_errors
@pass_es_client
def delete(es, repository, snapshot, older_than, dry_run, output, verbose, quiet):
    """Delete old snapshots."""
    from ...operations.snapshots import option_delete_old_snapshots
    option_delete_old_snapshots(es)

# 3. snapshot restore
@snapshot.command()
@click.option('--repository', '-r', required=True, help='Repository name')
@click.option('--snapshot', '-s', required=True, help='Snapshot name')
@click.option('--indices', '-i', help='Indices to restore (comma-separated)')
@click.option('--rename-pattern', help='Rename pattern')
@click.option('--rename-replacement', help='Rename replacement')
@dry_run_option
@common_options
@handle_errors
@pass_es_client
def restore(es, repository, snapshot, indices, rename_pattern, rename_replacement, dry_run, output, verbose, quiet):
    """Restore snapshot with wizard."""
    from ...operations.snapshots import option_restore_wizard
    option_restore_wizard(es)

# 4-11. Additional snapshot commands...
# - analyze, cleanup, compare, copy, repo list, verify, slm list, slm delete
```

### Operations to Wrap:
- `janitor/operations/snapshots.py`:
  - `option_list_snapshots()`
  - `option_delete_old_snapshots()`
  - `option_analyze_snapshot_sizes()`
  - `option_automated_snapshot_cleanup()`
  - `option_compare_snapshots()`
  - `option_cross_repository_copy()`
  - `option_restore_wizard()`
  - `option_list_repositories()`
  - `option_verify_repository()`
  - `option_list_slm_policies()`
  - `option_delete_slm_policy()`

### Testing Checklist:
- [ ] Create test snapshot repository
- [ ] Test snapshot list with various filters
- [ ] Test snapshot delete with dry-run
- [ ] Test snapshot restore wizard
- [ ] Test all output formats (JSON, Table, YAML, CSV)
- [ ] Test error handling (invalid repository, missing snapshot)
- [ ] Update documentation

### Estimated Effort: 3-4 days

---

## Week 2: Pipeline Commands (CRITICAL)

### File to Create: `janitor/cli/commands/pipeline.py`

### Commands to Implement (11):

```python
@click.group()
def pipeline():
    """Ingest pipeline management commands."""
    pass

# 1. pipeline list
@pipeline.command()
@click.option('--pattern', '-p', default='*', help='Pipeline pattern')
@common_options
@handle_errors
@pass_es_client
def list(es, pattern, output, verbose, quiet):
    """List ingest pipelines."""
    from ...operations.pipeline_management import option_list_pipelines
    option_list_pipelines(es)

# 2. pipeline view
@pipeline.command()
@click.argument('name')
@click.option('--show-processors', is_flag=True, help='Show processor details')
@common_options
@handle_errors
@pass_es_client
def view(es, name, show_processors, output, verbose, quiet):
    """View pipeline details."""
    from ...operations.pipeline_management import option_view_pipeline
    option_view_pipeline(es)

# 3. pipeline edit
@pipeline.command()
@click.argument('name')
@click.option('--description', '-d', help='Pipeline description')
@click.option('--processors', '-p', help='Processors JSON')
@click.option('--version', '-v', help='Version message')
@dry_run_option
@common_options
@handle_errors
@pass_es_client
def edit(es, name, description, processors, version, dry_run, output, verbose, quiet):
    """Edit pipeline with version control."""
    from ...operations.pipeline_management import option_edit_pipeline
    option_edit_pipeline(es)

# 4-11. Additional pipeline commands...
# - delete, clone, export, import, history, rollback, emergency-rollback
```

### Operations to Wrap:
- `janitor/operations/pipeline_management.py`:
  - `option_list_pipelines()`
  - `option_view_pipeline()`
  - `option_edit_pipeline()`
  - `option_delete_pipeline()`
  - `option_clone_pipeline()`
  - `option_export_pipelines()`
  - `option_import_pipelines()`
  - `option_version_history()`
  - `option_rollback_pipeline()`
  - `option_emergency_rollback()`

### Testing Checklist:
- [ ] Create test pipeline
- [ ] Test pipeline list and view
- [ ] Test pipeline edit with version control
- [ ] Test pipeline clone and export/import
- [ ] Test rollback functionality
- [ ] Test all output formats
- [ ] Test error handling
- [ ] Update documentation

### Estimated Effort: 3-4 days

---

## Week 3-4: Template Commands (CRITICAL)

### File to Expand: `janitor/cli/commands/template.py`

### Commands to Add (12 new, 2 existing):

**Index Templates (7):**
1. `template index list`
2. `template index view`
3. `template index edit`
4. `template index delete`
5. `template index export`
6. `template index import`
7. `template index rollback`

**Component Templates (7):**
8. `template component list`
9. `template component view`
10. `template component edit`
11. `template component delete`
12. `template component export`
13. `template component import`
14. `template component rollback`

### Operations to Wrap:
- `janitor/operations/template_management.py`
- `janitor/operations/templates_index.py`

### Testing Checklist:
- [ ] Test template CRUD operations
- [ ] Test version control
- [ ] Test export/import
- [ ] Test rollback
- [ ] Test dependency tracking
- [ ] Update documentation

### Estimated Effort: 6-8 days

---

## Registration in Main CLI

### Update: `janitor/cli/main.py`

```python
from .commands.snapshot import snapshot
from .commands.pipeline import pipeline

# Register new command groups
cli.add_command(snapshot)
cli.add_command(pipeline)
```

---

## Testing Strategy

### Unit Tests
Create test files:
- `tests/cli/test_snapshot_commands.py`
- `tests/cli/test_pipeline_commands.py`
- `tests/cli/test_template_commands.py`

### Integration Tests
- Test against real Elasticsearch cluster
- Test dry-run mode
- Test all output formats
- Test error scenarios

### CI/CD Pipeline
```yaml
# .github/workflows/cli-tests.yml
name: CLI Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
      - name: Install dependencies
        run: pip install -e .[dev]
      - name: Run CLI tests
        run: pytest tests/cli/
```

---

## Documentation Updates

### Files to Update:
1. `docs/CLI_COMMAND_LIBRARY.md` - Add implementation notes
2. `docs/CLI_USAGE.md` - Add new examples
3. `README.md` - Update command count
4. `CHANGELOG.md` - Document new features

---

## Success Metrics

### Week 1 Target:
- ✅ 11 snapshot commands implemented
- ✅ Coverage: 35% (39/113)
- ✅ All tests passing
- ✅ Documentation updated

### Week 2 Target:
- ✅ 11 pipeline commands implemented
- ✅ Coverage: 44% (50/113)
- ✅ All tests passing
- ✅ Documentation updated

### Week 3-4 Target:
- ✅ 12 template commands implemented
- ✅ Coverage: 55% (62/113)
- ✅ All tests passing
- ✅ Documentation updated

---

## Next Steps

1. **Review this plan** - Get approval from stakeholders
2. **Set up development environment** - Ensure Elasticsearch cluster available
3. **Create feature branch** - `feature/cli-phase-1-critical-commands`
4. **Begin Week 1 implementation** - Snapshot commands
5. **Daily standups** - Track progress and blockers

---

**Start Date:** TBD  
**Target Completion:** 4 weeks from start  
**Owner:** TBD

