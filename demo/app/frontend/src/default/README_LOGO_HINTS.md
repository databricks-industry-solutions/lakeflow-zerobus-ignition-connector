# Logo Hints System

## Overview

The logo hints system allows you to automatically inject detailed, logo-specific instructions into prompts when certain logos are detected. This is particularly useful for logos that AI models commonly misinterpret.

## How It Works

1. **Automatic Detection**: When you load a logo kit, nano_banana checks for a `logo_hints.yaml` file in the same directory
2. **Smart Matching**: If any loaded logos match entries in `logo_hints.yaml`, their hints are automatically retrieved
3. **Prompt Injection**: The hints are automatically injected at the top of the generated prompt, before any other content
4. **Zero Configuration**: Once configured, hints are applied automatically to all commands (generate, chat, refine, etc.)

## Configuration File

The `logo_hints.yaml` file in this directory defines logo-specific instructions:

```yaml
unity-catalog:
  enabled: true
  warning_level: "CRITICAL"  # CRITICAL | WARNING | INFO
  correct_description: "Detailed description of what the logo looks like"
  wrong_patterns:
    - "Common mistake 1"
    - "Common mistake 2"
  stop_condition: "Instruction to stop if doing wrong thing"
  additional_notes: "Any extra context"
```

## Current Logo Hints

### Unity Catalog (⚠️⚠️⚠️ CRITICAL)

**Problem**: AI models frequently misinterpret Unity Catalog as a single hexagon, when it's actually a multi-element composition.

**Solution**: Detailed instruction explaining the correct logo contains:
- Pink/magenta SQUARES (multiple)
- Yellow/gold TRIANGULAR shapes (multiple)  
- Navy blue HEXAGON (one, in center)
- Arranged in a constellation pattern

This hint is automatically applied to:
- `unity-catalog.png`
- `unity-catalog-solo.png`
- `governance-catalog` (alias)

## Verification

To verify logo hints are loading:

```bash
# Check hints are loaded
nano-banana validate-logos --logo-dir logos/default

# Generate with hints (automatic)
nano-banana generate-raw --prompt-file my_prompt.txt --logo-dir logos/default
```

You should see console output like:
```
Loading logos from logos/default...
  Loaded 7 logos with 3 hints
```

## Adding New Logo Hints

To add hints for a logo that's commonly misinterpreted:

1. Edit `logo_hints.yaml` in this directory
2. Add a new entry with the logo name (without file extension)
3. Set `enabled: true`
4. Provide detailed descriptions of correct/wrong patterns
5. Test by generating a diagram that uses that logo

Example for a new logo:

```yaml
databricks-full:
  enabled: true
  warning_level: "WARNING"
  correct_description: "Stacked orange/red bars with 'databricks' text below"
  wrong_patterns:
    - "A solid rectangle"
    - "A gradient bar without distinct segments"
  stop_condition: "If generating a solid shape, STOP - use the uploaded logo"
```

## Technical Details

- **Matching Logic**: Logo hints match on normalized names (case-insensitive, underscores→hyphens)
- **Fallback**: If no hints file exists, the system continues normally without hints
- **Performance**: Hints are loaded once per session and cached
- **Injection Point**: Hints are injected at the very top of prompts, before design constraints

## Benefits

1. **Consistent Logo Fidelity**: Dramatically improves logo accuracy for problematic logos
2. **Zero Friction**: Works automatically without changing commands or workflows
3. **Maintainable**: Centralized configuration makes it easy to update instructions
4. **Extensible**: Add new logo hints as you discover patterns

## Troubleshooting

**Hints not loading?**
- Check that `logo_hints.yaml` exists in the logo directory
- Verify the logo name matches the filename (without extension)
- Ensure `enabled: true` in the YAML
- Check console output for "loaded X logos with Y hints"

**Hints not working?**
- The hint is injected into the prompt, but AI behavior may vary
- Try increasing warning level to "CRITICAL"
- Add more specific anti-patterns to wrong_patterns
- Make the correct_description more detailed and visual

## Files

- `logo_hints.yaml` - Configuration file with logo-specific instructions
- This README - Documentation for the logo hints system
- Logos - The actual logo image files (PNG, JPG)
