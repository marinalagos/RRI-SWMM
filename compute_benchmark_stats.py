"""
Parses the timing log produced by the interleaved RRI-SWMM / SWMM benchmark
and computes run time statistics (mean, standard deviation, coefficient of
variation, min, max) per algorithm.

Each run's duration is read directly from the "Total elapsed time: HH:MM:SS"
line SWMM itself reports in the tail of the .rpt file (printed by the
benchmark script right after each stage), attributed to whichever stage
("RRI-SWMM: ", "SWMM 5.1: ", "SWMM: 5.2", "SWMM 5.2 1cpu: ") most recently
started.

SWMM 5.1 runs are parsed but excluded from the summary -- the comparison of
interest is RRI-SWMM vs. SWMM 5.2. The "SWMM 5.2 1cpu" stage (used by the
3-way comparison, slurm_3way_comparison.sh) is included in the summary only
when the log actually contains runs for it, so this stays a no-op for logs
from the earlier two-way experiments.

By default, the first repetition of each algorithm is dropped as a warm-up
run (cold filesystem cache from the first read of the DEM/rainfall/model
files), following standard benchmarking practice. Use --skip 0 to include it.

Usage:
    python compute_benchmark_stats.py path/to/bench2_<jobid>.log
    python compute_benchmark_stats.py path/to/bench2_<jobid>.log --skip 0
"""

import argparse
import re
import statistics
from pathlib import Path

STAGE_MARKERS = [
    ('rri_swmm', re.compile(r'^RRI-SWMM:\s*')),
    ('swmm51', re.compile(r'^SWMM 5\.1:\s*')),
    ('swmm52_1cpu', re.compile(r'^SWMM 5\.2 1cpu:\s*')),
    ('swmm52', re.compile(r'^SWMM:\s*5\.2')),
]
ELAPSED_TIME = re.compile(r'Total elapsed time:\s*(\d+):(\d{2}):(\d{2})')

STAGE_LABELS = {
    'rri_swmm': 'RRI-SWMM',
    'swmm51': 'SWMM 5.1',
    'swmm52': 'SWMM 5.2',
    'swmm52_1cpu': 'SWMM 5.2 (1cpu)',
}


def parse_log(log_path):
    """Returns {stage_name: [duration_seconds, ...]}."""
    durations = {'rri_swmm': [], 'swmm51': [], 'swmm52': [], 'swmm52_1cpu': []}
    current_stage = None

    with open(log_path, 'r') as f:
        for line in f:
            for stage, pattern in STAGE_MARKERS:
                if pattern.match(line):
                    current_stage = stage
                    break

            m = ELAPSED_TIME.search(line)
            if m and current_stage is not None:
                h, mnt, s = (int(x) for x in m.groups())
                durations[current_stage].append(h * 3600 + mnt * 60 + s)
                current_stage = None  # avoid double-counting if the pattern repeats

    return durations


def summarize(durations, label):
    n = len(durations)
    if n == 0:
        return {'label': label, 'n': 0}
    return {
        'label': label,
        'n': n,
        'mean': statistics.mean(durations),
        'stdev': statistics.stdev(durations) if n > 1 else 0.0,
        'min': min(durations),
        'max': max(durations),
    }


def fmt_hms(seconds):
    h, rem = divmod(int(round(seconds)), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}"


def format_row(stats):
    if stats['n'] == 0:
        return f"| {stats['label']} | 0 | — | — | — | — | — |"
    cv = (stats['stdev'] / stats['mean'] * 100) if stats['mean'] else 0.0
    return (f"| {stats['label']} | {stats['n']} | {fmt_hms(stats['mean'])} | "
            f"{fmt_hms(stats['stdev'])} | {cv:.1f}% | {fmt_hms(stats['min'])} | {fmt_hms(stats['max'])} |")


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('log_path', type=Path, help='Path to the bench2_<jobid>.log file')
    parser.add_argument('--skip', type=int, default=1, metavar='N',
                         help='Drop the first N repetitions of each algorithm as warm-up runs (default: 1)')
    args = parser.parse_args()

    durations = parse_log(args.log_path)
    total_found = sum(len(v) for v in durations.values())
    if total_found == 0:
        print(f"No 'Total elapsed time' entries found in {args.log_path}. Check the log format.")
        return

    has_1cpu = len(durations['swmm52_1cpu']) > 0

    print(f"Parsed {total_found} completed runs from {args.log_path}")
    stages_present = ('rri_swmm', 'swmm51', 'swmm52', 'swmm52_1cpu') if has_1cpu else ('rri_swmm', 'swmm51', 'swmm52')
    for stage in stages_present:
        print(f"  {STAGE_LABELS[stage]}: {len(durations[stage])} runs")
    if args.skip:
        print(f"\nDropping the first {args.skip} repetition(s) of each algorithm as warm-up.")
    print()

    # When the log also has a 1cpu SWMM stage (3-way comparison), the plain
    # "SWMM 5.2" marker refers to the 2cpu run -- label it explicitly so the
    # two SWMM rows aren't ambiguous. For 2-way logs (no 1cpu stage), keep
    # the plain "SWMM 5.2" label exactly as before.
    swmm52_label = 'SWMM 5.2 (2cpu)' if has_1cpu else 'SWMM 5.2'

    rri_stats = summarize(durations['rri_swmm'][args.skip:], 'RRI-SWMM')
    swmm52_stats = summarize(durations['swmm52'][args.skip:], swmm52_label)

    print("| Algorithm | N | Mean | Std dev | CV | Min | Max |")
    print("|---|---|---|---|---|---|---|")
    print(format_row(rri_stats))
    print(format_row(swmm52_stats))
    if has_1cpu:
        swmm52_1cpu_stats = summarize(durations['swmm52_1cpu'][args.skip:], STAGE_LABELS['swmm52_1cpu'])
        print(format_row(swmm52_1cpu_stats))


if __name__ == '__main__':
    main()
