# ISL NOVA project report

[`ISL_NOVA_Project_Report.pdf`](ISL_NOVA_Project_Report.pdf): 23 pages, 10 chapters. All figures come from genuine project artifacts: the released model's `metrics.json` and training log, `comparison.json` and `open_set_rows.csv` from the model release, the published landmark dataset, and Playwright screenshots of the app.

Regenerate (needs matplotlib and Playwright with Chromium):

```bash
python docs/report/src/charts.py <out_dir> <include-landmarks-v1 dir> <repo root>   # writes <out_dir>/img/*.png
# copy docs/screenshots to <out_dir>/build/shots and img to <out_dir>/build/img,
# replace SHOTS/ -> shots/ and IMG/ -> img/ in report.html, then:
python docs/report/src/render.py <out_dir>/build/report.html ISL_NOVA_Project_Report.pdf
```

Dataset images are rendered from INCLUDE landmarks (Sridhar et al., ACM MM 2020, CC BY 4.0).
