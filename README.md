# RRI-SWMM

Coupling between [RRI](http://rri-model.info/) (Rainfall-Runoff-Inundation), a
2D surface runoff and inundation model, and [SWMM](https://www.epa.gov/water-research/storm-water-management-model-swmm)
(Storm Water Management Model), which simulates the piped/open-channel
drainage network. The two models exchange water at each coupling time step:
RRI provides surface water depth at each SWMM node location, and SWMM returns
the resulting inflow/outflow at those nodes back to RRI's surface grid.

## Repository structure

- `main_parallel_with_logger.py` — main entry point. Runs the coupled
  simulation: steps SWMM forward, launches RRI as a subprocess for each
  coupling interval, and exchanges water depths/inflows between them.
- `helper_functions.py` — coupling logic (node-to-cell inflow computation,
  raster I/O, etc.), used by the entry point above.
- `read_inp.py` — parses SWMM `.inp` files into pandas/geopandas objects.
- `plot_water_levels.py` — plots observed vs. simulated (SWMM-only and
  RRI-SWMM) water levels at the sites with measured data.
- `node2cell/` — maps each SWMM node to its corresponding RRI grid cell
  (see [Node mapping](#node-mapping) below).
- `RRI_model/` — RRI input files (DEM, rainfall, model configuration, etc.) and
  the compiled RRI executable.
- `RRI_source/` — RRI Fortran source, for recompiling the executable
  (see [Compiling RRI](#compiling-rri) below).
- `SWMM_model/` — SWMM `.inp` file for the coupled run.
- `observed_data/` — measured water level time series used for validation.
- `benchmark/` — standalone SWMM model setup, used to compare SWMM-only
  results/performance against the coupled RRI-SWMM run.

## Setup

1. Create a virtual environment: `python -m venv .venv`
2. Activate it:
   - Linux/Mac: `source .venv/bin/activate`
   - Windows: `.venv\Scripts\activate`
3. Install dependencies: `pip install -r requirements.txt`

## Compiling RRI

A compiled RRI executable is already included in `RRI_model/` (`0_rri_1_4_2_7.exe`
for Windows, `0_rri_1_4_2_7` for Linux). `main_parallel_with_logger.py` picks
the right one automatically based on the OS it's running on.

To recompile from source (`RRI_source/`):

- **Windows** (Intel Fortran / ifort): run `make_1_4_2_7.bat` from inside the
  source folder.
- **Linux** (gfortran):
  ```bash
  cd RRI_source/1.4.2.7-20260121T122640Z-3-001/1.4.2.7/
  gfortran -O3 -fopenmp -ffree-line-length-none -c RRI_Mod.f90 RRI_Mod2.f90 RRI_Mod_Dam.f90 RRI_Mod_Tecout.f90
  gfortran -O3 -fopenmp -ffree-line-length-none -c RRI.f90 RRI_Bound.f90 RRI_Dam.f90 RRI_Div.f90 RRI_DT_Check.f90 RRI_Evp.f90 RRI_GW.f90 RRI_Infilt.f90 RRI_Read.f90 RRI_Riv.f90 RRI_RivSlo.f90 RRI_Section.f90 RRI_Slope.f90 RRI_Sub.f90 RRI_Tecout.f90 RRI_TSAS.f90
  gfortran -O3 -fopenmp -ffree-line-length-none *.o -o 0_rri_1_4_2_7
  ```
  Copy the resulting binary into `RRI_model/` and make sure it's executable
  (`chmod +x`).

This source is the upstream RRI 1.4.2.7 release with two small fixes applied
(see the comments in `RRI.f90`): a missing `write` statement, and a rainfall
end-of-file check (`iostat`) broadened to also catch a spurious positive
error code that some gfortran versions return at end-of-file instead of the
expected negative one.

## Node mapping

Before coupling the models, every SWMM node must be mapped to an RRI cell.
This is handled by the `node2cell` module.

### Requirements
You will need two input files:
1. **SWMM Coordinates:** A file containing the coordinates of the SWMM nodes.
2. **RRI raster:** One of the topography `.asc` files from the RRI model.

> **⚠️ Important:** Both files must use the **same projected coordinate system** with units in **meters**.

> **Note:** You can find example input files in the `node2cell` directory: `NodeXY.txt` (for SWMM coordinates) and `dem.asc` (for RRI raster).

### Usage
1. Open `set_node2cell.txt` and specify the paths/names of the two input files described above.
2. Run the executable: `node2cell.exe`
3. A new file named `node_ij.txt` will be generated containing the final mapping results.

## Running the coupled simulation

`main_parallel_with_logger.py` runs the coupled RRI-SWMM simulation. Edit the
settings at the top of the file before running:

- `time_start` / `time_end` — simulation period.
- `time_step` — coupling interval (must match RRI's `RRI_Input.txt` timestep
  settings, e.g. `'10min'` → `lasth = 0.166667`, `outnum = 1`).
- `ENABLE_LOGGING` — when `True`, each RRI call's output is written to
  `RRI_model/rri_execution.log` (overwritten every step) and printed on
  failure; when `False`, RRI's output is discarded.

Run it with:
```bash
python main_parallel_with_logger.py
```

Results are written to `HIST/out/` (RRI surface rasters per step) and to the
SWMM `.rpt`/`.out` files under `SWMM_model/`.

## Plotting results

`plot_water_levels.py` compares observed water levels (`observed_data/`)
against SWMM-only (`benchmark/model.out`) and coupled RRI-SWMM
(`SWMM_model/model.out`) simulated levels, at the sites with measured data.

```bash
python plot_water_levels.py            # English labels (default)
python plot_water_levels.py --lang es  # Spanish labels
```

Saves `water_levels_comparison.png` (or `water_levels_comparison_es.png`).
