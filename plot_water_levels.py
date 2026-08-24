"""
Compares observed vs simulated (SWMM 5.2 and RRI-SWMM) water level time series
at the sites with measured data, plotting one subplot per site.

Data sources:
- Observed: observed_data/*.csv
- SWMM 5.2 (standalone): benchmark/model.out
- RRI-SWMM (coupled): SWMM_model/model.out
"""

from pathlib import Path
import pandas as pd
import matplotlib.pyplot as plt
from swmmtoolbox import swmmtoolbox as stb

# --- CONFIG ---

SWMM52_OUT_PATH = Path('benchmark/model.out')
RRI_SWMM_OUT_PATH = Path('SWMM_model/model.out')

OBS_DIR = Path('observed_data')

sensors = {
    'LP_Libano': {
        'path': OBS_DIR / 'Las Piedras y Líbano-data-2024-06-07 11_02_59.csv',
        'zero_offset': 2.15,
        'link_swmm': 'channel16633',
        'label': 'Las Piedras y Líbano',
    },
    'LP_Monteverde': {
        'path': OBS_DIR / 'Las Piedras MVD-data-2024-06-07 11_03_11.csv',
        'zero_offset': 2.78,
        'link_swmm': 'channel16446',
        'label': 'Las Piedras MVD',
    },
    'SF_Torre': {
        'path': OBS_DIR / 'San Francisco TOR-data-2024-06-07 11_03_42.csv',
        'zero_offset': 2.72,
        'link_swmm': 'channel50247',
        'label': 'San Francisco TOR',
    },
    # SF_Montevideo excluded: no observed data during the simulation window
    # (sensor gap from ~2024-03-14 to 2024-03-23 17:00).
}

SIM_START = pd.Timestamp('2024-03-18 20:30:00', tz='utc')
SIM_END = pd.Timestamp('2024-03-23 01:20:00', tz='utc')


# --- FUNCTIONS ---

def clean_duplicates(ts):
    dups = ts.index[ts.index.duplicated()]
    if len(dups) == 0:
        return ts
    inconsistent = []
    for idx, group in ts.loc[dups].groupby(level=0):
        if not (group == group.iloc[0]).all():
            inconsistent.append(idx)
    if inconsistent:
        print(f"  Warning: {len(inconsistent)} duplicate timestamps with differing values, keeping all.")
        return ts
    return ts[~ts.index.duplicated(keep='first')]


def load_observed(sensor_key):
    info = sensors[sensor_key]
    df = pd.read_csv(info['path'])
    # Known timezone correction at the data source, then localize to the true
    # timezone so it can be compared against simulated data on an absolute
    # time basis (see load_simulated).
    df['time'] = pd.to_datetime(df['time']) + pd.Timedelta(hours=3)
    df = df.set_index('time')
    df.index = df.index.tz_localize('America/Argentina/Buenos_Aires')
    ts = df[df.columns[0]] - info['zero_offset']
    ts.name = f'{sensor_key} - obs'
    ts = clean_duplicates(ts)
    return ts[SIM_START:SIM_END]


def load_simulated(out_path, sensor_key, series_label):
    info = sensors[sensor_key]
    if not out_path.is_file():
        print(f"  [{series_label}] not found: {out_path} (skipping this series)")
        return None
    df_sim = stb.extract(str(out_path), f"link,{info['link_swmm']},Flow_depth")
    ts = df_sim[df_sim.columns[0]]
    ts.index = ts.index.tz_localize('utc')
    ts.name = f'{sensor_key} - {series_label}'
    return ts


# --- LOAD DATA ---

results = {}
for sensor_key in sensors:
    print(f"Loading {sensor_key}...")
    results[sensor_key] = {
        'obs': load_observed(sensor_key),
        'swmm52': load_simulated(SWMM52_OUT_PATH, sensor_key, 'SWMM 5.2'),
        'rri_swmm': load_simulated(RRI_SWMM_OUT_PATH, sensor_key, 'RRI-SWMM'),
    }


# --- PLOT ---

fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)

for ax, sensor_key in zip(axes, sensors):
    data = results[sensor_key]
    info = sensors[sensor_key]

    if data['rri_swmm'] is not None:
        ax.plot(data['rri_swmm'], label='RRI-SWMM', color='tab:orange', linewidth=1.5)
    if data['swmm52'] is not None:
        ax.plot(data['swmm52'], label='SWMM 5.2', color='tab:blue', linewidth=1.5)
    ax.plot(data['obs'], label='Observed', color='black', linewidth=1.2,
             linestyle='--', marker='.', markersize=3)

    ax.set_title(info['label'])
    ax.set_ylabel('Water level [m]')
    ax.grid(alpha=0.3)
    ax.legend(loc='upper right')

axes[-1].set_xlabel('Date')
fig.suptitle('Observed vs simulated water level (SWMM 5.2 vs RRI-SWMM)', fontsize=13)
fig.tight_layout()

out_file = 'water_levels_comparison.png'
fig.savefig(out_file, dpi=150)
print(f"\nSaved: {out_file}")
