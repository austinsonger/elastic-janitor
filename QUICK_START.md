# Quick Start Guide

## Installation

### 1. Navigate to the Repository
```bash
cd /Users/austin-songer/code/elastic-janitor
```

### 2. Create a Virtual Environment (Recommended)
```bash
python3 -m venv venv
source venv/bin/activate  # On macOS/Linux
# On Windows: venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Configuration

### Update Elasticsearch Credentials
Edit `janitor/config.py` and update the following:

```python
ELASTIC_URL = "https://your-elasticsearch-cluster:9243"
ELASTIC_API_KEY = "your-api-key-here"
```

**Security Note:** For production use, consider using environment variables:

```python
import os
ELASTIC_URL = os.getenv('ELASTIC_URL', 'https://default-url')
ELASTIC_API_KEY = os.getenv('ELASTIC_API_KEY', '')
```

Then set environment variables:
```bash
export ELASTIC_URL="https://your-elasticsearch-cluster:9243"
export ELASTIC_API_KEY="your-api-key-here"
```

## Running Elastic Janitor

You have three options to run the application:

### Option 1: As a Python Module (Recommended)
```bash
python -m janitor
```

### Option 2: Direct Execution
```bash
python janitor/__main__.py
```

### Option 3: Using the Launcher Script
```bash
python run.py
```

Or make it executable:
```bash
chmod +x run.py
./run.py
```

## First-Time Setup Checklist

- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Elasticsearch credentials configured in `janitor/config.py`
- [ ] Application runs successfully
- [ ] Dry-run mode tested (toggle in Cluster Health menu)

## Common Tasks

### Enable Dry-Run Mode
1. Run the application
2. Navigate to: `Cluster Health & Diagnostics`
3. Select: `Toggle Dry-Run Mode`
4. Confirm the mode is enabled (you'll see a warning banner)

### Clean Old Data Streams
1. Run the application
2. Navigate to: `Data Streams`
3. Select: `Clean Data Streams`
4. Follow the prompts

### View Cluster Health
1. Run the application
2. Navigate to: `Cluster Health & Diagnostics`
3. Select: `Cluster Health Overview`

## Safety Features

### Dry-Run Mode
- **Always test with dry-run mode first!**
- Shows what would be deleted without actually deleting
- Toggle from Cluster Health menu

### System Index Protection
- System indices (starting with `.`) are protected by default
- Configure via `PROTECT_SYSTEM` in `config.py`

### Confirmation Prompts
- All destructive operations require explicit confirmation
- Review carefully before confirming

### Operation Limits
- Maximum deletion limits prevent accidental bulk deletions
- Configure via `MAX_DELETE_LIMIT` in `config.py` (default: 5000)

## Troubleshooting

### Import Errors
**Problem:** `ModuleNotFoundError: No module named 'janitor'`

**Solution:** Ensure you're running from the repository root:
```bash
cd /Users/austin-songer/code/elastic-janitor
python -m janitor
```

### Missing Dependencies
**Problem:** `ModuleNotFoundError: No module named 'rich'` (or other packages)

**Solution:** Install dependencies:
```bash
pip install -r requirements.txt
```

### Connection Errors
**Problem:** Cannot connect to Elasticsearch

**Solution:** 
1. Verify `ELASTIC_URL` in `janitor/config.py`
2. Verify `ELASTIC_API_KEY` is correct
3. Check network connectivity
4. Verify Elasticsearch cluster is running

### Permission Errors
**Problem:** `403 Forbidden` or permission denied errors

**Solution:**
1. Verify your API key has sufficient permissions
2. Check if you're trying to modify system indices (protected by default)

## Development

### Install Development Dependencies
```bash
pip install -r requirements-dev.txt  # If available
# Or install manually:
pip install pytest pytest-cov black flake8 mypy
```

### Run Tests
```bash
pytest
```

### Format Code
```bash
black .
```

### Type Checking
```bash
mypy janitor/
```

## Next Steps

1. **Set up a remote repository** (e.g., on GitHub):
   ```bash
   git remote add origin <your-remote-url>
   git push -u origin main
   ```

2. **Create a `.env` file** for sensitive configuration:
   ```bash
   echo "ELASTIC_URL=https://your-cluster:9243" > .env
   echo "ELASTIC_API_KEY=your-key" >> .env
   echo ".env" >> .gitignore
   ```

3. **Install in development mode** for easier testing:
   ```bash
   pip install -e .
   ```

4. **Set up CI/CD** for automated testing

5. **Add more tests** to ensure code quality

## Getting Help

- See [README.md](README.md) for comprehensive documentation
- See [MIGRATION.md](MIGRATION.md) for migration details
- See [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) for code structure

## Version Information

- **Current Version:** 2.0.0
- **Python Required:** 3.8 or higher
- **Elasticsearch Compatibility:** 8.0.0 or higher

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
