#!/bin/bash
# Correr esto DESDE la raiz del repo en el cluster (donde estan main.py, RRI_model/, etc.)
# despues de haber corrido build_variants.sh. Prueba cada binario contra el escenario
# exacto que cuelga: primer paso, condiciones iniciales en seco.
BUILD_DIR="RRI_source/1.4.2.7-20260121T122640Z-3-001/1.4.2.7"
TIMEOUT_S=300

for NAME in 0_rri_test_O3 0_rri_test_strict 0_rri_test_O0; do
  BIN="$BUILD_DIR/$NAME"
  if [ ! -f "$BIN" ]; then
    echo "=== $NAME: no encontrado, saltando ==="
    continue
  fi

  TESTDIR=$(mktemp -d)
  cp -r RRI_model/input_files "$TESTDIR/"
  cp -r RRI_model/rain "$TESTDIR/"
  cp RRI_model/RRI_Input.txt "$TESTDIR/"
  mkdir -p "$TESTDIR/out"
  cp "$BIN" "$TESTDIR/0_rri_1_4_2_7"
  chmod +x "$TESTDIR/0_rri_1_4_2_7"

  # condiciones iniciales en seco, igual que write_hs_grid en main_parallel_with_logger.py
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

  cp "$TESTDIR/rain/PREC_20240318_2040.txt" "$TESTDIR/rain/P.txt"

  echo "=== Testing $NAME ==="
  cd "$TESTDIR"
  SECONDS=0
  timeout ${TIMEOUT_S}s ./0_rri_1_4_2_7 > stdout.log 2>&1
  RC=$?
  ELAPSED=$SECONDS
  cd - > /dev/null

  if [ "$RC" -eq 124 ]; then
    echo "$NAME: TIMEOUT despues de ${TIMEOUT_S}s (cuelga, igual que el binario actual)"
  elif [ "$RC" -eq 0 ]; then
    echo "$NAME: OK, termino en ${ELAPSED}s"
    grep -i "shrink" "$TESTDIR/stdout.log" && echo "  (nota: si hubo shrinks, igual termino)" || echo "  (sin shrinks, como el .exe de Windows)"
  else
    echo "$NAME: fallo con codigo $RC, ver $TESTDIR/stdout.log"
  fi
  echo "  (archivos de prueba en: $TESTDIR)"
done
