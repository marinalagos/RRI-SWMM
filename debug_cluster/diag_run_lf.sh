#!/bin/bash
# Igual que diag_run.sh, pero convierte P.txt a fin de linea Unix (LF) antes de correr,
# para probar la hipotesis de que el CRLF es la causa del loop infinito al leer
# el archivo de lluvia.
#
# Uso: bash debug_cluster/diag_run_lf.sh [NOMBRE_BINARIO] [SEGUNDOS]

set -u

NAME="${1:-0_rri_test_O0}"
SECS="${2:-30}"
BUILD_DIR="RRI_source/1.4.2.7-20260121T122640Z-3-001/1.4.2.7"
BIN="$BUILD_DIR/$NAME"

if [ ! -f "$BIN" ]; then
  echo "No encontre $BIN. Corre primero: bash debug_cluster/build_variants.sh"
  exit 1
fi

TESTDIR=$(mktemp -d)
cp -r RRI_model/input_files "$TESTDIR/"
cp -r RRI_model/rain "$TESTDIR/"
cp RRI_model/RRI_Input.txt "$TESTDIR/"
mkdir -p "$TESTDIR/out"
cp "$BIN" "$TESTDIR/0_rri_1_4_2_7"
chmod +x "$TESTDIR/0_rri_1_4_2_7"

python3 - "$TESTDIR" <<'PYEOF'
import sys
sys.path.insert(0, ".")
from helper_functions import read_ascii_raster_no_data, write_hs_grid
from pathlib import Path
testdir = Path(sys.argv[1])
nrows, ncols, cells_size, hs = read_ascii_raster_no_data(testdir / "input_files" / "DEM.asc")
out = testdir / "out"
write_hs_grid(hs, out_file=out/"gampt_ff_000001.out", nodata_value=-0.10000)
write_hs_grid(hs, out_file=out/"hs_000001.out", nodata_value=-0.10000)
write_hs_grid(hs, out_file=out/"hr_000001.out", nodata_value=-0.10000)
write_hs_grid(hs, out_file=out/"qr_000001.out", nodata_value=-0.10000)
PYEOF

# Aca esta la diferencia: convertir CRLF -> LF al armar P.txt
tr -d '\r' < "$TESTDIR/rain/PREC_20240318_2040.txt" > "$TESTDIR/rain/P.txt"

echo "=== Verificando fin de linea de P.txt (no deberia haber '^M') ==="
head -c 200 "$TESTDIR/rain/P.txt" | cat -A | head -2

echo "=== Corriendo $NAME por ${SECS}s (P.txt con LF) en $TESTDIR ==="
cd "$TESTDIR"
timeout "${SECS}s" ./0_rri_1_4_2_7 > stdout.log 2>&1
RC=$?
echo "=== fin (codigo $RC). Ultimas 40 lineas del log: ==="
tail -n 40 stdout.log
cd - > /dev/null
echo "log completo en: $TESTDIR/stdout.log"
