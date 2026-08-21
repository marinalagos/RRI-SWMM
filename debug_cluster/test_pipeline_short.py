import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, para poder importar helper_functions

from helper_functions import get_associated_lengths, get_hs_vector, compute_nodes_inflows, update_hs_raster, read_ascii_raster_no_data, write_hs_grid, read_hs_grid
import pandas as pd
import shutil
import subprocess
from pyswmm import Simulation, Nodes
import numpy as np

# Copia de main_parallel_with_logger.py acortada a ~1 hora (6 pasos de 10 min) para
# validar que el fix de RRI.f90 (lectura de lluvia) funciona en varios pasos seguidos,
# no solo el primero, sin tener que esperar la simulacion completa de 5 dias.
# No modifica main_parallel_with_logger.py.

ENABLE_LOGGING = True

time_step = '10min'
time_step_seconds = pd.Timedelta(time_step).seconds

hist_path = Path('./HIST')
out_path = hist_path / 'out'
out_path.mkdir(parents=True, exist_ok=True)

SWMM_model_path = Path('./SWMM_model/')
SWMM_model_name = 'model'

RRI_model_path = Path('./RRI_model/')
RRI_DEM_path = Path('./RRI_model/input_files/DEM.asc')
RRI_soil_depth_path = Path('./RRI_model/input_files/landuse_da.asc')
out_path = RRI_model_path / 'out'
out_path.mkdir(parents=True, exist_ok=True)

associated_lengths = get_associated_lengths(str(SWMM_model_path.joinpath(SWMM_model_name + '.inp')))
sim = Simulation(str(SWMM_model_path.joinpath(SWMM_model_name + '.inp')),
                 str(SWMM_model_path.joinpath(SWMM_model_name + '.rpt')),
                 str(SWMM_model_path.joinpath(SWMM_model_name + '.out')))

sim.step_advance(time_step_seconds)

nrows, ncols, cells_size, hs = read_ascii_raster_no_data(RRI_DEM_path)
write_hs_grid(hs, out_file=RRI_model_path.joinpath('out','gampt_ff_000001.out'), nodata_value=-0.10000)
write_hs_grid(hs, out_file=RRI_model_path.joinpath('out','hs_000001.out'), nodata_value=-0.10000)
write_hs_grid(hs, out_file=RRI_model_path.joinpath('out','hr_000001.out'), nodata_value=-0.10000)
write_hs_grid(hs, out_file=RRI_model_path.joinpath('out','qr_000001.out'), nodata_value=-0.10000)

cell_surface_area = cells_size**2

cells_idxs = pd.read_csv('node2cell/node_ij.txt', index_col=0, sep=r'\s+', engine='python', names=['i', 'j'], skiprows=1)
cells_idxs.i = nrows - cells_idxs.i + 1

da_vector = get_hs_vector(cells_idxs=cells_idxs,
                          hs_file=RRI_soil_depth_path,
                          nodata_threshold=-1)

# Unico cambio real respecto al script de produccion: rango de tiempo corto (6 pasos)
time_start = '2024-03-18 20:30'
time_end = '2024-03-18 21:30'

sim.start_time = pd.to_datetime(time_start)
sim.end_time = pd.to_datetime(time_end)

i = 0
cum_neg_vol = 0

first_step = True
log_file = None
log_path = RRI_model_path / 'rri_execution.log'

for step in sim:

    if not first_step:
        try:
            proc.wait(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
            if log_file:
                log_file.close()
            raise RuntimeError("RRI timeout")

        if log_file:
            log_file.close()
            log_file = None

        if proc.returncode != 0:
            if ENABLE_LOGGING and log_path.is_file():
                with open(log_path, 'r') as f:
                    print("=== ERROR RRI LOG ===")
                    print(f.read())
            raise RuntimeError(f"RRI falló con código {proc.returncode}")

        shutil.copy2(RRI_model_path.joinpath('out','gampt_ff_000001.out'), hist_path.joinpath('out', f'gampt_ff_{i:06d}.out'))
        shutil.copy2(RRI_model_path.joinpath('out','hs_000001.out'), hist_path.joinpath('out', f'hs_{i:06d}.out'))
        shutil.copy2(RRI_model_path.joinpath('out','hr_000001.out'), hist_path.joinpath('out', f'hr_{i:06d}.out'))
        shutil.copy2(RRI_model_path.joinpath('out','qr_000001.out'), hist_path.joinpath('out', f'qr_{i:06d}.out'))

        hs_vector = get_hs_vector(cells_idxs=cells_idxs,
                                hs_file=RRI_model_path.joinpath('out','hs_000001.out'),
                                nodata_threshold=0.0)

        if hs_vector.isna().sum() > 0:
            hs_vector = hs_vector.fillna(0.0)

        hsurface_vector = hs_vector - da_vector
        hsurface_vector = hsurface_vector.clip(0)

        node_inflows = compute_nodes_inflows(sim=sim,
                                            associated_lengths=associated_lengths,
                                            surface_depths=hsurface_vector,
                                            inlet_length_proportion=0.05,
                                            c_orifice=0.6,
                                            c_weir=1.5*np.sqrt(0.3048),
                                            orifice_opening_height=0.15,
                                            compute_effective_h1=False)

        hs, neg_volume = update_hs_raster(hs_file_1 = RRI_model_path.joinpath('out','hs_000001.out'),
                                        inflows = pd.Series(node_inflows),
                                        cells_idxs = cells_idxs,
                                        hs_file_2 = RRI_model_path.joinpath('out','hs_000001.out'),
                                        time_delta = time_step_seconds,
                                        cell_surface_area = cell_surface_area,
                                        nodata_value = -0.10000
                                        )

        cum_neg_vol += neg_volume

        for node, inflow in node_inflows.items():
            if inflow > 0.0:
                Nodes(sim)[node].generated_inflow(inflow)
            else:
                Nodes(sim)[node].generated_inflow(0.0)

    i += 1

    current_sim_time = sim.current_time
    print(current_sim_time)

    rainfall_file = RRI_model_path.joinpath('rain', f'PREC_{current_sim_time.replace(minute=(current_sim_time.minute//10)*10, second=0, microsecond=0):%Y%m%d_%H%M}.txt')
    if rainfall_file.is_file():
        shutil.copy2(rainfall_file, RRI_model_path.joinpath('rain', 'P.txt'))
    else:
        print('Rainfall file not found. Last file is used instead')

    if ENABLE_LOGGING:
        log_file = open(log_path, 'w')
        stdout_target = log_file
        stderr_target = subprocess.STDOUT
    else:
        log_file = None
        stdout_target = subprocess.DEVNULL
        stderr_target = subprocess.DEVNULL

    proc = subprocess.Popen(
        str((RRI_model_path / "0_rri_1_4_2_7").resolve()),  # binario Linux, no el .exe
        cwd=RRI_model_path,
        stdout=stdout_target,
        stderr=stderr_target,
    )

    first_step = False

if not first_step:
    try:
        proc.wait(timeout=300)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    finally:
        if log_file:
            log_file.close()

sim.close()
print(f'Total negative volume: {cum_neg_vol} m³ ({cum_neg_vol*1000/(240*1000*1000)} mm for the SSD basin)')
print(f'PASOS COMPLETADOS: {i}')
