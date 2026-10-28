# Thesis proposal

- `thesis_proposal/Thesis_Proposal.tex` follows the department template in `Sample_Thesis_Tex_format_2026/` (IU, Department of Mathematics).
- Build: `~/.local/bin/tectonic.exe Thesis_Proposal.tex`. Use XeTeX-safe fonts; `\mathbbm` breaks xdvipdfmx.
- Figures are regenerated from repo data with `python docs/proposal/thesis_proposal/make_figures.py`.
