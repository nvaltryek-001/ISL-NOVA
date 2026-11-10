# ISL NOVA project report

[`ISL_NOVA_Project_Report.pdf`](ISL_NOVA_Project_Report.pdf): 26 pages, 11 chapters (chapter 11: ISL NOVA 2.0 and 3.0). All figures come from genuine project artifacts: the released model's `metrics.json` and training log, `comparison.json` and `open_set_rows.csv` from the model release, the published landmark dataset, and Playwright screenshots of the app.

Regenerate (needs matplotlib and Playwright with Chromium):

```bash
python docs/report/src/charts.py <out_dir> <include-landmarks-v1 dir> <repo root>   # writes <out_dir>/img/*.png
python docs/report/src/charts_v3.py <out_dir> <v3 comparison.json> <v3 open_set_v3.json> 84.93   # chapter 11 charts
# copy docs/screenshots to <out_dir>/build/shots and img to <out_dir>/build/img,
# replace SHOTS/ -> shots/ and IMG/ -> img/ in report.html, then:
python docs/report/src/render.py <out_dir>/build/report.html ISL_NOVA_Project_Report.pdf
```

Dataset images are rendered from INCLUDE landmarks (Sridhar et al., ACM MM 2020, CC BY 4.0).
