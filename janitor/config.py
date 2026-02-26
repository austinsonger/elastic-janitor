"""
Configuration and constants for Elastic Janitor.
"""
import os
from dotenv import load_dotenv
from rich.console import Console
from questionary import Style

# Load environment variables from .env file
load_dotenv()

# ------------------------------------------------------------
# Elasticsearch Settings
# ------------------------------------------------------------

ELASTIC_URL = os.getenv("ELASTIC_URL", "https://cirrusmd-siem.es.us-gov-east-1.aws.elastic-cloud.com:9243")
ELASTIC_API_KEY = os.getenv("ELASTIC_API_KEY", "")

# ------------------------------------------------------------
# Application Settings
# ------------------------------------------------------------

PROTECT_SYSTEM = True
DEFAULT_RETENTION_DAYS = 90
MAX_DELETE_LIMIT = 5000

# God-Mode flag - when False (default), all operations are non-destructive simulations
# Set to True to enable destructive operations (requires confirmation phrase)
GOD_MODE = False
GOD_MODE_CONFIRMATION_PHRASE = "I UNDERSTAND"

# ------------------------------------------------------------
# Query Timeout Settings
# ------------------------------------------------------------

# Default timeout for Elasticsearch queries (seconds)
DEFAULT_QUERY_TIMEOUT = 30

# Timeout for slow queries like wildcard searches (seconds)
SLOW_QUERY_TIMEOUT = 60

# Client-side request timeout (seconds)
REQUEST_TIMEOUT = 90

# Reindex operation timeout (seconds)
REINDEX_TIMEOUT = 300

# ------------------------------------------------------------
# Version Control Settings
# ------------------------------------------------------------

# Enable automatic dependency tracking when saving resource versions
# When enabled, saving a resource will also capture snapshots of all related resources
ENABLE_DEPENDENCY_TRACKING = True

# Maximum depth for dependency chain traversal (prevents infinite recursion)
# Depth 1: Direct dependencies only
# Depth 2: Dependencies and their dependencies
MAX_DEPENDENCY_DEPTH = 2

# Maximum number of versions to keep per resource
MAX_VERSIONS_PER_RESOURCE = 20

# ------------------------------------------------------------
# UI Configuration
# ------------------------------------------------------------

# Initialize Rich console
console = Console()

# Questionary custom style
custom_style = Style([
    ('qmark', 'fg:#673ab7 bold'),
    ('question', 'bold'),
    ('answer', 'fg:#f44336 bold'),
    ('pointer', 'fg:#673ab7 bold'),
    ('highlighted', 'fg:#673ab7 bold'),
    ('selected', 'fg:#cc5454'),
    ('separator', 'fg:#cc5454'),
    ('instruction', ''),
    ('text', ''),
    ('disabled', 'fg:#858585 italic')
])

