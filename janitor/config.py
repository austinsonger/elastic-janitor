"""
Configuration and constants for Elastic Janitor.
"""
from rich.console import Console
from questionary import Style

# ------------------------------------------------------------
# Elasticsearch Settings
# ------------------------------------------------------------

ELASTIC_URL = "https://cirrusmd-siem.es.us-gov-east-1.aws.elastic-cloud.com:9243"
ELASTIC_API_KEY = "azBpcFY1d0JaelVXTU5aeTRZZms6eUpZUVJCS1ozNjZKZ21kMWNEVUJkdw=="

# ------------------------------------------------------------
# Application Settings
# ------------------------------------------------------------

PROTECT_SYSTEM = True
DEFAULT_RETENTION_DAYS = 90
MAX_DELETE_LIMIT = 5000

# Global dry-run mode flag
DRY_RUN_MODE = False

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

