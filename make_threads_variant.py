"""
Creates a copy of a SWMM .inp file with the [OPTIONS] THREADS value changed.

Used to build "fair" resource comparisons where SWMM's requested thread
count matches the number of CPUs actually allocated to it, instead of
leaving a mismatched default (see README / benchmark methodology notes).

Usage:
    python make_threads_variant.py path/to/model.inp N [output_path]

If output_path is omitted, writes to "<input_stem>_threads<N>.inp" next to
the input file.
"""

import argparse
import re
from pathlib import Path

THREADS_LINE = re.compile(r'(?m)^(THREADS[ \t]+)\d+[ \t]*$')


def make_variant(inp_path, threads, out_path=None):
    text = inp_path.read_text()

    new_text, n_subs = THREADS_LINE.subn(rf'\g<1>{threads}', text)
    if n_subs == 0:
        raise ValueError(f"No 'THREADS' option found in {inp_path} -- check the [OPTIONS] section.")
    if n_subs > 1:
        raise ValueError(f"Found {n_subs} 'THREADS' lines in {inp_path} -- expected exactly 1.")

    if out_path is None:
        out_path = inp_path.with_name(f"{inp_path.stem}_threads{threads}{inp_path.suffix}")

    out_path.write_text(new_text)
    return out_path


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('inp_path', type=Path)
    parser.add_argument('threads', type=int)
    parser.add_argument('output_path', type=Path, nargs='?', default=None)
    args = parser.parse_args()

    out_path = make_variant(args.inp_path, args.threads, args.output_path)
    print(f"Wrote {out_path} (THREADS={args.threads})")


if __name__ == '__main__':
    main()
