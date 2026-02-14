# Elastic Janitor - AWS Ingestion Improvements Summary

## 🎉 What's New

### 1. Actionable Issue Detection Output

**Before:**
```
⚠️  Found 2 issue type(s)

Recommended actions:
• Review pipeline configurations
• Check CloudWatch field extraction settings
• Use Pipeline Troubleshooting to identify specific processor failures
```

**After:**
```
⚠️  2 HIGH SEVERITY issue(s) detected!

Total affected documents: 20,000

📋 Step-by-Step Fix Guide:

For Pipeline Failures:
  1. Go to: Pipeline Troubleshooting → View failing processors
  2. Go to: Template & Policy Management → Edit Pipeline → Fix processors
  3. Go to: Quick Fixes & Actions → 🔄 Bulk Reindex Failed Documents → Reprocess

For Missing log.original:
  1. Go to: Template & Policy Management → Edit Pipeline
  2. Add 'set' processor to copy message to log.original
  3. See: example_pipeline_with_log_original.json for reference
  4. Go to: Quick Fixes & Actions → 🔄 Bulk Reindex → Reprocess existing docs

💡 Tip: See AWS_INGESTION_FIXES_GUIDE.md for detailed instructions

What would you like to do next?

❯ 🔍 View Pipeline Troubleshooting (identify failing processors)
  🔄 Go to Bulk Reindex (fix failed documents)
  ✏️  Edit Pipeline Configuration
  📤 Export Failed Logs for Analysis
  ─────────────────────────────────
  📖 View Complete Fix Guide (AWS_INGESTION_FIXES_GUIDE.md)
  ← Return to AWS Ingestion Menu
```

### 2. Context-Aware Recommendations

The tool now:
- ✅ Detects which specific issues you have
- ✅ Shows only relevant fix steps for YOUR issues
- ✅ Provides exact menu paths to navigate
- ✅ Offers interactive shortcuts to jump directly to the right tool

### 3. Interactive Quick Actions

After detecting issues, you can immediately:
- Jump to **Pipeline Troubleshooting** to see what's failing
- Jump to **Bulk Reindex** to fix failed documents
- View guidance on editing pipelines
- Export failed logs for detailed analysis
- View the complete fix guide

### 4. Smart Issue-Specific Guidance

**For Pipeline Failures:**
- Direct link to Pipeline Troubleshooting
- Direct link to Edit Pipeline
- Direct link to Bulk Reindex

**For Missing log.original:**
- Shows how to add the processor
- References example configuration file
- Links to bulk reindex for existing docs

**For Nested JSON Issues:**
- Suggests exporting logs to examine structure
- Explains how to add JSON processor
- Links to bulk reindex

## 🚀 How to Use

1. **Run Common Issue Detection:**
   ```
   Main Menu → AWS Ingestion Management → Common Issue Detection
   ```

2. **Review the issues** in the table

3. **Read the step-by-step guide** tailored to your specific issues

4. **Select a quick action** from the interactive menu:
   - Jump directly to the tool you need
   - Or return to the menu to navigate manually

## 📊 Example Workflow

### Scenario: You have 10,000 failed documents

**Step 1:** Run Common Issue Detection
- Detects "Pipeline Failures" (High Severity)
- Shows 10,000 affected documents

**Step 2:** Review the actionable guide
```
For Pipeline Failures:
  1. Go to: Pipeline Troubleshooting → View failing processors
  2. Go to: Template & Policy Management → Edit Pipeline → Fix processors
  3. Go to: Quick Fixes & Actions → 🔄 Bulk Reindex Failed Documents → Reprocess
```

**Step 3:** Select quick action
- Choose "🔍 View Pipeline Troubleshooting"
- Tool automatically navigates there
- You see which processors are failing

**Step 4:** Fix the pipeline
- Navigate to Edit Pipeline (or use the guide)
- Add/fix the failing processor
- Test with sample document

**Step 5:** Reindex failed documents
- Return to Common Issue Detection
- Select "🔄 Go to Bulk Reindex"
- Tool automatically reprocesses all 10,000 documents
- Shows detailed results

**Step 6:** Verify the fix
- Run Common Issue Detection again
- Confirm failures are eliminated

## 🎯 Key Benefits

1. **No More Guessing**: Exact menu paths for every action
2. **Faster Fixes**: Jump directly to the right tool
3. **Context-Aware**: Only see recommendations for YOUR issues
4. **Complete Guidance**: Step-by-step instructions from detection to resolution
5. **Interactive**: One-click navigation to the tools you need

## 📝 Files Modified

- `janitor/operations/aws_ingestion_diagnostics.py`
  - Enhanced issue detection output
  - Added context-aware recommendations
  - Added interactive quick actions menu
  - Integrated with existing tools

- `AWS_INGESTION_FIXES_GUIDE.md`
  - Added Quick Start section
  - Updated with new interactive features

## 🔧 Technical Details

### Issue Detection Logic

The tool now:
1. Detects which specific issues are present
2. Builds custom recommendations based on detected issues
3. Offers relevant quick actions
4. Provides direct navigation to tools

### Quick Actions Integration

- **Pipeline Troubleshooting**: Calls `option_pipeline_troubleshooting(es)`
- **Bulk Reindex**: Calls `_bulk_reindex_failed_documents(es)`
- **Edit Pipeline**: Shows navigation instructions
- **Export Logs**: Shows navigation instructions
- **View Guide**: Displays guide preview

## 🎓 User Experience Improvements

**Before**: Users had to:
1. Read generic recommendations
2. Remember menu paths
3. Navigate manually through menus
4. Figure out which tool to use

**After**: Users can:
1. See specific steps for their issues
2. Click to jump directly to the right tool
3. Follow a clear, linear workflow
4. Get immediate help at every step

## 🚦 Next Steps

The improvements are ready to use! Just run:
```
Main Menu → AWS Ingestion Management → Common Issue Detection
```

And follow the on-screen guidance to fix your issues.

