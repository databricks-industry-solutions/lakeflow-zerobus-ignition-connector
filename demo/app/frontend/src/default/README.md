# Default Logo Kit

Core Databricks logos for general use.

## Included Logos

| File | Description | Use Case |
|------|-------------|----------|
| `databricks-full.png` | Databricks logo (red/orange bars with text) | All diagrams |
| `delta.png` | Delta Lake (teal triangle) | Lakehouse architectures |
| `unity-catalog.png` | Unity Catalog (pink/yellow/hexagon with text) | Governance, data cataloging |
| `unity-catalog-solo.png` | Unity Catalog icon only | When space is limited |
| `iceberg.png` | Apache Iceberg (blue iceberg) | Table format |
| `MLflow-logo-final-black.png` | MLflow (black text logo) | ML workflows, tracking |
| `postgres-logo.png` | PostgreSQL (blue elephant) | Database, Lakebase |

## When to Use This Kit

Use this kit for:
- ✅ Generic Databricks architectures
- ✅ Cloud-agnostic diagrams
- ✅ Internal documentation
- ✅ Proof of concepts

## How to Add Logos

1. **Get official logos** from https://databricks.com/company/brand
2. **Save as JPG** with descriptive names (lowercase, hyphens)
3. **Add to this directory:**
   ```bash
   cp ~/Downloads/databricks-logo.jpg logos/default/
   ```
4. **Verify:**
   ```bash
   nano-banana validate-logos --logo-dir logos/default
   ```

## Logo Descriptions

When the AI generates diagrams, it uses these descriptions (not filenames):

| Logo Name | Description in Prompt |
|-----------|----------------------|
| `databricks-full` | "red/orange stacked bars icon with 'databricks' text" |
| `delta` | "teal/cyan triangle icon" |
| `unity-catalog` | "pink squares, yellow triangles, navy hexagon in center" |
| `unity-catalog-solo` | "pink squares, yellow triangles, navy hexagon icon" |
| `iceberg` | "blue iceberg icon" |
| `mlflow-logo-final-black` | "black MLflow logo with text" |
| `postgres-logo` | "blue elephant icon" |

These descriptions prevent filename leakage in generated diagrams.

## Example Diagram Spec

```yaml
name: "basic-lakehouse"
description: "Simple lakehouse with Unity Catalog"

components:
  - id: "databricks"
    label: "Databricks Workspace"
    logo_name: "databricks-full"

  - id: "delta"
    label: "Delta Lake"
    logo_name: "delta"

  - id: "uc"
    label: "Unity Catalog"
    logo_name: "unity-catalog"

  - id: "postgres"
    label: "PostgreSQL"
    logo_name: "postgres-logo"

connections:
  - from_id: "databricks"
    to_id: "delta"
    label: "Write"
```

## Notes

- Keep this kit minimal and focused on core Databricks products
- For cloud provider logos, use `logos/aws/`, `logos/azure/`, or `logos/gcp/`
- For customer-specific logos, create a new kit (e.g., `logos/acme-corp/`)
