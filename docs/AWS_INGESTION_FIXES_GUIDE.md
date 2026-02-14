# AWS Ingestion Issues - Complete Fix Guide

This guide provides step-by-step instructions for fixing the AWS ingestion issues detected in your Elastic cluster.

## 🎯 Quick Start

After running **Common Issue Detection**, you'll now see:
1. **Specific issues detected** with severity levels
2. **Step-by-step fix guide** tailored to your specific issues
3. **Interactive menu** to jump directly to the right tool

Just follow the on-screen prompts to fix your issues!

## Issues Detected

1. **Pipeline Failures (High Severity)**: 10,000 documents with 'ingest_pipeline_failed' tag
2. **Missing log.original (Low Severity)**: 10,000 CloudWatch logs missing the log.original fallback field
3. **Nested JSON Timeout**: The nested JSON check timed out during scanning

## New Features Implemented

### 1. Bulk Reindex Feature ✅
**Location**: `Main Menu → AWS Ingestion Management → Quick Fixes & Actions → 🔄 Bulk Reindex Failed Documents`

**What it does**:
- Automatically reindexes failed documents through a corrected pipeline
- Removes the 'ingest_pipeline_failed' tag
- Cleans up error fields
- Provides detailed progress and results

**How to use**:
1. Fix your ingest pipeline first (see section below)
2. Navigate to Quick Fixes & Actions
3. Select "🔄 Bulk Reindex Failed Documents"
4. Enter your index pattern (e.g., `logs-aws.cloudwatch-*`)
5. Enter the corrected pipeline name
6. Confirm and execute

### 2. Sophisticated Timeout Configuration ✅
**Location**: `janitor/config.py`

**New timeout settings**:
```python
DEFAULT_QUERY_TIMEOUT = 30      # Default timeout for queries (seconds)
SLOW_QUERY_TIMEOUT = 60         # Timeout for slow queries like wildcards (seconds)
REQUEST_TIMEOUT = 90            # Client-side request timeout (seconds)
REINDEX_TIMEOUT = 300           # Reindex operation timeout (5 minutes)
```

**Benefits**:
- Prevents queries from hanging indefinitely
- Configurable timeouts for different operation types
- Better error handling and user feedback

### 3. Efficient Nested JSON Detection ✅
**Location**: `Main Menu → AWS Ingestion Management → Common Issue Detection`

**Improvements**:
- **Fast Mode Option**: Skip slow wildcard queries entirely
- **Sampling Approach**: Instead of scanning all documents, samples 1,000 recent documents
- **Extrapolation**: Estimates total nested JSON issues from sample
- **Timeout Handling**: Gracefully handles timeouts with warnings

**Old approach** (slow):
- Used wildcard queries: `{"wildcard": {"message": "*msg.msg*"}}`
- Scanned all 873 indices
- Frequently timed out on large datasets

**New approach** (fast):
- Samples 1,000 recent documents
- Analyzes message content in application code
- Extrapolates to estimate total issues
- Completes in seconds instead of minutes

## Step-by-Step Fix Workflow

### Phase 1: Fix the Ingest Pipeline

#### Step 1: View Current Pipeline Configuration
```
Main Menu → AWS Ingestion Management → Pipeline Troubleshooting
```
- Select your index pattern: `logs-aws.cloudwatch-*`
- Note the pipeline name(s) that need fixing

#### Step 2: Edit the Pipeline
```
Main Menu → Template & Policy Management → Edit Pipeline
```
- Select the failing pipeline
- Add the `log.original` processor at the beginning

**Example Pipeline Configuration**:
See `example_pipeline_with_log_original.json` for a complete example.

**Key Processors to Add**:
```json
{
  "set": {
    "description": "Preserve original message before parsing",
    "field": "log.original",
    "copy_from": "message",
    "override": false,
    "ignore_failure": true
  }
}
```

#### Step 3: Test the Pipeline
- When prompted "Test pipeline with sample document?" → Select Yes
- Use a sample CloudWatch document (see example below)
- Verify the output includes `log.original` field

**Sample Test Document**:
```json
{
  "message": "{\"level\":\"INFO\",\"msg\":\"Application started\"}",
  "@timestamp": "2024-01-01T00:00:00Z",
  "aws": {
    "cloudwatch": {
      "log_group": "/aws/lambda/my-function",
      "log_stream": "2024/01/01/[$LATEST]abc123"
    }
  }
}
```

#### Step 4: Save the Pipeline
- Confirm the changes
- The pipeline is now updated and will apply to new documents

### Phase 2: Reprocess Failed Documents

#### Step 5: Run Bulk Reindex
```
Main Menu → AWS Ingestion Management → Quick Fixes & Actions → 🔄 Bulk Reindex Failed Documents
```

**Configuration**:
- Source Index: `logs-aws.cloudwatch-*` (or your specific pattern)
- Target Index: Same as source (or specify different)
- Pipeline: Your corrected pipeline name
- Documents: 10,000 (automatically detected)

**What happens**:
1. Counts failed documents
2. Verifies pipeline exists
3. Shows configuration summary
4. Reindexes documents through corrected pipeline
5. Removes 'ingest_pipeline_failed' tag
6. Cleans up error fields
7. Shows detailed results

**Expected Results**:
```
✅ Reindex completed!

Reindex Results
┌──────────────────┬────────┐
│ Metric           │  Count │
├──────────────────┼────────┤
│ Total Processed  │ 10,000 │
│ Created          │      0 │
│ Updated          │ 10,000 │
│ Deleted          │      0 │
│ Failures         │      0 │
└──────────────────┴────────┘
```

### Phase 3: Verify the Fix

#### Step 6: Run Common Issue Detection Again
```
Main Menu → AWS Ingestion Management → Common Issue Detection
```
- Select "Use fast mode?" → Yes (to skip slow queries)
- Verify pipeline failures are reduced or eliminated
- Verify log.original fields are now present

#### Step 7: Check Data Quality Metrics
```
Main Menu → AWS Ingestion Management → Data Quality Metrics
```
- Analyze last 24 hours
- Verify success rate has improved
- Monitor failure rates by log group

## Troubleshooting

### Issue: Reindex Times Out
**Solution**: The timeout is set to 300 seconds (5 minutes). If you have more than 10,000 documents:
1. Use a more specific index pattern to process smaller batches
2. Increase `REINDEX_TIMEOUT` in `janitor/config.py`
3. Process documents in smaller time windows

### Issue: Pipeline Still Failing
**Solution**:
1. Export failed logs: `Quick Fixes & Actions → Export Failed Logs`
2. Examine the structure of failed documents
3. Use Pipeline Troubleshooting to view processor details
4. Test pipeline with actual failed documents
5. Adjust pipeline configuration as needed

### Issue: Nested JSON Check Still Times Out
**Solution**:
1. Use "Fast mode" when running Common Issue Detection
2. Use more specific index patterns (e.g., `logs-aws.cloudwatch-default` instead of `*`)
3. The new sampling approach should prevent most timeouts

## Configuration Reference

### Timeout Settings (`janitor/config.py`)
```python
DEFAULT_QUERY_TIMEOUT = 30      # Adjust for slower clusters
SLOW_QUERY_TIMEOUT = 60         # For wildcard/regex queries
REQUEST_TIMEOUT = 90            # Client-side timeout
REINDEX_TIMEOUT = 300           # Increase for large reindex operations
```

### Fast Mode
When enabled, skips:
- Nested JSON wildcard queries (uses sampling instead)
- Other slow pattern-matching queries

## Next Steps

1. ✅ Fix pipeline configuration
2. ✅ Run bulk reindex
3. ✅ Verify results
4. 📊 Monitor ongoing ingestion
5. 🔔 Set up alerts for future failures (optional)

## Additional Resources

- `example_pipeline_with_log_original.json` - Complete pipeline example
- `reindex_failed_documents.py` - Standalone reindex script (alternative to menu option)
- Elastic Janitor documentation in `README.md`

