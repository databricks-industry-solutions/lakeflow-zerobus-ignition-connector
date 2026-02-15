### EQT (USA/Appalachia) — Shale gas demo tag model (Ignition) — example

This folder contains a lightweight Ignition demo tag hierarchy modeled after a typical **Appalachia shale gas** flow:

- pads / wells (wellhead + production + integrity)
- processing (separator, compressor, dehydrator)
- midstream (sales meter + pipeline)
- safety (ESD + gas detection)

## How to use

1) Create a Standard Tag Provider named `eqt` in Ignition.

2) Import:

- Provider `eqt` → `eqt_appalachia_site01_tags.json`

Tag paths will look like:

- `[eqt]EQT/USA/Appalachia/Site01/Pads/PadA/W01/Wellhead/Pressure_psi`
- `[eqt]EQT/USA/Appalachia/Site01/Processing/Compressor01/Vibration_mm_s`
- `[eqt]EQT/USA/Appalachia/Site01/Midstream/SalesMeter01/GasFlow_Mscfd`

