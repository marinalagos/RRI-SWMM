# RRI-SWMM

## Node Mapping
Before coupling the models, every SWMM node must be mapped to an RRI cell. This is handled by the `node2cell` module.

### Requirements
You will need two input files:
1. **SWMM Coordinates:** A file containing the coordinates of the SWMM nodes.
2. **RRI raster:** One of the topografy `.asc` files from the RRI model.

> **⚠️ Important:** Both files must use the **same projected coordinate system** with units in **meters**.

> **Note:** You can find example input files in the `node2cell` directory: `NodeXY.txt` (for SWMM coordinates) and `dem.asc` (for RRI raster).

### usage
1. Open `set_node2cell.txt` and specify the paths/names of the two input files described above.
2. Run the executable:`node2cell.exe`
3. A new file named `node_ij.txt` will be generated containing the final mapping results.

## Python environment

2. Create the environment: `python -m venv .venv`
3. Activate it: `source .venv/bin/activate`
4. Install packages: `pip install -r requirements.txt`