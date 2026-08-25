#!/bin/bash
#SBATCH --job-name=3way_comparison
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=2
#SBATCH --exclusive
#SBATCH --nodelist=node124
#SBATCH --output=3way_%j.log
#SBATCH --time=14-00:00:00

# 3-way resource comparison, all on the same node/hardware so the three
# numbers are directly comparable without relying on results from a
# different cluster:
#   - RRI-SWMM            (2 CPUs)
#   - SWMM 5.2 standalone  (2 CPUs, THREADS=2 -- "fair" case, same as
#                            slurm_fair_comparison.sh)
#   - SWMM 5.2 standalone  (1 CPU,  THREADS=1 -- SWMM's best possible
#                            single-CPU performance, not the THREADS=4
#                            mismatch used in the original slurm_tiempos_5.sh)
#
# Run this from its own clone/checkout of the repo (not the same working
# directory as another benchmark that might still be running) -- RRI-SWMM
# writes to fixed paths (HIST/out/, RRI_model/out/) that aren't parameterized
# by model name, so two concurrent RRI-SWMM runs in the same directory would
# clobber each other's output regardless of how the SWMM .inp/.out files are
# named.
#
# Same thread-limiting env vars as slurm_tiempos_5.sh / slurm_fair_comparison.sh,
# so RRI's and Python's own behavior stays identical across all three
# experiments -- only SWMM's own CPU/THREADS configuration is varied here.

export OMP_NUM_THREADS=1
export OMP_DYNAMIC=FALSE
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1

source /opt/anaconda3/bin/activate
conda activate /opt/anaconda3/envs/swmm_env

# Generate the THREADS variants (idempotent, safe to re-run)
python make_threads_variant.py SWMM_model/model.inp 2
python make_threads_variant.py benchmark/model.inp 2
python make_threads_variant.py benchmark/model.inp 1

ejecutar_rriswmm() {
    rm -rf HIST/out/ && echo "HIST/out borrado"
    rm -rf RRI_model/out/ && echo "RRI_model/out borrado"
    srun --cpus-per-task=2 --cpu-bind=cores python main_parallel_with_logger.py --swmm-model-name model_threads2

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="

    if [ -f "SWMM_model/model_threads2.rpt" ]; then
        tail -n 5 "SWMM_model/model_threads2.rpt"
        cp "SWMM_model/model_threads2.rpt" "SWMM_model/3way_rriswmm${i}.rpt"
    else
        echo "ALERTA: El archivo model_threads2.rpt no fue generado."
    fi
    echo "==========================================="
}

ejecutar_swmm_2cpu() {
    cd benchmark/
    rm -f model_threads2.out
    # OMP_NUM_THREADS is 1 for the whole script (so RRI stays single-threaded);
    # override it here so SWMM's own OpenMP routing can actually use 2 threads,
    # matching the THREADS=2 requested in model_threads2.inp.
    # Set it via `env` on the remote process itself, rather than `srun --export`:
    # for job steps nested inside an sbatch allocation, --export's precedence vs.
    # the already-exported OMP_NUM_THREADS=1 is inconsistent across Slurm versions
    # (confirmed on the cluster used for slurm_fair_comparison.sh: --export=ALL,...
    # was silently ignored, ps -T and /proc/<pid>/environ both still showed
    # 1 thread / OMP=1; `env VAR=val cmd` fixed it).
    srun --cpus-per-task=2 --cpu-bind=cores env OMP_NUM_THREADS=2 ./runswmm model_threads2.inp "3way_swmm2cpu${i}.rpt" model_threads2.out
    cd ..

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="

    if [ -f "benchmark/3way_swmm2cpu${i}.rpt" ]; then
        tail -n 5 "benchmark/3way_swmm2cpu${i}.rpt"
    else
        echo "ALERTA: El archivo .rpt no fue generado."
    fi
    echo "==========================================="
}

ejecutar_swmm_1cpu() {
    cd benchmark/
    rm -f model_threads1.out
    # No env override needed here: OMP_NUM_THREADS=1 (set for the whole
    # script) already matches THREADS=1 in model_threads1.inp.
    srun --cpus-per-task=1 --cpu-bind=cores ./runswmm model_threads1.inp "3way_swmm1cpu${i}.rpt" model_threads1.out
    cd ..

    echo "==========================================="
    echo " RESUMEN DEL REPORTE (Iteración $i) "
    echo "==========================================="

    if [ -f "benchmark/3way_swmm1cpu${i}.rpt" ]; then
        tail -n 5 "benchmark/3way_swmm1cpu${i}.rpt"
    else
        echo "ALERTA: El archivo .rpt no fue generado."
    fi
    echo "==========================================="
}

echo "Iniciando Benchmark 3 vias (RRI-SWMM 2cpu / SWMM 5.2 2cpu / SWMM 5.2 1cpu): $(date)"
echo "-------------------------------------------"

for i in $(seq 1 11); do
    echo "--- Iteración $i ---"

    echo -n "SWMM: 5.2 "
    echo "$(date)"
    ejecutar_swmm_2cpu

    echo -n "SWMM 5.2 1cpu: "
    echo "$(date)"
    ejecutar_swmm_1cpu

    echo -n "RRI-SWMM: "
    echo "$(date)"
    ejecutar_rriswmm
done

echo "-------------------------------------------"
echo "Benchmark finalizado: $(date)"
