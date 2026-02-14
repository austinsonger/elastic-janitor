# Complete List of AWS Firehose & ESF Issues

This document catalogs **all possible issues** that can occur when ingesting data from AWS Firehose and Elastic Serverless Forwarder (ESF) into Elasticsearch.

## 📊 Currently Detected Issues (by Elastic Janitor)

### ✅ Issue 1: Pipeline Failures (High Severity)
**Detection**: Documents tagged with `ingest_pipeline_failed`
**Cause**: Ingest pipeline processors failing during document processing
**Impact**: Data not properly parsed, enriched, or indexed
**Common Reasons**:
- Invalid JSON in message field
- Missing required fields for processors
- Type conversion errors
- Script processor failures
- Grok pattern mismatches

### ✅ Issue 2: CloudWatch Wrapper Issues (Medium Severity)
**Detection**: JSON in `aws.cloudwatch.message` not extracted to `message` field
**Cause**: CloudWatch wraps logs in JSON, but pipeline doesn't unwrap them
**Impact**: Nested JSON not properly parsed, logs not searchable
**Common Reasons**:
- Missing JSON processor in pipeline
- Incorrect target_field configuration
- CloudWatch message field not being processed

### ✅ Issue 3: Message Arrays (Medium Severity)
**Detection**: `message` field is an array instead of string
**Cause**: Firehose batching or incorrect field mapping
**Impact**: Logs stuck in array format, not searchable as text
**Common Reasons**:
- Firehose sending multiple messages in single document
- Incorrect pipeline handling of batched data
- Field mapping conflict (text vs array)

### ✅ Issue 4: Missing log.original (Low Severity)
**Detection**: CloudWatch logs without `log.original` field
**Cause**: Pipeline doesn't preserve original message before parsing
**Impact**: Cannot recover original message if parsing fails
**Common Reasons**:
- No `set` processor to copy message to log.original
- Processor runs after message is modified
- Pipeline doesn't follow ECS best practices

### ✅ Issue 5: Nested JSON Parsing (Medium Severity)
**Detection**: Patterns like `msg.msg`, `{\"msg\"`, `\"message\":\"` in message field
**Cause**: Multiple layers of JSON encoding/escaping
**Impact**: Nested JSON not properly flattened, fields not extracted
**Common Reasons**:
- Application logs JSON, CloudWatch wraps in JSON, Firehose wraps again
- Incorrect JSON processor configuration
- Missing recursive JSON parsing

### ✅ Issue 6: Duplicate Data (Low Severity)
**Detection**: Both `aws.cloudwatch.message` and `message` fields exist
**Cause**: Pipeline extracts message but doesn't remove source field
**Impact**: Wasted storage, potential confusion
**Common Reasons**:
- Missing `remove` processor after extraction
- `include_cw_extracted_fields: true` in Firehose config
- Pipeline doesn't clean up intermediate fields

---

## 🔍 Additional Issues NOT Currently Detected

### Category: Data Format & Parsing Issues

#### Issue 7: Base64 Encoded Messages (Medium Severity)
**Symptoms**: Message field contains base64-encoded data
**Cause**: CloudWatch or Firehose base64-encodes binary data
**Detection Query**:
```json
{
  "query": {
    "regexp": {
      "message": "^[A-Za-z0-9+/]+=*$"
    }
  }
}
```
**Fix**: Add decode processor in pipeline

#### Issue 8: Gzip Compressed Data (Medium Severity)
**Symptoms**: Binary/compressed data in message field
**Cause**: Firehose compression not properly handled
**Detection**: Check for binary characters in message field
**Fix**: Configure Firehose decompression or add pipeline processor

#### Issue 9: Multi-line Log Aggregation Issues (Medium Severity)
**Symptoms**: Stack traces or multi-line logs split across documents
**Cause**: CloudWatch/Firehose doesn't aggregate multi-line logs
**Detection**: Look for incomplete stack traces or partial messages
**Fix**: Use CloudWatch Logs subscription filter patterns or pipeline aggregation

#### Issue 10: Character Encoding Issues (Low Severity)
**Symptoms**: Garbled text, special characters corrupted
**Cause**: UTF-8 encoding issues in CloudWatch or Firehose
**Detection**: Search for replacement characters (�) or invalid UTF-8
**Fix**: Configure proper encoding in Firehose

#### Issue 11: Truncated Messages (Medium Severity)
**Symptoms**: Messages cut off mid-sentence
**Cause**: CloudWatch or Firehose message size limits
**Detection**: Messages ending abruptly, no closing brackets
**Fix**: Increase message size limits or split large messages

---

### Category: Timestamp & Date Issues

#### Issue 12: Missing @timestamp (High Severity)
**Symptoms**: Documents without `@timestamp` field
**Cause**: Timestamp parsing failure in pipeline
**Detection Query**:
```json
{
  "query": {
    "bool": {
      "must_not": {"exists": {"field": "@timestamp"}}
    }
  }
}
```
**Fix**: Add date processor with fallback to event.ingested

#### Issue 13: Incorrect Timezone (Medium Severity)
**Symptoms**: Timestamps off by hours
**Cause**: Timezone not specified in date processor
**Detection**: Compare @timestamp with aws.cloudwatch.ingestion_time
**Fix**: Add timezone parameter to date processor

#### Issue 14: Future Timestamps (Medium Severity)
**Symptoms**: Documents with timestamps in the future
**Cause**: Clock skew, incorrect date parsing
**Detection**: Query for @timestamp > now
**Fix**: Add validation and fallback in pipeline

#### Issue 15: Timestamp Precision Loss (Low Severity)
**Symptoms**: All timestamps rounded to seconds
**Cause**: Date format doesn't include milliseconds
**Detection**: All timestamps end in .000Z
**Fix**: Update date processor format to include milliseconds




---

### Category: Field Mapping & Structure Issues

#### Issue 16: Field Mapping Conflicts (High Severity)
**Symptoms**: Same field has different types across indices
**Cause**: Inconsistent data from different log sources
**Detection**: Use Elastic Janitor's Field Mapping Conflict Resolver
**Fix**: Reindex to common type or use runtime fields

#### Issue 17: Missing AWS Metadata Fields (Medium Severity)
**Symptoms**: Missing `aws.cloudwatch.log_group`, `log_stream`, or `aws.firehose.arn`
**Cause**: Firehose/ESF not configured to include metadata
**Detection Query**:
```json
{
  "query": {
    "bool": {
      "must": {"exists": {"field": "aws"}},
      "must_not": {"exists": {"field": "aws.cloudwatch.log_group"}}
    }
  }
}
```
**Fix**: Enable metadata in Firehose/ESF configuration

#### Issue 18: Flattened vs Nested Object Conflicts (Medium Severity)
**Symptoms**: Fields like `aws.cloudwatch.log_group` stored as `aws.cloudwatch.log.group`
**Cause**: Incorrect field name parsing or mapping
**Detection**: Check field names for unexpected dots
**Fix**: Update pipeline to use correct field names

#### Issue 19: ECS Field Violations (Low Severity)
**Symptoms**: Fields don't follow Elastic Common Schema (ECS)
**Cause**: Custom field names or incorrect mapping
**Detection**: Compare fields against ECS specification
**Fix**: Rename fields to match ECS or use custom namespace

#### Issue 20: Excessive Field Count (Medium Severity)
**Symptoms**: Indices with thousands of fields
**Cause**: Dynamic mapping creating fields for every unique key
**Detection**: Check index mapping field count
**Fix**: Disable dynamic mapping, use explicit mappings

---

### Category: Configuration Issues

#### Issue 21: CloudWatch Extracted Fields Enabled (Low Severity)
**Symptoms**: Duplicate fields like `extracted_fields.*`
**Cause**: `include_cw_extracted_fields: true` in Firehose config
**Detection Query**:
```json
{
  "query": {"exists": {"field": "extracted_fields"}}
}
```
**Fix**: Set `include_cw_extracted_fields: false` in Firehose

#### Issue 22: Wrong Index/Data Stream Target (High Severity)
**Symptoms**: Data going to wrong index pattern
**Cause**: Incorrect Firehose/ESF index configuration
**Detection**: Check index names don't match expected pattern
**Fix**: Update Firehose/ESF index name configuration

#### Issue 23: Missing Index Template (High Severity)
**Symptoms**: Incorrect field mappings, no ILM policy
**Cause**: Index template not created before data ingestion
**Detection**: Check if index has associated template
**Fix**: Create index template before ingesting data

#### Issue 24: Incorrect Buffer Settings (Medium Severity)
**Symptoms**: Very small or very large batches
**Cause**: Firehose buffer size/interval misconfigured
**Detection**: Check document batch sizes and timing
**Fix**: Tune Firehose buffer size (1-5 MB) and interval (60-300s)

#### Issue 25: Missing Error Handling (Medium Severity)
**Symptoms**: Failed documents silently dropped
**Cause**: No S3 backup or error logging configured
**Detection**: Compare CloudWatch log count vs Elasticsearch doc count
**Fix**: Enable S3 backup for failed documents in Firehose

---

### Category: Performance & Resource Issues

#### Issue 26: Ingestion Lag (High Severity)
**Symptoms**: Data delayed by minutes or hours
**Cause**: Firehose buffer settings, cluster overload, or throttling
**Detection**: Compare `@timestamp` with `event.ingested`
**Fix**: Reduce buffer interval, scale cluster, check throttling

#### Issue 27: Hot Shard Issues (High Severity)
**Symptoms**: Uneven shard distribution, slow queries
**Cause**: All data going to same shard (poor routing)
**Detection**: Check shard sizes and document distribution
**Fix**: Use better routing key or increase shard count

#### Issue 28: Memory Pressure from Large Documents (High Severity)
**Symptoms**: Cluster instability, OOM errors
**Cause**: Very large CloudWatch log messages
**Detection**: Check document sizes, look for >1MB docs
**Fix**: Add pipeline processor to truncate large messages

#### Issue 29: Pipeline Processing Overhead (Medium Severity)
**Symptoms**: Slow ingestion, high CPU usage
**Cause**: Complex pipeline with many processors
**Detection**: Monitor pipeline execution time
**Fix**: Optimize pipeline, remove unnecessary processors

#### Issue 30: Refresh Interval Too Aggressive (Low Severity)
**Symptoms**: High CPU, slow indexing
**Cause**: Default 1s refresh interval
**Detection**: Check index refresh settings
**Fix**: Increase refresh interval to 30s for bulk ingestion

---

### Category: Security & Permissions Issues

#### Issue 31: IAM Permission Errors (High Severity)
**Symptoms**: Firehose/ESF cannot write to Elasticsearch
**Cause**: Missing IAM permissions
**Detection**: Check Firehose/Lambda error logs
**Fix**: Add required permissions to IAM role

#### Issue 32: VPC/Network Connectivity Issues (High Severity)
**Symptoms**: Intermittent failures, timeouts
**Cause**: VPC configuration, security groups, or network ACLs
**Detection**: Check Firehose/Lambda network errors
**Fix**: Configure VPC endpoints, update security groups

#### Issue 33: API Key/Authentication Expiry (High Severity)
**Symptoms**: Sudden ingestion failure
**Cause**: Elasticsearch API key expired
**Detection**: Check authentication errors in logs
**Fix**: Rotate API keys, use IAM roles instead

#### Issue 34: Index Permissions (Medium Severity)
**Symptoms**: Cannot write to specific indices
**Cause**: Elasticsearch user lacks index write permissions
**Detection**: Check for 403 Forbidden errors
**Fix**: Grant write permissions to user/role

---

### Category: Cost & Storage Issues

#### Issue 35: Excessive Storage Usage (Medium Severity)
**Symptoms**: Rapid storage growth
**Cause**: Duplicate data, no ILM policy, or large messages
**Detection**: Monitor index sizes over time
**Fix**: Enable ILM, remove duplicates, compress data

#### Issue 36: No Data Lifecycle Management (Medium Severity)
**Symptoms**: Old data never deleted
**Cause**: No ILM policy attached to indices
**Detection**: Check for very old indices
**Fix**: Create and attach ILM policy

#### Issue 37: Firehose Data Transformation Costs (Low Severity)
**Symptoms**: High AWS bills for data transformation
**Cause**: Using Firehose data transformation Lambda
**Detection**: Check AWS billing for Lambda costs
**Fix**: Move transformation to Elasticsearch ingest pipeline

#### Issue 38: S3 Backup Storage Costs (Low Severity)
**Symptoms**: High S3 storage costs
**Cause**: S3 backup enabled but never cleaned up
**Detection**: Check S3 bucket size
**Fix**: Add S3 lifecycle policy to delete old backups


---

### Category: Data Quality Issues

#### Issue 39: Duplicate Documents (Medium Severity)
**Symptoms**: Same log appears multiple times
**Cause**: Firehose retries, no document ID deduplication
**Detection**: Search for duplicate `message` + `@timestamp`
**Fix**: Use fingerprint processor to generate document IDs

#### Issue 40: Missing Required Fields (Medium Severity)
**Symptoms**: Documents missing critical fields
**Cause**: Source logs incomplete or pipeline drops fields
**Detection**: Use Elastic Janitor's Data Quality Validator
**Fix**: Add validation and default values in pipeline

#### Issue 41: Invalid Field Values (Low Severity)
**Symptoms**: Fields with wrong data types or invalid values
**Cause**: No validation in pipeline
**Detection**: Check for type conversion errors
**Fix**: Add validation processors

#### Issue 42: Inconsistent Field Naming (Low Severity)
**Symptoms**: Same data in different field names
**Cause**: Multiple log sources with different formats
**Detection**: Check for similar fields with different names
**Fix**: Normalize field names in pipeline

---

### Category: Monitoring & Observability Issues

#### Issue 43: No Ingestion Monitoring (High Severity)
**Symptoms**: Don't know when ingestion fails
**Cause**: No CloudWatch alarms or monitoring
**Detection**: Manual checks required
**Fix**: Set up CloudWatch alarms for Firehose metrics

#### Issue 44: Missing Error Logs (Medium Severity)
**Symptoms**: Cannot troubleshoot failures
**Cause**: CloudWatch Logs not enabled for Firehose/Lambda
**Detection**: No logs in CloudWatch
**Fix**: Enable error logging in Firehose/ESF configuration

#### Issue 45: Stale Data Streams (Medium Severity)
**Symptoms**: Data streams receiving no new data
**Cause**: Log source stopped, Firehose misconfigured
**Detection**: Use Elastic Janitor's Firehose/Forwarder Health Check
**Fix**: Investigate log source, check Firehose configuration

#### Issue 46: No Alerting on Pipeline Failures (High Severity)
**Symptoms**: Pipeline failures go unnoticed
**Cause**: No monitoring of `ingest_pipeline_failed` tag
**Detection**: Manual checks required
**Fix**: Create Elasticsearch watcher or external monitoring

---

### Category: Kubernetes/Container-Specific Issues (ESF)

#### Issue 47: Missing Kubernetes Metadata (Medium Severity)
**Symptoms**: No pod name, namespace, or container info
**Cause**: ESF not configured to enrich with K8s metadata
**Detection**: Check for missing `kubernetes.*` fields
**Fix**: Enable Kubernetes metadata enrichment in ESF

#### Issue 48: Container Log Multiline Issues (Medium Severity)
**Symptoms**: Stack traces split across documents
**Cause**: Container runtime splits logs at newlines
**Detection**: Incomplete stack traces
**Fix**: Configure multiline parsing in ESF or pipeline

#### Issue 49: Pod Restart Log Loss (High Severity)
**Symptoms**: Missing logs during pod restarts
**Cause**: ESF buffer not flushed before pod termination
**Detection**: Gaps in logs during pod lifecycle events
**Fix**: Configure graceful shutdown, reduce buffer time

---

## 🎯 Detection Priority Recommendations

### Should Add to Elastic Janitor (High Priority)

1. **Missing @timestamp** (Issue 12) - Critical for time-series data
2. **Field Mapping Conflicts** (Issue 16) - Already have resolver, add to detection
3. **Ingestion Lag** (Issue 26) - Important for real-time monitoring
4. **Duplicate Documents** (Issue 39) - Wastes storage and skews metrics
5. **Stale Data Streams** (Issue 45) - Already have health check, integrate better
6. **Base64 Encoded Messages** (Issue 7) - Common issue, easy to detect

### Medium Priority

7. **CloudWatch Extracted Fields** (Issue 21) - Already checked in Field Structure Analysis
8. **Excessive Field Count** (Issue 20) - Storage and performance impact
9. **Missing AWS Metadata** (Issue 17) - Data quality issue
10. **Truncated Messages** (Issue 11) - Data loss issue

### Lower Priority (Edge Cases)

- Character encoding issues
- Timezone problems
- Cost optimization issues
- Monitoring gaps

---

## 📋 Summary Statistics

- **Total Issues Cataloged**: 49
- **Currently Detected**: 6 (12%)
- **High Severity**: 15 issues
- **Medium Severity**: 24 issues
- **Low Severity**: 10 issues

**Categories**:
- Data Format & Parsing: 9 issues
- Timestamp & Date: 4 issues
- Field Mapping & Structure: 5 issues
- Configuration: 5 issues
- Performance & Resource: 5 issues
- Security & Permissions: 4 issues
- Cost & Storage: 4 issues
- Data Quality: 4 issues
- Monitoring & Observability: 4 issues
- Kubernetes/Container: 3 issues
- Currently Detected: 6 issues

---

## 🚀 Next Steps

To improve Elastic Janitor's detection capabilities, consider adding checks for:

1. **Missing @timestamp** - Critical issue, easy to detect
2. **Ingestion lag** - Compare @timestamp vs event.ingested
3. **Duplicate documents** - Use aggregations to find duplicates
4. **Base64 encoded data** - Regex pattern matching
5. **Excessive field count** - Check mapping field count
6. **Missing AWS metadata** - Check for required aws.* fields

These additions would increase detection coverage from 12% to ~25% of all possible issues.

---

## 📖 How to Use This Guide

1. **For Current Issues**: Check the "Currently Detected Issues" section for problems Elastic Janitor already finds
2. **For Troubleshooting**: Search for your symptoms in the additional issues sections
3. **For Prevention**: Review all categories to understand potential problems
4. **For Monitoring**: Use the detection queries to create custom alerts

Each issue includes:
- **Symptoms**: How to recognize the problem
- **Cause**: Why it happens
- **Detection**: How to find it (query or tool)
- **Fix**: How to resolve it

---

## 🔗 Related Tools in Elastic Janitor

- **Common Issue Detection**: Detects issues 1-6 automatically
- **Pipeline Troubleshooting**: Helps diagnose pipeline failures
- **Field Structure Analysis**: Validates AWS metadata fields
- **Firehose/Forwarder Health Check**: Detects stale data streams
- **Field Mapping Conflict Resolver**: Fixes field type conflicts
- **Data Quality Validator**: Checks for missing required fields
- **Bulk Reindex**: Fixes failed documents after pipeline corrections
