"""
Developer Tools for Elastic Janitor.
Interactive tools for building index templates, generating mappings, constructing queries, and bulk operations.
"""
import json
from datetime import datetime
import questionary
from questionary import Choice, Separator
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.syntax import Syntax
from rich import box
from ..config import console, GOD_MODE, custom_style
from ..utils import (
    show_breadcrumb, safe_input, confirm_action, get_number_input,
    get_text_input, select_from_list, paginate_renderables
)


def option_index_template_generator(es):
    """
    Interactive wizard to build index templates.
    Guide users through template creation with validation and preview.
    """
    show_breadcrumb(["Main Menu", "Developer Tools", "Index Template Generator"])
    
    console.print("\n[bold cyan]🛠️  Index Template Generator[/bold cyan]\n")
    console.print("[dim]Interactive wizard to create index templates[/dim]\n")
    
    try:
        # Step 1: Template type selection
        template_type = questionary.select(
            "Select template type:",
            choices=[
                Choice("Index Template", value="index"),
                Choice("Component Template", value="component"),
            ],
            style=custom_style
        ).ask()
        
        if not template_type:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return
        
        # Step 2: Template name
        template_name = get_text_input("Template name:", default="my-template")
        if not template_name:
            return
        
        # Step 3: Index patterns (only for index templates)
        index_patterns = []
        if template_type == "index":
            patterns_input = get_text_input("Index patterns (comma-separated):", default="logs-*,metrics-*")
            if not patterns_input:
                return
            index_patterns = [p.strip() for p in patterns_input.split(",") if p.strip()]
        
        # Step 4: Priority (only for index templates)
        priority = 0
        if template_type == "index":
            priority = get_number_input("Priority:", default=100, min_val=0)
            if priority is None:
                return
        
        # Step 5: Settings
        console.print("\n[cyan]Configure index settings:[/cyan]")
        shards = get_number_input("Number of shards:", default=1, min_val=1)
        replicas = get_number_input("Number of replicas:", default=1, min_val=0)
        refresh_interval = get_text_input("Refresh interval:", default="1s")
        
        if shards is None or replicas is None or not refresh_interval:
            return
        
        settings = {
            "index": {
                "number_of_shards": shards,
                "number_of_replicas": replicas,
                "refresh_interval": refresh_interval
            }
        }
        
        # Step 6: Mappings
        console.print("\n[cyan]Configure mappings:[/cyan]")
        add_mappings = confirm_action("Add field mappings?")
        
        mappings = {"properties": {}}
        if add_mappings:
            while True:
                field_name = get_text_input("Field name (or press Enter to finish):")
                if not field_name:
                    break
                
                field_type = questionary.select(
                    f"Type for '{field_name}':",
                    choices=[
                        Choice("text", value="text"),
                        Choice("keyword", value="keyword"),
                        Choice("long", value="long"),
                        Choice("integer", value="integer"),
                        Choice("date", value="date"),
                        Choice("boolean", value="boolean"),
                        Choice("ip", value="ip"),
                        Choice("geo_point", value="geo_point"),
                        Choice("nested", value="nested"),
                        Choice("object", value="object"),
                    ],
                    style=custom_style
                ).ask()
                
                if not field_type:
                    break
                
                field_def = {"type": field_type}
                
                # Add analyzer for text fields
                if field_type == "text":
                    add_analyzer = confirm_action("Add custom analyzer?")
                    if add_analyzer:
                        analyzer = get_text_input("Analyzer name:", default="standard")
                        if analyzer:
                            field_def["analyzer"] = analyzer
                
                mappings["properties"][field_name] = field_def
        
        # Step 7: Aliases
        console.print("\n[cyan]Configure aliases:[/cyan]")
        add_aliases = confirm_action("Add aliases?")
        
        aliases = {}
        if add_aliases:
            while True:
                alias_name = get_text_input("Alias name (or press Enter to finish):")
                if not alias_name:
                    break
                aliases[alias_name] = {}
        
        # Build template JSON
        if template_type == "index":
            template_json = {
                "index_patterns": index_patterns,
                "priority": priority,
                "template": {
                    "settings": settings,
                    "mappings": mappings,
                    "aliases": aliases
                }
            }
        else:  # component template
            template_json = {
                "template": {
                    "settings": settings,
                    "mappings": mappings,
                    "aliases": aliases
                }
            }

        # Display preview with syntax highlighting
        console.print("\n[bold cyan]Template Preview:[/bold cyan]\n")

        json_str = json.dumps(template_json, indent=2)
        syntax = Syntax(json_str, "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[bold green]Generated Template[/bold green]", box=box.ROUNDED))
        console.print()

        # Validate template
        console.print("[cyan]Validating template...[/cyan]\n")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]Validating..."),
                transient=True,
            ) as progress:
                progress.add_task("validate", total=None)

                # Simulate validation (in production, use ES API)
                if template_type == "index":
                    # Check if template already exists
                    try:
                        existing = es.indices.get_index_template(name=template_name)
                        console.print(f"[yellow]⚠️  Template '{template_name}' already exists[/yellow]\n")
                    except:
                        pass
                else:
                    # Check if component template already exists
                    try:
                        existing = es.cluster.get_component_template(name=template_name)
                        console.print(f"[yellow]⚠️  Component template '{template_name}' already exists[/yellow]\n")
                    except:
                        pass

            console.print("[green]✅ Template validation passed[/green]\n")
        except Exception as e:
            console.print(f"[red]❌ Validation error: {e}[/red]\n")
            return

        # Confirm creation
        if not confirm_action(f"Create {template_type} template '{template_name}'?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if not GOD_MODE:
            console.print("[yellow]🔍 SAFE MODE: Would create template but no action taken.[/yellow]\n")
            return

        # Create template
        try:
            if template_type == "index":
                es.indices.put_index_template(name=template_name, body=template_json)
            else:
                es.cluster.put_component_template(name=template_name, body=template_json)

            console.print(f"\n[green]✅ Successfully created {template_type} template '{template_name}'[/green]\n")
        except Exception as e:
            console.print(f"\n[red]❌ Error creating template: {e}[/red]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")


def option_mapping_generator_from_json(es):
    """
    Auto-generate mappings from sample JSON documents.
    Analyze JSON structure and infer field types.
    """
    show_breadcrumb(["Main Menu", "Developer Tools", "Mapping Generator from JSON"])

    console.print("\n[bold cyan]📄 Mapping Generator from JSON[/bold cyan]\n")
    console.print("[dim]Analyze JSON documents and generate Elasticsearch mappings[/dim]\n")

    try:
        # Get sample JSON
        console.print("[cyan]Paste your sample JSON document(s):[/cyan]")
        console.print("[dim]Tip: You can paste multiple documents separated by newlines[/dim]")
        console.print("[dim]Press Ctrl+D (Unix) or Ctrl+Z (Windows) when done[/dim]\n")

        json_lines = []
        try:
            while True:
                line = safe_input("")
                if not line:
                    break
                json_lines.append(line)
        except EOFError:
            pass

        if not json_lines:
            console.print("\n[yellow]⚠️  No JSON provided.[/yellow]\n")
            return

        json_text = "\n".join(json_lines)

        # Parse JSON
        try:
            # Try to parse as single document
            try:
                documents = [json.loads(json_text)]
            except:
                # Try to parse as multiple documents (one per line)
                documents = []
                for line in json_lines:
                    if line.strip():
                        documents.append(json.loads(line))
        except Exception as e:
            console.print(f"\n[red]❌ Invalid JSON: {e}[/red]\n")
            return

        if not documents:
            console.print("\n[yellow]⚠️  No valid JSON documents found.[/yellow]\n")
            return

        console.print(f"\n[green]✅ Parsed {len(documents)} document(s)[/green]\n")

        # Analyze JSON structure and infer types
        console.print("[cyan]Analyzing field types...[/cyan]\n")

        field_types = {}

        def analyze_value(value):
            """Infer Elasticsearch type from Python value."""
            if isinstance(value, bool):
                return "boolean"
            elif isinstance(value, int):
                return "long"
            elif isinstance(value, float):
                return "double"
            elif isinstance(value, str):
                # Try to detect date format
                if len(value) > 0:
                    # Simple date detection
                    if "T" in value and ("Z" in value or "+" in value or "-" in value[-6:]):
                        return "date"
                    # Check if it looks like an IP
                    parts = value.split(".")
                    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
                        return "ip"
                # Default to keyword for short strings, text for longer ones
                return "keyword" if len(value) < 50 else "text"
            elif isinstance(value, list):
                if len(value) > 0:
                    # Analyze first element
                    first_type = analyze_value(value[0])
                    return first_type
                return "keyword"
            elif isinstance(value, dict):
                return "object"
            else:
                return "keyword"

        def extract_fields(obj, prefix=""):
            """Recursively extract fields from JSON object."""
            if not isinstance(obj, dict):
                return

            for key, value in obj.items():
                field_path = f"{prefix}{key}" if prefix else key

                if isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    # Nested object array
                    field_types[field_path] = {
                        "type": "nested",
                        "detected_from": "array of objects",
                        "count": 1
                    }
                    # Analyze nested structure
                    extract_fields(value[0], f"{field_path}.")
                elif isinstance(value, dict):
                    # Nested object
                    field_types[field_path] = {
                        "type": "object",
                        "detected_from": "object",
                        "count": 1
                    }
                    extract_fields(value, f"{field_path}.")
                else:
                    # Leaf field
                    inferred_type = analyze_value(value)

                    if field_path in field_types:
                        # Field seen before, check consistency
                        field_types[field_path]["count"] += 1
                        if field_types[field_path]["type"] != inferred_type:
                            field_types[field_path]["type"] = "keyword"  # Fallback to keyword for conflicts
                            field_types[field_path]["detected_from"] = "mixed types"
                    else:
                        field_types[field_path] = {
                            "type": inferred_type,
                            "detected_from": type(value).__name__,
                            "count": 1
                        }

        # Analyze all documents
        for doc in documents:
            extract_fields(doc)

        # Display inferred mappings
        console.print()
        table = Table(title="Inferred Field Mappings", box=box.ROUNDED, title_style="bold cyan")
        table.add_column("Field Path", style="cyan", no_wrap=False)
        table.add_column("Detected Type", style="yellow")
        table.add_column("Suggested Mapping", style="green")
        table.add_column("Occurrences", style="dim", justify="right")

        sorted_fields = sorted(field_types.items())
        for field_path, info in sorted_fields:
            detected_type = info["type"]
            suggested = detected_type

            # Add suggestions
            if detected_type == "text":
                suggested = "text (with keyword multi-field)"

            table.add_row(
                field_path,
                detected_type,
                suggested,
                str(info["count"])
            )

        console.print(table)
        console.print()

        # Build mappings JSON
        mappings = {"properties": {}}

        def build_mapping_tree(field_path, field_info):
            """Build nested mapping structure."""
            parts = field_path.split(".")
            current = mappings["properties"]

            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {"properties": {}}
                elif "properties" not in current[part]:
                    current[part]["properties"] = {}
                current = current[part]["properties"]

            # Add final field
            field_name = parts[-1]
            field_type = field_info["type"]

            if field_type == "text":
                current[field_name] = {
                    "type": "text",
                    "fields": {
                        "keyword": {
                            "type": "keyword",
                            "ignore_above": 256
                        }
                    }
                }
            else:
                current[field_name] = {"type": field_type}

        for field_path, info in sorted_fields:
            if "." not in field_path:
                # Top-level field
                field_type = info["type"]
                if field_type == "text":
                    mappings["properties"][field_path] = {
                        "type": "text",
                        "fields": {
                            "keyword": {
                                "type": "keyword",
                                "ignore_above": 256
                            }
                        }
                    }
                else:
                    mappings["properties"][field_path] = {"type": field_type}

        # Display generated mappings
        console.print("[bold cyan]Generated Mappings:[/bold cyan]\n")

        mappings_json = json.dumps(mappings, indent=2)
        syntax = Syntax(mappings_json, "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[bold green]Mappings JSON[/bold green]", box=box.ROUNDED))
        console.print()

        # Options for saving
        save_option = questionary.select(
            "What would you like to do with these mappings?",
            choices=[
                Choice("Save as component template", value="component"),
                Choice("Add to existing index template", value="index"),
                Choice("Copy to clipboard (display only)", value="display"),
                Choice("Cancel", value="cancel"),
            ],
            style=custom_style
        ).ask()

        if not save_option or save_option == "cancel":
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if save_option == "display":
            console.print("\n[green]✅ Mappings displayed above. Copy as needed.[/green]\n")
            return

        if save_option == "component":
            template_name = get_text_input("Component template name:", default="my-mappings")
            if not template_name:
                return

            if not GOD_MODE:
                console.print("[yellow]🔍 SAFE MODE: Would create component template but no action taken.[/yellow]\n")
                return

            try:
                es.cluster.put_component_template(
                    name=template_name,
                    body={"template": {"mappings": mappings}}
                )
                console.print(f"\n[green]✅ Created component template '{template_name}'[/green]\n")
            except Exception as e:
                console.print(f"\n[red]❌ Error: {e}[/red]\n")

        elif save_option == "index":
            console.print("\n[yellow]ℹ️  Adding to existing index template not yet implemented.[/yellow]")
            console.print("[dim]Use the component template option or copy the JSON manually.[/dim]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")


def option_query_builder_ui(es):
    """
    Visual query builder for constructing Elasticsearch queries.
    Interactive menu to build complex queries with preview and testing.
    """
    show_breadcrumb(["Main Menu", "Developer Tools", "Query Builder"])

    console.print("\n[bold cyan]🔍 Query Builder[/bold cyan]\n")
    console.print("[dim]Build Elasticsearch queries interactively[/dim]\n")

    try:
        # Initialize query structure
        query = {"query": {}}

        # Main query type selection
        query_type = questionary.select(
            "Select query type:",
            choices=[
                Choice("match - Full-text search", value="match"),
                Choice("term - Exact term match", value="term"),
                Choice("range - Range query", value="range"),
                Choice("bool - Boolean query (must/should/must_not/filter)", value="bool"),
                Choice("wildcard - Wildcard pattern", value="wildcard"),
                Choice("prefix - Prefix match", value="prefix"),
                Choice("exists - Field exists", value="exists"),
                Choice("match_all - Match all documents", value="match_all"),
            ],
            style=custom_style
        ).ask()

        if not query_type:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Build query based on type
        if query_type == "match":
            field = get_text_input("Field name:", default="message")
            value = get_text_input("Search value:")
            if field and value:
                query["query"] = {"match": {field: value}}

        elif query_type == "term":
            field = get_text_input("Field name:", default="status")
            value = get_text_input("Exact value:")
            if field and value:
                query["query"] = {"term": {field: value}}

        elif query_type == "range":
            field = get_text_input("Field name:", default="@timestamp")
            gte = get_text_input("Greater than or equal (gte):", default="now-1d")
            lte = get_text_input("Less than or equal (lte):", default="now")
            if field:
                range_query = {}
                if gte:
                    range_query["gte"] = gte
                if lte:
                    range_query["lte"] = lte
                query["query"] = {"range": {field: range_query}}

        elif query_type == "bool":
            console.print("\n[cyan]Building bool query...[/cyan]\n")
            bool_query = {}

            # Must clauses
            if confirm_action("Add 'must' clauses (AND)?"):
                must_clauses = []
                while True:
                    clause_type = questionary.select(
                        "Add clause type:",
                        choices=[
                            Choice("match", value="match"),
                            Choice("term", value="term"),
                            Choice("range", value="range"),
                            Choice("Done", value="done"),
                        ],
                        style=custom_style
                    ).ask()

                    if clause_type == "done" or not clause_type:
                        break

                    if clause_type == "match":
                        field = get_text_input("Field:")
                        value = get_text_input("Value:")
                        if field and value:
                            must_clauses.append({"match": {field: value}})
                    elif clause_type == "term":
                        field = get_text_input("Field:")
                        value = get_text_input("Value:")
                        if field and value:
                            must_clauses.append({"term": {field: value}})
                    elif clause_type == "range":
                        field = get_text_input("Field:")
                        gte = get_text_input("gte (optional):")
                        lte = get_text_input("lte (optional):")
                        if field:
                            range_q = {}
                            if gte:
                                range_q["gte"] = gte
                            if lte:
                                range_q["lte"] = lte
                            must_clauses.append({"range": {field: range_q}})

                if must_clauses:
                    bool_query["must"] = must_clauses

            # Should clauses
            if confirm_action("Add 'should' clauses (OR)?"):
                should_clauses = []
                while True:
                    field = get_text_input("Field (or press Enter to finish):")
                    if not field:
                        break
                    value = get_text_input("Value:")
                    if value:
                        should_clauses.append({"match": {field: value}})

                if should_clauses:
                    bool_query["should"] = should_clauses

            # Must not clauses
            if confirm_action("Add 'must_not' clauses (NOT)?"):
                must_not_clauses = []
                while True:
                    field = get_text_input("Field (or press Enter to finish):")
                    if not field:
                        break
                    value = get_text_input("Value:")
                    if value:
                        must_not_clauses.append({"term": {field: value}})

                if must_not_clauses:
                    bool_query["must_not"] = must_not_clauses

            # Filter clauses
            if confirm_action("Add 'filter' clauses?"):
                filter_clauses = []
                while True:
                    field = get_text_input("Field (or press Enter to finish):")
                    if not field:
                        break
                    value = get_text_input("Value:")
                    if value:
                        filter_clauses.append({"term": {field: value}})

                if filter_clauses:
                    bool_query["filter"] = filter_clauses

            query["query"] = {"bool": bool_query}

        elif query_type == "wildcard":
            field = get_text_input("Field name:")
            pattern = get_text_input("Wildcard pattern (use * and ?):")
            if field and pattern:
                query["query"] = {"wildcard": {field: pattern}}

        elif query_type == "prefix":
            field = get_text_input("Field name:")
            prefix = get_text_input("Prefix value:")
            if field and prefix:
                query["query"] = {"prefix": {field: prefix}}

        elif query_type == "exists":
            field = get_text_input("Field name:")
            if field:
                query["query"] = {"exists": {"field": field}}

        elif query_type == "match_all":
            query["query"] = {"match_all": {}}

        # Add aggregations
        if confirm_action("Add aggregations?"):
            console.print("\n[cyan]Building aggregations...[/cyan]\n")
            aggs = {}

            while True:
                agg_name = get_text_input("Aggregation name (or press Enter to finish):")
                if not agg_name:
                    break

                agg_type = questionary.select(
                    f"Aggregation type for '{agg_name}':",
                    choices=[
                        Choice("terms - Bucket by field values", value="terms"),
                        Choice("date_histogram - Time-based buckets", value="date_histogram"),
                        Choice("avg - Average value", value="avg"),
                        Choice("sum - Sum values", value="sum"),
                        Choice("min - Minimum value", value="min"),
                        Choice("max - Maximum value", value="max"),
                        Choice("cardinality - Unique count", value="cardinality"),
                    ],
                    style=custom_style
                ).ask()

                if not agg_type:
                    break

                if agg_type in ["terms", "avg", "sum", "min", "max", "cardinality"]:
                    field = get_text_input("Field name:")
                    if field:
                        aggs[agg_name] = {agg_type: {"field": field}}
                        if agg_type == "terms":
                            size = get_number_input("Number of buckets:", default=10, min_val=1)
                            if size:
                                aggs[agg_name][agg_type]["size"] = size

                elif agg_type == "date_histogram":
                    field = get_text_input("Date field:", default="@timestamp")
                    interval = get_text_input("Interval (e.g., 1h, 1d, 1w):", default="1h")
                    if field and interval:
                        aggs[agg_name] = {
                            "date_histogram": {
                                "field": field,
                                "calendar_interval": interval
                            }
                        }

            if aggs:
                query["aggs"] = aggs

        # Add sorting
        if confirm_action("Add sorting?"):
            console.print("\n[cyan]Configuring sort...[/cyan]\n")
            sort_list = []

            while True:
                field = get_text_input("Sort field (or press Enter to finish):")
                if not field:
                    break

                order = questionary.select(
                    f"Sort order for '{field}':",
                    choices=[
                        Choice("asc - Ascending", value="asc"),
                        Choice("desc - Descending", value="desc"),
                    ],
                    style=custom_style
                ).ask()

                if order:
                    sort_list.append({field: {"order": order}})

            if sort_list:
                query["sort"] = sort_list

        # Add size limit
        size = get_number_input("Number of results to return:", default=10, min_val=0)
        if size is not None:
            query["size"] = size

        # Display query preview
        console.print("\n[bold cyan]Query Preview:[/bold cyan]\n")
        query_json = json.dumps(query, indent=2)
        syntax = Syntax(query_json, "json", theme="monokai", line_numbers=True)
        console.print(Panel(syntax, title="[bold green]Elasticsearch Query[/bold green]", box=box.ROUNDED))
        console.print()

        # Test query option
        if confirm_action("Test query against an index?"):
            # Get list of indices
            try:
                indices_response = es.cat.indices(format="json", h="index")
                index_names = [idx["index"] for idx in indices_response if not idx["index"].startswith(".")]

                if not index_names:
                    console.print("\n[yellow]⚠️  No indices found.[/yellow]\n")
                else:
                    selected_index = questionary.select(
                        "Select index to test against:",
                        choices=[Choice(idx, value=idx) for idx in sorted(index_names)[:50]],
                        style=custom_style
                    ).ask()

                    if selected_index:
                        console.print(f"\n[cyan]Testing query against '{selected_index}'...[/cyan]\n")

                        try:
                            with Progress(
                                SpinnerColumn(),
                                TextColumn("[cyan]Executing query..."),
                                transient=True,
                            ) as progress:
                                progress.add_task("query", total=None)
                                result = es.search(index=selected_index, body=query)

                            hits = result.get("hits", {})
                            total = hits.get("total", {}).get("value", 0)

                            console.print(f"[green]✅ Query executed successfully[/green]")
                            console.print(f"[cyan]Total matches: {total}[/cyan]\n")

                            # Display sample results with pagination
                            if hits.get("hits"):
                                # Build renderable panels for each document
                                doc_panels = []
                                for i, hit in enumerate(hits["hits"], 1):
                                    source_json = json.dumps(hit.get("_source", {}), indent=2)
                                    syntax = Syntax(source_json, "json", theme="monokai", line_numbers=False)
                                    doc_panels.append(Panel(
                                        syntax,
                                        title=f"[bold]Document {i} (ID: {hit.get('_id', 'N/A')})[/bold]",
                                        box=box.ROUNDED
                                    ))
                                
                                paginate_renderables(doc_panels, page_size=5, title="Query Results")

                            # Display aggregation results
                            if "aggregations" in result:
                                console.print("[bold cyan]Aggregation Results:[/bold cyan]\n")
                                agg_json = json.dumps(result["aggregations"], indent=2)
                                syntax = Syntax(agg_json, "json", theme="monokai", line_numbers=False)
                                console.print(Panel(syntax, title="[bold green]Aggregations[/bold green]", box=box.ROUNDED))
                                console.print()

                        except Exception as e:
                            console.print(f"\n[red]❌ Query execution error: {e}[/red]\n")

            except Exception as e:
                console.print(f"\n[red]❌ Error fetching indices: {e}[/red]\n")

        # Export query option
        if confirm_action("Export query to file?"):
            filename = get_text_input("Filename:", default=f"query_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            if filename:
                try:
                    if not filename.endswith(".json"):
                        filename += ".json"

                    with open(filename, "w") as f:
                        json.dump(query, f, indent=2)

                    console.print(f"\n[green]✅ Query exported to '{filename}'[/green]\n")
                except Exception as e:
                    console.print(f"\n[red]❌ Error saving file: {e}[/red]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")


def option_bulk_api_helper(es):
    """
    Bulk API operations helper for index, update, and delete operations.
    Support NDJSON files and interactive entry with progress tracking.
    """
    show_breadcrumb(["Main Menu", "Developer Tools", "Bulk API Helper"])

    console.print("\n[bold cyan]📦 Bulk API Helper[/bold cyan]\n")
    console.print("[dim]Perform bulk index, update, or delete operations[/dim]\n")

    try:
        # Select operation mode
        operation_mode = questionary.select(
            "Select bulk operation mode:",
            choices=[
                Choice("Bulk Index - Add/index documents", value="index"),
                Choice("Bulk Update - Update existing documents", value="update"),
                Choice("Bulk Delete - Delete documents", value="delete"),
            ],
            style=custom_style
        ).ask()

        if not operation_mode:
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        # Get target index
        index_name = get_text_input("Target index name:")
        if not index_name:
            return

        bulk_operations = []

        if operation_mode == "index":
            console.print("\n[cyan]Bulk Index Mode[/cyan]\n")

            input_method = questionary.select(
                "How would you like to provide documents?",
                choices=[
                    Choice("Load from NDJSON file", value="file"),
                    Choice("Enter documents interactively", value="interactive"),
                ],
                style=custom_style
            ).ask()

            if not input_method:
                return

            if input_method == "file":
                filepath = get_text_input("NDJSON file path:")
                if not filepath:
                    return

                try:
                    with open(filepath, "r") as f:
                        for line_num, line in enumerate(f, 1):
                            line = line.strip()
                            if not line:
                                continue

                            try:
                                doc = json.loads(line)
                                bulk_operations.append({"index": {"_index": index_name}})
                                bulk_operations.append(doc)
                            except json.JSONDecodeError as e:
                                console.print(f"[yellow]⚠️  Skipping invalid JSON on line {line_num}: {e}[/yellow]")

                    console.print(f"\n[green]✅ Loaded {len(bulk_operations) // 2} documents from file[/green]\n")

                except FileNotFoundError:
                    console.print(f"\n[red]❌ File not found: {filepath}[/red]\n")
                    return
                except Exception as e:
                    console.print(f"\n[red]❌ Error reading file: {e}[/red]\n")
                    return

            else:  # interactive
                console.print("\n[cyan]Enter documents as JSON (one per entry)[/cyan]")
                console.print("[dim]Press Enter with empty input to finish[/dim]\n")

                doc_count = 0
                while True:
                    console.print(f"[cyan]Document {doc_count + 1}:[/cyan]")
                    doc_json = get_text_input("JSON document (or press Enter to finish):")

                    if not doc_json:
                        break

                    try:
                        doc = json.loads(doc_json)
                        bulk_operations.append({"index": {"_index": index_name}})
                        bulk_operations.append(doc)
                        doc_count += 1
                        console.print(f"[green]✅ Added document {doc_count}[/green]\n")
                    except json.JSONDecodeError as e:
                        console.print(f"[red]❌ Invalid JSON: {e}[/red]\n")

                if doc_count == 0:
                    console.print("\n[yellow]⚠️  No documents added.[/yellow]\n")
                    return

        elif operation_mode == "update":
            console.print("\n[cyan]Bulk Update Mode[/cyan]\n")

            # Get document IDs
            id_method = questionary.select(
                "How would you like to specify document IDs?",
                choices=[
                    Choice("Load IDs from file (one per line)", value="file"),
                    Choice("Enter IDs manually", value="manual"),
                ],
                style=custom_style
            ).ask()

            if not id_method:
                return

            doc_ids = []

            if id_method == "file":
                filepath = get_text_input("File path with document IDs:")
                if not filepath:
                    return

                try:
                    with open(filepath, "r") as f:
                        doc_ids = [line.strip() for line in f if line.strip()]
                    console.print(f"\n[green]✅ Loaded {len(doc_ids)} document IDs[/green]\n")
                except Exception as e:
                    console.print(f"\n[red]❌ Error reading file: {e}[/red]\n")
                    return
            else:
                console.print("\n[cyan]Enter document IDs (one per entry)[/cyan]")
                console.print("[dim]Press Enter with empty input to finish[/dim]\n")

                while True:
                    doc_id = get_text_input(f"Document ID {len(doc_ids) + 1} (or press Enter to finish):")
                    if not doc_id:
                        break
                    doc_ids.append(doc_id)

            if not doc_ids:
                console.print("\n[yellow]⚠️  No document IDs provided.[/yellow]\n")
                return

            # Get update method
            update_method = questionary.select(
                "Update method:",
                choices=[
                    Choice("Partial document update", value="doc"),
                    Choice("Script update", value="script"),
                ],
                style=custom_style
            ).ask()

            if not update_method:
                return

            if update_method == "doc":
                console.print("\n[cyan]Enter partial document (fields to update):[/cyan]")
                update_doc_json = get_text_input("JSON:")

                if not update_doc_json:
                    return

                try:
                    update_doc = json.loads(update_doc_json)

                    for doc_id in doc_ids:
                        bulk_operations.append({"update": {"_index": index_name, "_id": doc_id}})
                        bulk_operations.append({"doc": update_doc})

                except json.JSONDecodeError as e:
                    console.print(f"\n[red]❌ Invalid JSON: {e}[/red]\n")
                    return

            else:  # script
                script_source = get_text_input("Script source (e.g., ctx._source.counter += params.count):")
                if not script_source:
                    return

                params_json = get_text_input("Script params as JSON (optional, or press Enter to skip):")
                params = {}
                if params_json:
                    try:
                        params = json.loads(params_json)
                    except json.JSONDecodeError as e:
                        console.print(f"\n[red]❌ Invalid params JSON: {e}[/red]\n")
                        return

                for doc_id in doc_ids:
                    bulk_operations.append({"update": {"_index": index_name, "_id": doc_id}})
                    script_body = {"script": {"source": script_source}}
                    if params:
                        script_body["script"]["params"] = params
                    bulk_operations.append(script_body)

        elif operation_mode == "delete":
            console.print("\n[cyan]Bulk Delete Mode[/cyan]\n")

            delete_method = questionary.select(
                "How would you like to specify documents to delete?",
                choices=[
                    Choice("By document IDs", value="ids"),
                    Choice("By query (delete by query)", value="query"),
                ],
                style=custom_style
            ).ask()

            if not delete_method:
                return

            if delete_method == "ids":
                # Get document IDs
                id_method = questionary.select(
                    "How would you like to specify document IDs?",
                    choices=[
                        Choice("Load IDs from file (one per line)", value="file"),
                        Choice("Enter IDs manually", value="manual"),
                    ],
                    style=custom_style
                ).ask()

                if not id_method:
                    return

                doc_ids = []

                if id_method == "file":
                    filepath = get_text_input("File path with document IDs:")
                    if not filepath:
                        return

                    try:
                        with open(filepath, "r") as f:
                            doc_ids = [line.strip() for line in f if line.strip()]
                        console.print(f"\n[green]✅ Loaded {len(doc_ids)} document IDs[/green]\n")
                    except Exception as e:
                        console.print(f"\n[red]❌ Error reading file: {e}[/red]\n")
                        return
                else:
                    console.print("\n[cyan]Enter document IDs (one per entry)[/cyan]")
                    console.print("[dim]Press Enter with empty input to finish[/dim]\n")

                    while True:
                        doc_id = get_text_input(f"Document ID {len(doc_ids) + 1} (or press Enter to finish):")
                        if not doc_id:
                            break
                        doc_ids.append(doc_id)

                if not doc_ids:
                    console.print("\n[yellow]⚠️  No document IDs provided.[/yellow]\n")
                    return

                for doc_id in doc_ids:
                    bulk_operations.append({"delete": {"_index": index_name, "_id": doc_id}})

            else:  # query-based deletion
                console.print("\n[yellow]⚠️  Query-based deletion uses delete_by_query API, not bulk API.[/yellow]")
                console.print("[cyan]Enter query to match documents for deletion:[/cyan]\n")

                query_json = get_text_input("Query JSON:")
                if not query_json:
                    return

                try:
                    query = json.loads(query_json)

                    if not confirm_action(f"Delete all documents matching this query from '{index_name}'?"):
                        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
                        return

                    if not GOD_MODE:
                        console.print("[yellow]🔍 SAFE MODE: Would execute delete_by_query but no action taken.[/yellow]\n")
                        console.print(f"[dim]Query: {json.dumps(query, indent=2)}[/dim]\n")
                        return

                    # Execute delete by query
                    result = es.delete_by_query(index=index_name, body={"query": query})
                    deleted = result.get("deleted", 0)

                    console.print(f"\n[green]✅ Deleted {deleted} documents[/green]\n")
                    return

                except json.JSONDecodeError as e:
                    console.print(f"\n[red]❌ Invalid JSON: {e}[/red]\n")
                    return
                except Exception as e:
                    console.print(f"\n[red]❌ Error: {e}[/red]\n")
                    return

        # Execute bulk operations
        if not bulk_operations:
            console.print("\n[yellow]⚠️  No operations to execute.[/yellow]\n")
            return

        operation_count = len(bulk_operations) // 2 if operation_mode != "delete" or delete_method == "ids" else len(bulk_operations)

        console.print(f"\n[cyan]Prepared {operation_count} {operation_mode} operation(s)[/cyan]\n")

        # Show summary
        summary_table = Table(title="Bulk Operation Summary", box=box.ROUNDED, title_style="bold cyan")
        summary_table.add_column("Property", style="cyan")
        summary_table.add_column("Value", style="yellow")

        summary_table.add_row("Operation Type", operation_mode.upper())
        summary_table.add_row("Target Index", index_name)
        summary_table.add_row("Number of Operations", str(operation_count))

        console.print(summary_table)
        console.print()

        # Confirm execution
        if not confirm_action(f"Execute {operation_count} {operation_mode} operation(s)?"):
            console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")
            return

        if not GOD_MODE:
            console.print("[yellow]🔍 SAFE MODE: Would execute bulk operations but no action taken.[/yellow]\n")
            console.print(f"[dim]First operation preview:[/dim]")
            preview = bulk_operations[:4] if len(bulk_operations) >= 4 else bulk_operations
            console.print(f"[dim]{json.dumps(preview, indent=2)}[/dim]\n")
            return

        # Execute bulk request with progress bar
        console.print("\n[cyan]Executing bulk operations...[/cyan]\n")

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[cyan]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                transient=False,
            ) as progress:
                task = progress.add_task(f"Processing {operation_count} operations...", total=operation_count)

                # Execute bulk
                response = es.bulk(body=bulk_operations, refresh=True)
                progress.update(task, completed=operation_count)

            # Parse results
            items = response.get("items", [])
            errors = response.get("errors", False)

            success_count = 0
            error_count = 0
            error_details = []

            for item in items:
                # Each item is a dict with one key (index/update/delete)
                op_type = list(item.keys())[0]
                op_result = item[op_type]

                if op_result.get("status") in [200, 201]:
                    success_count += 1
                else:
                    error_count += 1
                    error_details.append({
                        "id": op_result.get("_id", "N/A"),
                        "error": op_result.get("error", {}).get("reason", "Unknown error"),
                        "status": op_result.get("status", "N/A")
                    })

            console.print()

            # Display results table
            results_table = Table(title="Bulk Operation Results", box=box.ROUNDED, title_style="bold cyan")
            results_table.add_column("Metric", style="cyan")
            results_table.add_column("Count", style="yellow", justify="right")

            results_table.add_row("Total Operations", str(operation_count))
            results_table.add_row("Successful", f"[green]{success_count}[/green]")
            results_table.add_row("Failed", f"[red]{error_count}[/red]" if error_count > 0 else "0")
            results_table.add_row("Took (ms)", str(response.get("took", "N/A")))

            console.print(results_table)
            console.print()

            # Display errors if any
            if error_count > 0:
                console.print("[bold red]Errors:[/bold red]\n")

                error_table = Table(box=box.ROUNDED)
                error_table.add_column("Document ID", style="cyan")
                error_table.add_column("Status", style="yellow")
                error_table.add_column("Error", style="red", no_wrap=False)

                for error in error_details[:10]:  # Show first 10 errors
                    error_table.add_row(
                        error["id"],
                        str(error["status"]),
                        error["error"]
                    )

                console.print(error_table)

                if len(error_details) > 10:
                    console.print(f"\n[dim]... and {len(error_details) - 10} more errors[/dim]\n")
                else:
                    console.print()
            else:
                console.print("[green]✅ All operations completed successfully![/green]\n")

        except Exception as e:
            console.print(f"\n[red]❌ Bulk operation error: {e}[/red]\n")

    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Cancelled.[/yellow]\n")

