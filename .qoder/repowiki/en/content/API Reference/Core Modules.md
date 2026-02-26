# Core Modules

<cite>
**Referenced Files in This Document**
- [connection.py](file://janitor/core/connection.py)
- [config.py](file://janitor/config.py)
- [formatters.py](file://janitor/utils/formatters.py)
- [helpers.py](file://janitor/utils/helpers.py)
- [main_menu.py](file://janitor/menus/main_menu.py)
- [submenus.py](file://janitor/menus/submenus.py)
- [cluster.py](file://janitor/operations/cluster.py)
- [template_policy_advanced.py](file://janitor/operations/template_policy_advanced.py)
- [templates_policies.py](file://janitor/operations/templates_policies.py)
- [template_management.py](file://janitor/operations/template_management.py)
- [requirements.txt](file://requirements.txt)
- [README.md](file://README.md)
</cite>

## Update Summary
**Changes Made**
- Added comprehensive documentation for advanced template and policy management operations
- Documented sophisticated pattern matching, dependency analysis, and reporting mechanisms
- Updated architecture overview to include advanced template conflict detection and policy management
- Enhanced troubleshooting guide with new template and policy management scenarios
- Added new sections covering template validation, policy simulation, and performance impact analysis

## Table of Contents
1. [Introduction](#introduction)
2. [Project Structure](#project-structure)
3. [Core Components](#core-components)
4. [Architecture Overview](#architecture-overview)
5. [Detailed Component Analysis](#detailed-component-analysis)
6. [Advanced Template and Policy Management](#advanced-template-and-policy-management)
7. [Dependency Analysis](#dependency-analysis)
8. [Performance Considerations](#performance-considerations)
9. [Troubleshooting Guide](#troubleshooting-guide)
10. [Conclusion](#conclusion)

## Introduction
This document provides comprehensive API documentation for Elastic Janitor's core modules with a focus on connection management and advanced template and policy management operations. It explains how the Elasticsearch client is initialized, how connections are established and reused, and how errors are handled. The document now includes extensive coverage of advanced template conflict detection, ILM policy simulation, template validation analyzers, performance impact analysis, policy health checking, and template-policy alignment detection. It also documents the public interfaces exposed by the core connection module, configuration options, timeouts, and operational patterns used across the application.

## Project Structure
The core connection logic resides in the core package and is consumed by menu-driven flows and operations. Advanced template and policy management operations are integrated into the main menu system under the "Template & Policy Management" category. Supporting utilities provide formatting and interactive helpers. Configuration constants define connection parameters and timeouts.

```mermaid
graph TB
subgraph "Core"
C["janitor/core/connection.py"]
end
subgraph "Config"
CFG["janitor/config.py"]
end
subgraph "Utils"
FMT["janitor/utils/formatters.py"]
HELP["janitor/utils/helpers.py"]
end
subgraph "Menus"
MM["janitor/menus/main_menu.py"]
SUB["janitor/menus/submenus.py"]
end
subgraph "Operations"
CL["janitor/operations/cluster.py"]
TPA["janitor/operations/template_policy_advanced.py"]
TPL["janitor/operations/templates_policies.py"]
TM["janitor/operations/template_management.py"]
end
subgraph "External"
REQ["requirements.txt"]
end
MM --> C
SUB --> C
CL --> C
TPA --> C
TPL --> C
TM --> C
C --> CFG
C --> FMT
HELP --> CFG
REQ --> |"elasticsearch"| C
```

**Diagram sources**
- [connection.py](file://janitor/core/connection.py#L1-L72)
- [config.py](file://janitor/config.py#L1-L78)
- [formatters.py](file://janitor/utils/formatters.py#L1-L53)
- [helpers.py](file://janitor/utils/helpers.py#L1-L258)
- [main_menu.py](file://janitor/menus/main_menu.py#L1-L135)
- [submenus.py](file://janitor/menus/submenus.py#L269-L550)
- [cluster.py](file://janitor/operations/cluster.py#L1-L242)
- [template_policy_advanced.py](file://janitor/operations/template_policy_advanced.py#L1-L1881)
- [templates_policies.py](file://janitor/operations/templates_policies.py#L1-L180)
- [template_management.py](file://janitor/operations/template_management.py#L1-L821)
- [requirements.txt](file://requirements.txt#L1-L7)

**Section sources**
- [connection.py](file://janitor/core/connection.py#L1-L72)
- [config.py](file://janitor/config.py#L1-L78)
- [README.md](file://README.md#L143-L184)

## Core Components
This section documents the core connection module's public interfaces, configuration options, and lifecycle management.

- Public interface functions
  - connect(): Establishes an Elasticsearch connection using configured credentials and validates connectivity.
  - get_index_creation(es, index_name): Retrieves an index's creation date from cluster settings.
  - get_all_indices_info(es): Fetches index metadata (creation date, sizes, and tier) for all indices in a single call.

- Configuration options
  - ELASTIC_URL: Elasticsearch endpoint URL.
  - ELASTIC_API_KEY: API key for authentication.
  - DEFAULT_QUERY_TIMEOUT, SLOW_QUERY_TIMEOUT, REQUEST_TIMEOUT, REINDEX_TIMEOUT: Client-side and operation-specific timeouts.
  - DRY_RUN_MODE: Global dry-run flag affecting downstream operations.
  - PROTECT_SYSTEM, MAX_DELETE_LIMIT: Operational safeguards.

- Connection lifecycle
  - Initialization: connect() constructs an Elasticsearch client with hosts and API key, then calls cluster info to validate connectivity.
  - Validation: On success, the function prints the cluster name and returns the client instance.
  - Failure handling: On exception, an error message is printed and the process exits.

- Data formatting utilities
  - parse_epoch_millis(): Converts millisecond timestamps to UTC datetime.
  - size_to_bytes(): Parses human-readable sizes (e.g., kb, mb, gb, tb) to bytes.

- Example usage patterns
  - Establishing a connection: Call connect() from the main menu or operations to obtain an Elasticsearch client instance.
  - Managing connection state: Use the returned client instance across operations until the session ends.
  - Handling failures: Rely on connect()'s built-in error handling and exit behavior; wrap downstream operations in try/except blocks as needed.

**Section sources**
- [connection.py](file://janitor/core/connection.py#L11-L33)
- [connection.py](file://janitor/core/connection.py#L35-L39)
- [connection.py](file://janitor/core/connection.py#L42-L70)
- [config.py](file://janitor/config.py#L11-L12)
- [config.py](file://janitor/config.py#L29-L40)
- [config.py](file://janitor/config.py#L18-L24)
- [formatters.py](file://janitor/utils/formatters.py#L7-L38)
- [main_menu.py](file://janitor/menus/main_menu.py#L48-L48)

## Architecture Overview
The connection module integrates with the configuration and utilities to provide a cohesive connection lifecycle. Menus and operations consume the client instance returned by connect(). The architecture now includes advanced template and policy management operations that leverage the same connection infrastructure.

```mermaid
sequenceDiagram
participant User as "User"
participant Menu as "Main Menu"
participant Submenu as "Template & Policy Submenu"
participant Conn as "Connection Module"
participant ES as "Elasticsearch Client"
participant Util as "Formatters"
User->>Menu : Launch application
Menu->>Conn : connect()
Conn->>Conn : Validate ELASTIC_URL and ELASTIC_API_KEY
Conn->>ES : Initialize client with hosts and API key
Conn->>ES : info()
ES-->>Conn : Cluster info (including cluster_name)
Conn->>Util : parse_epoch_millis() (for index creation)
Conn-->>Menu : Return ES client instance
Menu->>Submenu : Navigate to Template & Policy Management
Submenu->>ES : Advanced template and policy operations
ES-->>Submenu : Analysis results and recommendations
```

**Diagram sources**
- [main_menu.py](file://janitor/menus/main_menu.py#L48-L48)
- [submenus.py](file://janitor/menus/submenus.py#L270-L306)
- [connection.py](file://janitor/core/connection.py#L11-L33)
- [formatters.py](file://janitor/utils/formatters.py#L7-L9)

## Detailed Component Analysis

### Connection Module
The connection module exposes three primary functions and orchestrates client initialization and validation.

```mermaid
flowchart TD
Start(["connect() called"]) --> CheckCfg["Check ELASTIC_URL and ELASTIC_API_KEY"]
CheckCfg --> CfgOK{"Both configured?"}
CfgOK --> |No| Exit["Print error and exit"]
CfgOK --> |Yes| InitClient["Initialize Elasticsearch client with hosts and API key"]
InitClient --> Validate["Call client.info()"]
Validate --> Ok{"Success?"}
Ok --> |No| PrintErr["Print error and exit"]
Ok --> |Yes| PrintCluster["Print connected cluster name"]
PrintCluster --> ReturnClient["Return ES client instance"]
```

- Parameters and configuration
  - ELASTIC_URL: Host endpoint used to initialize the client.
  - ELASTIC_API_KEY: Authentication credential passed to the client.
  - DEFAULT_QUERY_TIMEOUT, SLOW_QUERY_TIMEOUT, REQUEST_TIMEOUT, REINDEX_TIMEOUT: While timeouts are defined in configuration, the current connect() implementation does not pass them to the client constructor. Downstream operations may apply these timeouts when invoking client APIs.

- Authentication method
  - API key authentication is used during client initialization.

- SSL/TLS configuration
  - The client is initialized with a host URL; SSL/TLS behavior follows the underlying client defaults. No explicit TLS parameters are set in the current implementation.

- Error handling patterns
  - connect(): Validates configuration, attempts client.info(), catches exceptions, prints a red error message, and exits the process.
  - get_all_indices_info(): Wraps the indices retrieval in a progress spinner and returns a structured map of index metadata. Exceptions are not explicitly caught in this function; callers should handle exceptions when invoking it.

- Retry mechanisms
  - There is no built-in retry logic in the connection module. Retries are not implemented in connect() or the index retrieval functions.

- Thread safety and reuse
  - The Elasticsearch client instance returned by connect() is intended for use within a single session. The module does not implement connection pooling or long-lived client reuse. Each invocation of connect() creates a new client instance.

- Practical examples
  - Establishing a connection: See the main menu's call to connect().
  - Managing connection state: Use the returned client instance across menu submenus and operations.
  - Handling failures: Rely on connect()'s error handling; wrap downstream operations in try/except blocks as needed.

**Section sources**
- [connection.py](file://janitor/core/connection.py#L11-L33)
- [connection.py](file://janitor/core/connection.py#L42-L70)
- [config.py](file://janitor/config.py#L11-L12)
- [config.py](file://janitor/config.py#L29-L40)
- [main_menu.py](file://janitor/menus/main_menu.py#L48-L48)

### Data Formatting Utilities
The formatting utilities support parsing and converting index metadata retrieved from the cluster.

```mermaid
flowchart TD
A["parse_epoch_millis(ms)"] --> B["Convert milliseconds to datetime in UTC"]
C["size_to_bytes(size_str)"] --> D{"Ends with unit?"}
D --> |kb| E["Multiply by 1024"]
D --> |mb| F["Multiply by 1024^2"]
D --> |gb| G["Multiply by 1024^3"]
D --> |tb| H["Multiply by 1024^4"]
D --> |b| I["Use raw value"]
D --> |none| J["Fallback to raw value"]
E --> K["Return float value"]
F --> K
G --> K
H --> K
I --> K
J --> K
```

- Purpose
  - parse_epoch_millis(): Converts creation timestamps from milliseconds to UTC datetime.
  - size_to_bytes(): Converts human-readable sizes to bytes for numerical comparisons.

- Usage in connection module
  - get_all_indices_info() uses parse_epoch_millis() to normalize creation dates and size_to_bytes() to convert textual sizes to numeric byte values.

**Section sources**
- [formatters.py](file://janitor/utils/formatters.py#L7-L38)
- [connection.py](file://janitor/core/connection.py#L35-L39)
- [connection.py](file://janitor/core/connection.py#L60-L68)

### Menu and Operations Integration
The main menu obtains the client instance and passes it to submenus and operations. The Template & Policy Management submenu now provides access to advanced template and policy operations.

```mermaid
sequenceDiagram
participant Menu as "Main Menu"
participant Conn as "Connection Module"
participant Submenu as "Template & Policy Submenu"
participant Op as "Operations"
participant ES as "Elasticsearch Client"
Menu->>Conn : connect()
Conn-->>Menu : ES client
Menu->>Submenu : submenu_templates_policies(ES)
Submenu->>Op : Advanced template operations
Submenu->>Op : ILM policy operations
Op->>ES : Advanced template and policy operations
ES-->>Op : Analysis results and recommendations
Op-->>Submenu : Formatted reports
Submenu-->>Menu : Results displayed
```

- Key points
  - The main menu calls connect() once per session and forwards the client to all operations.
  - The Template & Policy Management submenu provides access to both basic template operations and advanced analysis tools.
  - Operations like cluster health and index listing rely on the shared client instance.
  - get_all_indices_info() is used by operations to aggregate index metadata efficiently.

**Section sources**
- [main_menu.py](file://janitor/menus/main_menu.py#L88-L118)
- [submenus.py](file://janitor/menus/submenus.py#L270-L306)
- [cluster.py](file://janitor/operations/cluster.py#L127-L200)
- [connection.py](file://janitor/core/connection.py#L42-L70)

## Advanced Template and Policy Management

### Template Management Operations
The template management system provides comprehensive operations for managing index and component templates with version control and rollback capabilities.

- **Index Template Operations**
  - View template details with structure analysis
  - Edit templates with version control and dependency tracking
  - Rollback to previous versions with automatic backups
  - Export/import templates to/from JSON files
  - Delete templates by name matching with safety limits

- **Component Template Operations**
  - Similar operations to index templates with component-specific features
  - Version control integration for component templates
  - Dependency analysis for template inheritance chains

- **Template Analysis Tools**
  - Template conflict detection for overlapping patterns
  - Template inheritance viewer for component template composition
  - Unused template detection for cleanup recommendations
  - Template validation analyzer for structural integrity checks

### ILM Policy Management Operations
The ILM policy management system provides sophisticated lifecycle management capabilities.

- **Basic Operations**
  - List and delete ILM policies by name matching
  - View policy details and structure
  - Manage ingest pipelines with version control

- **Advanced Operations**
  - ILM policy simulator for lifecycle phase prediction
  - Bulk policy assignment for multiple indices
  - Policy effectiveness report for usage statistics
  - Policy health checker for compliance monitoring
  - Template-policy alignment detector for governance

### Performance Impact Analysis
The system includes comprehensive performance impact analysis for template configurations.

- **Performance Issue Detection**
  - Excessive replica settings analysis
  - Shard allocation optimization recommendations
  - Disabled refresh interval warnings
  - Timestamp field mapping validation
  - Codec settings optimization for different data tiers
  - Tier allocation recommendations for storage optimization

- **Impact Scoring System**
  - High, medium, and low impact level categorization
  - Automated optimization recommendations
  - Performance impact visualization

### Pattern Matching and Conflict Detection
Sophisticated pattern matching algorithms for template conflict resolution.

- **Pattern Overlap Detection**
  - Wildcard pattern matching and comparison
  - Priority-based conflict resolution
  - Template inheritance chain analysis
  - Component template dependency mapping

- **Dependency Analysis**
  - Template composition analysis
  - Component template inheritance tracking
  - Version dependency management
  - Rollback dependency resolution

**Section sources**
- [template_management.py](file://janitor/operations/template_management.py#L1-L821)
- [template_policy_advanced.py](file://janitor/operations/template_policy_advanced.py#L1-L1881)
- [templates_policies.py](file://janitor/operations/templates_policies.py#L1-L180)
- [submenus.py](file://janitor/menus/submenus.py#L270-L550)

## Dependency Analysis
External dependencies and internal relationships are summarized below.

```mermaid
graph TB
REQ["requirements.txt"] --> |"elasticsearch"| ES["Elasticsearch Client"]
CFG["config.py"] --> |"ELASTIC_URL, ELASTIC_API_KEY"| CONN["connection.py"]
CONN --> |"info(), cat.indices()"| ES
CONN --> |"parse_epoch_millis(), size_to_bytes()"| FMT["formatters.py"]
MM["main_menu.py"] --> |"calls connect()"| CONN
SUB["menus/submenus.py"] --> |"calls operations" | CONN
CL["operations/cluster.py"] --> |"uses ES client"| ES
TPA["operations/template_policy_advanced.py"] --> |"advanced template ops"| ES
TPL["operations/templates_policies.py"] --> |"basic template ops"| ES
TM["operations/template_management.py"] --> |"template ops"| ES
```

**Diagram sources**
- [requirements.txt](file://requirements.txt#L1-L7)
- [config.py](file://janitor/config.py#L11-L12)
- [connection.py](file://janitor/core/connection.py#L17-L29)
- [connection.py](file://janitor/core/connection.py#L50-L68)
- [formatters.py](file://janitor/utils/formatters.py#L7-L38)
- [main_menu.py](file://janitor/menus/main_menu.py#L48-L48)
- [submenus.py](file://janitor/menus/submenus.py#L270-L306)
- [cluster.py](file://janitor/operations/cluster.py#L127-L200)
- [template_policy_advanced.py](file://janitor/operations/template_policy_advanced.py#L1-L1881)
- [templates_policies.py](file://janitor/operations/templates_policies.py#L1-L180)
- [template_management.py](file://janitor/operations/template_management.py#L1-L821)

**Section sources**
- [requirements.txt](file://requirements.txt#L1-L7)
- [config.py](file://janitor/config.py#L11-L12)
- [connection.py](file://janitor/core/connection.py#L17-L29)
- [connection.py](file://janitor/core/connection.py#L50-L68)
- [formatters.py](file://janitor/utils/formatters.py#L7-L38)
- [main_menu.py](file://janitor/menus/main_menu.py#L48-L48)
- [submenus.py](file://janitor/menus/submenus.py#L270-L306)
- [cluster.py](file://janitor/operations/cluster.py#L127-L200)

## Performance Considerations
- Single-client sessions: The connection module initializes a new client per session. This avoids complex pooling logic but means each operation uses a fresh connection instance.
- Efficient metadata retrieval: get_all_indices_info() consolidates index metadata in a single API call, reducing round-trips and improving throughput for dashboards and analytics.
- Timeout configuration: While timeouts are defined in configuration, the current connect() implementation does not pass them to the client. Downstream operations should apply appropriate timeouts when invoking client APIs.
- Advanced operations performance: Template and policy analysis operations may require multiple API calls and can be resource-intensive. Progress indicators and batch processing help manage performance impact.

## Troubleshooting Guide
Common issues and resolutions:

- Missing configuration
  - Symptom: Immediate exit after printing an error message.
  - Cause: ELASTIC_URL or ELASTIC_API_KEY is not set.
  - Resolution: Set both values in configuration or environment variables and rerun.

- Connection failure
  - Symptom: Error message indicating inability to connect; process exits.
  - Cause: Network issues, invalid URL, or incorrect API key.
  - Resolution: Verify endpoint accessibility, credentials, and network connectivity.

- Index metadata retrieval errors
  - Symptom: Exceptions when fetching indices.
  - Cause: Cluster state changes or permission issues.
  - Resolution: Retry after ensuring cluster stability and permissions; wrap calls in try/except blocks.

- Template operation failures
  - Symptom: Template validation errors or rollback issues.
  - Cause: Invalid JSON structure or template conflicts.
  - Resolution: Use template validation analyzer to identify issues; resolve conflicts before applying changes.

- Performance impact analysis warnings
  - Symptom: Performance warnings for template configurations.
  - Cause: Suboptimal settings for replica counts, shard allocation, or field mappings.
  - Resolution: Review optimization recommendations and adjust template settings accordingly.

- Timeout-related delays
  - Symptom: Slow operations or timeouts.
  - Cause: Long-running queries or insufficient timeouts.
  - Resolution: Adjust DEFAULT_QUERY_TIMEOUT, SLOW_QUERY_TIMEOUT, REQUEST_TIMEOUT, or REINDEX_TIMEOUT as needed.

**Section sources**
- [connection.py](file://janitor/core/connection.py#L13-L15)
- [connection.py](file://janitor/core/connection.py#L30-L32)
- [config.py](file://janitor/config.py#L29-L40)

## Conclusion
The core connection module provides a straightforward, configuration-driven mechanism to establish and validate an Elasticsearch client instance. It integrates cleanly with menus and operations, offering efficient index metadata retrieval and robust error handling at the connection boundary. The addition of advanced template and policy management operations significantly enhances the system's capabilities, providing sophisticated pattern matching, dependency analysis, and comprehensive reporting mechanisms. These advanced operations leverage the same connection infrastructure while offering specialized functionality for template conflict detection, ILM policy simulation, template validation, performance impact analysis, and governance compliance checking. For production deployments, consider externalizing secrets, adding retry logic, and enabling connection pooling if long-lived sessions are required. The existing utilities and configuration options provide a solid foundation for extending connection management capabilities while the new template and policy management features offer enterprise-grade template governance and optimization tools.