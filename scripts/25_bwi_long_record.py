"""BWI long-record air temperature: trends over different windows and a test for acceleration.

GHCN-Daily USW00093721 (1939-2025). Seasonal / annual mean Tmax and Tmin per year (years with
>= 90% of the maximum day count). (1) OLS trends for windows ending 2025 and the distribution of
all 13-year window trends since 1940; (2) acceleration test for 1970-2025: hinge model
T ~ year + (year - 2000)+ and a quadratic, HAC standard errors (2 lags).

Run: conda run -p .\\env python scripts\\25_bwi_long_record.py
"""
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
SERIES = [("Jul-Aug Tmax", "TMAX", [7, 8]), ("Jun-Aug Tmax", "TMAX", [6, 7, 8]),
          ("Annual Tmax", "TMAX", list(range(1, 13))), ("Annual Tmin", "TMIN", list(range(1, 13)))]


def yearly(d, col, months):
    s = d[d.m.isin(months)].groupby("y")[col].agg(["mean", "count"])
    return s[s["count"] >= 0.9 * s["count"].max()]["mean"]


def main():
    d = pd.read_csv(ROOT / "data/raw/noaa/ghcnd_USW00093721.csv", usecols=["DATE", "TMAX", "TMIN"],
                    parse_dates=["DATE"], low_memory=False)
    d["y"], d["m"] = d.DATE.dt.year, d.DATE.dt.month
    for c in ("TMAX", "TMIN"):
        d[c] = d[c] / 10  # tenths of deg C -> deg C

    rows = []
    for lab, col, months in SERIES:
        s = yearly(d, col, months)
        s = s[(s.index >= 1940) & (s.index <= 2025)]
        row = {"series": lab}
        for a, b in [(1940, 2025), (1970, 2025), (1990, 2025), (2000, 2025), (2013, 2025)]:
            w = s[(s.index >= a) & (s.index <= b)]
            r = stats.linregress(w.index, w.values)
            row[f"{a}-{b}"] = f"{r.slope * 10:+.2f} (p {r.pvalue:.2f})"
        tr = [stats.linregress(s.loc[y0:y0 + 12].index, s.loc[y0:y0 + 12].values).slope * 10
              for y0 in range(1940, 2014) if len(s.loc[y0:y0 + 12]) >= 12]
        row["13yr trends: median"] = f"{np.median(tr):+.2f}"
        row["13yr: 90th pct"] = f"{np.percentile(tr, 90):+.2f}"
        row["2013-25 rank"] = f"{int(np.sum(np.array(tr) < tr[-1])) + 1}/{len(tr)}"
        rows.append(row)
    pd.set_option("display.width", 200)
    print("Trends in deg C per decade:\n", pd.DataFrame(rows).set_index("series").T.to_string())

    print()
    for lab, col, months in SERIES:
        s = yearly(d, col, months)
        s = s[(s.index >= 1970) & (s.index <= 2025)].rename("T").reset_index()
        s["x"], s["xl"] = s.y - 1970, (s.y - 2000).clip(lower=0)
        m = smf.ols("T ~ x + xl", data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        q = smf.ols("T ~ x + I(x**2)", data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        print(f"{lab}: 1970-99 slope {m.params.x * 10:+.2f} C/dec; change after 2000 {m.params.xl * 10:+.2f} "
              f"(p {m.pvalues.xl:.3f}) -> post-2000 {(m.params.x + m.params.xl) * 10:+.2f}; "
              f"quadratic term p {q.pvalues['I(x ** 2)']:.3f}")

    # (3) 2013-2025 vs 2000-2012: separate lines (slope and intercept free) and a continuous hinge at 2013
    print("\n2013-2025 vs 2000-2012 (deg C per decade; 95% CI; HAC SEs):")
    for lab, col, months in SERIES:
        s = yearly(d, col, months)
        s = s[(s.index >= 2000) & (s.index <= 2025)].rename("T").reset_index()
        s["x"], s["late"] = s.y - 2000, (s.y >= 2013).astype(int)
        s["xl"] = (s.y - 2013).clip(lower=0)
        sep = smf.ols("T ~ x * late", data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        hin = smf.ols("T ~ x + xl", data=s).fit(cov_type="HAC", cov_kwds={"maxlags": 2})
        e1, e2 = stats.linregress(s.y[s.late == 0], s["T"][s.late == 0]), stats.linregress(s.y[s.late == 1], s["T"][s.late == 1])
        ci_s, ci_h = sep.conf_int().loc["x:late"] * 10, hin.conf_int().loc["xl"] * 10
        print(f"  {lab:13s} 2000-12 {e1.slope * 10:+.2f}, 2013-25 {e2.slope * 10:+.2f} | difference, separate lines "
              f"{sep.params['x:late'] * 10:+.2f} [{ci_s[0]:+.2f}, {ci_s[1]:+.2f}] p {sep.pvalues['x:late']:.2f}; "
              f"continuous hinge {hin.params.xl * 10:+.2f} [{ci_h[0]:+.2f}, {ci_h[1]:+.2f}] p {hin.pvalues.xl:.2f}; "
              f"mean 2013-25 minus 2000-12 {s["T"][s.late == 1].mean() - s["T"][s.late == 0].mean():+.2f} C")


if __name__ == "__main__":
    main()
