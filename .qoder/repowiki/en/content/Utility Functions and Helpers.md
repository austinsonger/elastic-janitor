# Utility Functions and Helpers

<cite>
**Referenced Files in This Document**
- [__init__.py](file://janitor/utils/__init__.py)
- [helpers.py](file://janitor/utils/helpers.py)
- [formatters.py](file://janitor/utils/formatters.py)
- [ui.py](file://janitor/utils/ui.py)
- [history_logger.py](file://janitor/utils/history_logger.py)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py)
- [version_control.py](file://janitor/utils/version_control.py)
- [config.py](file://janitor/config.py)
- [output.py](file://janitor/cli/utils/output.py)
- [decorators.py](file://janitor/cli/utils/decorators.py)
- [index_basic.py](file://janitor/operations/index_basic.py)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py)
- [template_management.py](file://janitor/operations/template_management.py)
- [rollback.py](file://janitor/operations/rollback.py)
- [change_history.py](file://janitor/operations/change_history.py)
</cite>

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Dependency Analysis](#dependency-analysis)
7. [Performance Considerations](#performance-considerations)
8. [Troubleshooting Guide](#troubleshooting-guide)
9. [Conclusion](#conclusion)
10. [Appendices](#appendices)

## Introduction
This document covers the utility functions and helpers that underpin Elastic Janitor’s operational safety, user experience, and auditability. It focuses on:
- Input validation utilities that ensure safe operations
- Formatting functions for dates, sizes, and other data types
- UI helper components such as breadcrumbs and interactive prompts
- History logging and change tracking mechanisms
- Pipeline and generic resource version management
- Practical usage examples and extensibility points for customization

These utilities are foundational to the CLI and menu-driven workflows, enabling robust, user-friendly, and auditable operations against Elasticsearch.

## Project Structure
The utility layer is organized into cohesive modules:
- Input validation and user prompts
- Formatting helpers for dates and sizes
- UI helpers for breadcrumbs
- History logging for operations
- Pipeline-specific version control
- Generic resource version control with dependency tracking
- CLI output formatting and decorators

```mermaid
graph TB
subgraph "Utilities"
U1["janitor/utils/helpers.py"]
U2["janitor/utils/formatters.py"]
U3["janitor/utils/ui.py"]
U4["janitor/utils/history_logger.py"]
U5["janitor/utils/pipeline_versions.py"]
U6["janitor/utils/version_control.py"]
end
subgraph "CLI Utilities"
C1["janitor/cli/utils/output.py"]
C2["janitor/cli/utils/decorators.py"]
end
subgraph "Config"
CFG["janitor/config.py"]
end
subgraph "Operations"
O1["janitor/operations/index_basic.py"]
O2["janitor/operations/data_streams_cleanup.py"]
O3["janitor/operations/template_management.py"]
O4["janitor/operations/rollback.py"]
O5["janitor/operations/change_history.py"]
end
U1 --> O1
U1 --> O2
U1 --> O3
U1 --> O4
U2 --> O1
U2 --> O2
U3 --> O1
U3 --> O2
U3 --> O3
U4 --> O4
U4 --> O5
U5 --> O3
U6 --> O3
C1 --> O3
C2 --> O3
CFG --> U1
CFG --> U6
```

**Diagram sources**
- [helpers.py](file://janitor/utils/helpers.py#L1-L258)
- [formatters.py](file://janitor/utils/formatters.py#L1-L53)
- [ui.py](file://janitor/utils/ui.py#L1-L12)
- [history_logger.py](file://janitor/utils/history_logger.py#L1-L73)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L1-L303)
- [version_control.py](file://janitor/utils/version_control.py#L1-L974)
- [output.py](file://janitor/cli/utils/output.py#L1-L153)
- [decorators.py](file://janitor/cli/utils/decorators.py#L1-L89)
- [config.py](file://janitor/config.py#L1-L78)
- [index_basic.py](file://janitor/operations/index_basic.py#L1-L200)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py#L1-L200)
- [template_management.py](file://janitor/operations/template_management.py#L1-L200)
- [rollback.py](file://janitor/operations/rollback.py#L156-L509)
- [change_history.py](file://janitor/operations/change_history.py#L194-L282)

**Section sources**
- [__init__.py](file://janitor/utils/__init__.py#L1-L27)
- [config.py](file://janitor/config.py#L1-L78)

## Core Components
- Input validation and user prompts:
  - Safe input handling with cancellation support
  - System resource protection checks
  - Confirmation dialogs with keyboard interrupt handling
  - Interactive selection with fuzzy filtering
  - Numeric input validation with bounds
  - Text input with defaults
  - Intelligent index pattern selection with fallbacks
- Formatting utilities:
  - Epoch milliseconds to UTC datetime
  - Human-readable size parsing to bytes
  - Byte-to-human-readable conversion
- UI helpers:
  - Breadcrumb navigation display
- History logging:
  - Operation logging to a local file
  - Retrieval of recent operations
  - Clearing history
- Pipeline version management:
  - SQLite-backed versioning for ingest pipelines
  - Known-good markers and pruning
- Generic resource version control:
  - Multi-resource versioning with dependency tracking
  - Automatic dependency discovery and snapshotting
  - Migration from legacy pipeline-only storage
- CLI output formatting and decorators:
  - Structured output in JSON, YAML, CSV, or Rich tables
  - Error handling and dry-run options

**Section sources**
- [helpers.py](file://janitor/utils/helpers.py#L1-L258)
- [formatters.py](file://janitor/utils/formatters.py#L1-L53)
- [ui.py](file://janitor/utils/ui.py#L1-L12)
- [history_logger.py](file://janitor/utils/history_logger.py#L1-L73)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L1-L303)
- [version_control.py](file://janitor/utils/version_control.py#L1-L974)
- [output.py](file://janitor/cli/utils/output.py#L1-L153)
- [decorators.py](file://janitor/cli/utils/decorators.py#L1-L89)

## Architecture Overview
The utilities integrate across layers:
- Operations modules import helpers for safe user interactions and formatting
- Version control integrates with Elasticsearch clients to discover dependencies
- CLI utilities provide consistent output and error handling
- Config centralizes global flags affecting behavior (e.g., system protection, dependency tracking)

```mermaid
graph TB
OP["Operations Modules"] --> H["helpers.py"]
OP --> F["formatters.py"]
OP --> UI["ui.py"]
OP --> HL["history_logger.py"]
OP --> PV["pipeline_versions.py"]
OP --> VC["version_control.py"]
VC --> ES["Elasticsearch Client"]
H --> CFG["config.py"]
VC --> CFG
OUT["CLI Output"] --> OP
DEC["CLI Decorators"] --> OP
```

**Diagram sources**
- [helpers.py](file://janitor/utils/helpers.py#L1-L258)
- [formatters.py](file://janitor/utils/formatters.py#L1-L53)
- [ui.py](file://janitor/utils/ui.py#L1-L12)
- [history_logger.py](file://janitor/utils/history_logger.py#L1-L73)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L1-L303)
- [version_control.py](file://janitor/utils/version_control.py#L1-L974)
- [config.py](file://janitor/config.py#L1-L78)
- [output.py](file://janitor/cli/utils/output.py#L1-L153)
- [decorators.py](file://janitor/cli/utils/decorators.py#L1-L89)

## Detailed Component Analysis

### Input Validation and User Prompts
Purpose:
- Enforce safe operations by validating inputs and confirming destructive actions
- Provide resilient user interactions with graceful cancellation and fallbacks

Key functions:
- Safe input handling with keyboard interrupt support
- System resource protection checks
- Confirmation dialogs with counts and keyboard interrupt handling
- Interactive selection with checkbox and select modes
- Numeric input validation with optional min/max bounds
- Text input with defaults
- Intelligent index pattern selection with auto-discovery and fallbacks

```mermaid
flowchart TD
Start(["User Action"]) --> Validate["Validate Input<br/>and Confirm"]
Validate --> SysCheck{"System Resource?"}
SysCheck --> |Yes| Protect["Skip or Warn"]
SysCheck --> |No| Proceed["Proceed"]
Validate --> Confirm{"Confirmed?"}
Confirm --> |No| Cancel["Cancel Operation"]
Confirm --> |Yes| Proceed
Proceed --> Fallback{"Error Occurs?"}
Fallback --> |Yes| Manual["Manual Input Fallback"]
Fallback --> |No| Complete["Complete Safely"]
```

**Diagram sources**
- [helpers.py](file://janitor/utils/helpers.py#L18-L258)
- [config.py](file://janitor/config.py#L18-L23)

Practical examples:
- Index cleanup operations use numeric input validation for retention days and interactive selection for targets
- Template management uses confirmation dialogs and breadcrumb navigation for clarity
- Rollback operations rely on safe input and confirmation to prevent accidental rollbacks

**Section sources**
- [helpers.py](file://janitor/utils/helpers.py#L1-L258)
- [index_basic.py](file://janitor/operations/index_basic.py#L14-L71)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py#L15-L200)
- [template_management.py](file://janitor/operations/template_management.py#L25-L125)
- [rollback.py](file://janitor/operations/rollback.py#L447-L509)

### Formatting Functions
Purpose:
- Normalize and present data consistently across the application

Functions:
- Epoch milliseconds to UTC datetime
- Size string to bytes (supports kb, mb, gb, tb, b)
- Bytes to human-readable format

```mermaid
flowchart TD
A["Input Value"] --> B{"Type?"}
B --> |Epoch ms| C["Convert to datetime (UTC)"]
B --> |Size String| D["Parse unit and magnitude"]
D --> E["Multiply by multiplier"]
B --> |Bytes| F["Scale to appropriate unit"]
C --> G["Formatted Output"]
E --> G
F --> G
```

**Diagram sources**
- [formatters.py](file://janitor/utils/formatters.py#L7-L52)

Practical examples:
- Index listing and cleanup operations use size parsing and human-readable formatting for reports
- Data stream operations compute reclaimed space and present it in human-readable units

**Section sources**
- [formatters.py](file://janitor/utils/formatters.py#L1-L53)
- [index_basic.py](file://janitor/operations/index_basic.py#L26-L49)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py#L95-L162)

### UI Helper Components
Purpose:
- Improve user experience with structured navigation and feedback

Components:
- Breadcrumb navigation display for menu-based workflows

```mermaid
sequenceDiagram
participant User as "User"
participant Ops as "Operations Module"
participant UI as "ui.py"
participant Console as "Rich Console"
User->>Ops : Navigate to submenu
Ops->>UI : show_breadcrumb(path)
UI->>Console : Print formatted breadcrumb
Console-->>User : Visual navigation aid
```

**Diagram sources**
- [ui.py](file://janitor/utils/ui.py#L7-L11)
- [index_basic.py](file://janitor/operations/index_basic.py#L79-L81)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py#L154-L156)
- [template_management.py](file://janitor/operations/template_management.py#L25-L27)

**Section sources**
- [ui.py](file://janitor/utils/ui.py#L1-L12)
- [index_basic.py](file://janitor/operations/index_basic.py#L79-L81)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py#L154-L156)
- [template_management.py](file://janitor/operations/template_management.py#L25-L27)

### History Logging and Change Tracking
Purpose:
- Maintain an audit trail of operations for accountability and recovery

Functions:
- Log operations to a local file with timestamps and resource lists
- Retrieve recent operations for review
- Clear history

```mermaid
sequenceDiagram
participant Ops as "Operations Module"
participant Logger as "history_logger.py"
participant FS as "Filesystem"
Ops->>Logger : log_operation(type, resources, description)
Logger->>FS : Append log entry
FS-->>Logger : Success/Failure
Logger-->>Ops : Return
Ops->>Logger : get_recent_operations(n)
Logger->>FS : Read last n lines
FS-->>Logger : Entries
Logger-->>Ops : List of entries
Ops->>Logger : clear_history()
Logger->>FS : Remove log file
FS-->>Logger : Success/Failure
Logger-->>Ops : Boolean result
```

**Diagram sources**
- [history_logger.py](file://janitor/utils/history_logger.py#L9-L72)
- [rollback.py](file://janitor/operations/rollback.py#L503-L507)
- [change_history.py](file://janitor/operations/change_history.py#L194-L282)

Practical examples:
- Rollback operations log the action with affected resources
- Change history module loads and filters historical entries for analysis

**Section sources**
- [history_logger.py](file://janitor/utils/history_logger.py#L1-L73)
- [rollback.py](file://janitor/operations/rollback.py#L503-L507)
- [change_history.py](file://janitor/operations/change_history.py#L194-L282)

### Pipeline Version Management
Purpose:
- Track and manage ingest pipeline configurations with version limits and known-good markers

Key functions:
- Save pipeline versions with comments and known-good flags
- Retrieve all versions, specific versions, and last known-good version
- Prune older versions beyond a configurable limit
- Delete all versions for a pipeline
- Enumerate pipelines with stored versions and count versions

```mermaid
flowchart TD
S["Save Version"] --> V["Compute Next Version"]
V --> Store["Insert into DB"]
Store --> Prune["Delete Old Versions (Limit)"]
Prune --> Done["Done"]
R["Retrieve Versions"] --> Q["Query Versions Desc"]
Q --> Parse["Parse JSON Config"]
Parse --> Return["Return List"]
K["Known-Good"] --> Latest["Latest Known-Good"]
```

**Diagram sources**
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L61-L116)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L118-L189)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L191-L227)

Practical examples:
- Template management leverages pipeline versioning during edits and rollbacks

**Section sources**
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L1-L303)
- [template_management.py](file://janitor/operations/template_management.py#L18-L22)

### Generic Resource Version Control and Dependency Tracking
Purpose:
- Extend versioning to multiple resource types (pipelines, index templates, component templates)
- Capture and compare dependencies across versions

Core capabilities:
- Save resource versions with comments and known-good flags
- Retrieve versions, specific version, and last known-good version
- Delete all versions for a resource
- Enumerate resources by type and count versions
- Discover dependencies across resource types
- Save dependency snapshots and compare with current state
- Migration from legacy pipeline-only storage

```mermaid
sequenceDiagram
participant Ops as "Operations Module"
participant VC as "version_control.py"
participant ES as "Elasticsearch Client"
participant DB as "SQLite DB"
Ops->>VC : save_resource_version_with_dependencies(es, type, name, cfg, comment, known-good)
VC->>DB : Insert version record
VC->>VC : _discover_dependencies(es, type, name)
VC->>ES : Query templates/pipelines/components
ES-->>VC : Dependency definitions
VC->>DB : Insert dependency snapshots
VC-->>Ops : Version number
Ops->>VC : get_resource_dependencies(type, name, version)
VC->>DB : Query dependency snapshots
DB-->>VC : Dependency records
VC-->>Ops : Dependency list
```

**Diagram sources**
- [version_control.py](file://janitor/utils/version_control.py#L167-L224)
- [version_control.py](file://janitor/utils/version_control.py#L441-L528)
- [version_control.py](file://janitor/utils/version_control.py#L703-L734)
- [version_control.py](file://janitor/utils/version_control.py#L737-L773)

Practical examples:
- Template management uses dependency-aware versioning to capture composed-of relationships and pipeline references

**Section sources**
- [version_control.py](file://janitor/utils/version_control.py#L1-L974)
- [template_management.py](file://janitor/operations/template_management.py#L18-L22)

### CLI Output Formatting and Decorators
Purpose:
- Standardize output presentation and error handling across CLI commands

Capabilities:
- Output formatting in JSON, YAML, CSV, or Rich tables
- Structured success/warning/error/info messaging
- Command decorators for Elasticsearch client injection, error handling, dry-run, and common options

```mermaid
flowchart TD
A["Command Function"] --> B["Apply Decorators"]
B --> C["Pass ES Client"]
B --> D["Handle Errors"]
B --> E["Add Options (--dry-run, --output, etc.)"]
C --> F["Execute Logic"]
D --> F
E --> F
F --> G["Format Output"]
G --> H["Rich Console Output"]
```

**Diagram sources**
- [decorators.py](file://janitor/cli/utils/decorators.py#L13-L89)
- [output.py](file://janitor/cli/utils/output.py#L22-L132)

**Section sources**
- [output.py](file://janitor/cli/utils/output.py#L1-L153)
- [decorators.py](file://janitor/cli/utils/decorators.py#L1-L89)
- [template_management.py](file://janitor/operations/template_management.py#L25-L125)

## Dependency Analysis
- Cohesion:
  - Each module encapsulates a distinct concern (input validation, formatting, UI, logging, versioning)
- Coupling:
  - Operations modules depend on helpers and formatters for safe UX and consistent data display
  - Version control depends on Elasticsearch for dependency discovery
  - CLI utilities are consumed by operations for standardized output and error handling
- External dependencies:
  - SQLite for local persistence of versions and history
  - Rich and Questionary for UI and interactive prompts
  - Elasticsearch client for dependency discovery and resource operations

```mermaid
graph TB
H["helpers.py"] --> CFG["config.py"]
F["formatters.py"] --> OPS["operations/*"]
UI["ui.py"] --> OPS
HL["history_logger.py"] --> OPS
PV["pipeline_versions.py"] --> OPS
VC["version_control.py"] --> ES["Elasticsearch"]
VC --> CFG
OUT["output.py"] --> OPS
DEC["decorators.py"] --> OPS
```

**Diagram sources**
- [helpers.py](file://janitor/utils/helpers.py#L1-L258)
- [formatters.py](file://janitor/utils/formatters.py#L1-L53)
- [ui.py](file://janitor/utils/ui.py#L1-L12)
- [history_logger.py](file://janitor/utils/history_logger.py#L1-L73)
- [pipeline_versions.py](file://janitor/utils/pipeline_versions.py#L1-L303)
- [version_control.py](file://janitor/utils/version_control.py#L1-L974)
- [config.py](file://janitor/config.py#L1-L78)
- [output.py](file://janitor/cli/utils/output.py#L1-L153)
- [decorators.py](file://janitor/cli/utils/decorators.py#L1-L89)

**Section sources**
- [__init__.py](file://janitor/utils/__init__.py#L1-L27)
- [config.py](file://janitor/config.py#L1-L78)

## Performance Considerations
- Input validation:
  - Interactive selections and numeric inputs use lightweight validators; avoid excessive retries by providing sensible defaults
- Formatting:
  - Size parsing and byte conversions are O(1); ensure minimal repeated conversions in tight loops
- UI:
  - Breadcrumbs are lightweight prints; avoid frequent updates in hot loops
- History logging:
  - Logging is append-only and non-blocking; consider rotating logs for long-running sessions
- Version control:
  - SQLite operations are efficient; pruning limits reduce overhead
  - Dependency discovery queries can be expensive; enable depth limits and disable tracking when unnecessary
- CLI output:
  - Rich tables and syntax highlighting add overhead; prefer JSON/YAML for machine consumption

[No sources needed since this section provides general guidance]

## Troubleshooting Guide
- Keyboard interrupts:
  - Safe input and confirmation dialogs handle interrupts gracefully; operations cancel cleanly
- No indices found:
  - Index pattern selection falls back to manual input; verify cluster connectivity and permissions
- History file issues:
  - Logging failures are suppressed to avoid interrupting operations; check filesystem permissions
- Dependency tracking disabled:
  - When dependency tracking is off, dependency snapshots are not captured; enable via configuration
- Dry-run mode:
  - Decorators support dry-run; ensure flags are respected in operations to preview changes

**Section sources**
- [helpers.py](file://janitor/utils/helpers.py#L13-L15)
- [helpers.py](file://janitor/utils/helpers.py#L63-L65)
- [helpers.py](file://janitor/utils/helpers.py#L250-L257)
- [history_logger.py](file://janitor/utils/history_logger.py#L33-L35)
- [version_control.py](file://janitor/utils/version_control.py#L462-L463)
- [decorators.py](file://janitor/cli/utils/decorators.py#L49-L61)

## Conclusion
The utility layer in Elastic Janitor provides a robust foundation for safe, user-friendly, and auditable operations. By centralizing input validation, formatting, UI aids, logging, and version control—both for pipelines and generic resources—the system ensures reliability across diverse workflows. Developers can extend these utilities to customize prompts, add new formats, or integrate additional resource types while maintaining consistent behavior and strong safeguards.

[No sources needed since this section summarizes without analyzing specific files]

## Appendices

### Practical Examples and How Utilities Support Main Functionality
- Index management:
  - Uses safe input and size formatting for top-N largest indices
  - Applies system protection and breadcrumb navigation for clarity
- Data streams cleanup:
  - Validates numeric inputs for retention, computes reclaimed space, and paginates previews
- Template management:
  - Leverages version control with dependency tracking and structured output
- Rollback:
  - Logs rollback operations and relies on safe input and confirmation for safety
- Change history:
  - Loads and filters historical entries for auditing

**Section sources**
- [index_basic.py](file://janitor/operations/index_basic.py#L14-L71)
- [data_streams_cleanup.py](file://janitor/operations/data_streams_cleanup.py#L15-L200)
- [template_management.py](file://janitor/operations/template_management.py#L25-L125)
- [rollback.py](file://janitor/operations/rollback.py#L447-L509)
- [change_history.py](file://janitor/operations/change_history.py#L194-L282)

### Extensibility Points
- Adding new input validators:
  - Extend helpers with new validation functions and integrate into existing prompts
- New formatting rules:
  - Add format converters in formatters.py and apply in operations modules
- UI enhancements:
  - Extend ui.py with additional navigation aids or status indicators
- Logging improvements:
  - Enhance history_logger with structured metadata or external sinks
- Version control expansion:
  - Add new resource types to version_control.py and define discovery logic
- CLI output customization:
  - Extend output.py with new formats or styles, and update decorators for new options

**Section sources**
- [helpers.py](file://janitor/utils/helpers.py#L68-L96)
- [formatters.py](file://janitor/utils/formatters.py#L7-L52)
- [ui.py](file://janitor/utils/ui.py#L7-L11)
- [history_logger.py](file://janitor/utils/history_logger.py#L9-L36)
- [version_control.py](file://janitor/utils/version_control.py#L167-L224)
- [output.py](file://janitor/cli/utils/output.py#L22-L132)
- [decorators.py](file://janitor/cli/utils/decorators.py#L64-L89)