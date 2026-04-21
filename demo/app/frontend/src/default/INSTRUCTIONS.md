# Adding Logos to Default Kit

## Quick Start

1. **Download logos** from official sources
2. **Convert to JPG** if needed
3. **Name appropriately** (lowercase, hyphens)
4. **Copy to this directory**

## Required Logos

For basic functionality, add these logos:

```bash
# Databricks logo (red icon)
# Get from: https://databricks.com/company/brand
cp ~/Downloads/databricks-logo.jpg logos/default/

# Delta Lake logo (teal triangle)
cp ~/Downloads/delta-lake-logo.jpg logos/default/

# Unity Catalog logo (pink/yellow/hexagon)
cp ~/Downloads/uc-logo.jpg logos/default/
```

## Verify Installation

```bash
# Check files are present
ls -lh logos/default/*.jpg

# Validate with tool
nano-banana validate-logos --logo-dir logos/default
```

## Logo Naming Convention

| Product | Filename | Description |
|---------|----------|-------------|
| Databricks | `databricks-logo.jpg` | Main product logo |
| Delta Lake | `delta-lake-logo.jpg` | Storage layer |
| Unity Catalog | `uc-logo.jpg` | Data governance |
| MLflow | `mlflow-logo.jpg` | ML tracking |

## File Requirements

- **Format:** JPG or PNG (JPG preferred)
- **Max size:** 5MB per file
- **Resolution:** 500x500px minimum
- **Background:** Transparent or white
- **Quality:** High resolution (will be resized)

## Example Usage

Once logos are added:

```bash
# Generate diagram using default kit
nano-banana generate \
    --diagram-spec prompts/diagram_specs/example_basic.yaml \
    --template baseline

# Use in diagram spec
components:
  - id: "db"
    label: "Databricks"
    logo_name: "databricks"  # References databricks-logo.jpg
```

## Need Help?

- See [logos/README.md](../README.md) for complete documentation
- See [docs/nano_banana/LOGO_SETUP.md](../../docs/nano_banana/LOGO_SETUP.md) for detailed setup
