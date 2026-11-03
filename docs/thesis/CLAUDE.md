# Graduation thesis

- `Thesis.tex` follows the department template in `../proposal/Sample_Thesis_Tex_format_2026/`. `Thesis_noDSR.tex` builds the variant without the DSR subsection (`\ifdsr`).
- Build both: `~/.local/bin/tectonic.exe Thesis.tex` and `~/.local/bin/tectonic.exe Thesis_noDSR.tex`. XeTeX-safe fonts only; `\mathbbm` breaks xdvipdfmx.
- Figures: `.venv/Scripts/python.exe docs/thesis/make_figures.py` (from the repo root) rewrites `figures/*.png` from `results/`.
- Every number in the text comes from `docs/RESULTS.md`; change RESULTS first, then the text. Signature lines stay blank: the student and supervisor sign the printed copy.
- The web serves `Thesis.pdf` / `Thesis_noDSR.pdf` at `/thesis`.
