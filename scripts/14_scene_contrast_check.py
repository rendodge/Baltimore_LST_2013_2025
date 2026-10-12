"""Diagnostic: hot-minus-cool LST contrast per scene (>= 80% impervious vs >= 70% canopy, CC 2021/22)
vs year, day of year, BWI air temperature and sensor, for the variant-B L8 + L9 scenes.
Run: conda run -p .\\env python scripts\\14_scene_contrast_check.py
"""
import importlib.util, numpy as np, pandas as pd, rasterio, geopandas as gpd
import statsmodels.formula.api as smf
from rasterio.features import geometry_mask
spec=importlib.util.spec_from_file_location("lst","scripts/02_lst_trend.py"); L=importlib.util.module_from_spec(spec); spec.loader.exec_module(L)
def rd(p):
    with rasterio.open(p) as s: a=s.read(1).astype(float); return np.where(a==s.nodata,np.nan,a)
with rasterio.open("data/processed/lst_trend/B_rel_slope_ols.tif") as s: tr,sh=s.transform,s.shape
city=geometry_mask(gpd.read_file(L.NSA).to_crs(32618).geometry,out_shape=sh,transform=tr,invert=True)
sc,st,_=L.load_scenes(city,("LC08","LC09"))
wx=pd.read_csv("data/processed/lst_trend_lc08_lc09/C_scene_weather.csv")[["scene_id","tair_C","prcp_prev3d_mm"]]
sc=sc.merge(wx,on="scene_id",how="left"); use=(sc.clear_frac_city>=0.5).values
imp=sum(rd(f"data/processed/cc_lulc/cc_frac_{g}_2021_utm.tif") for g in ("structures","roads","other_imperv"))
can=rd("data/processed/cc_lulc/cc_frac_canopy_2021_utm.tif"); wat=rd("data/processed/cc_lulc/cc_frac_water_2021_utm.tif")
land=city&(np.nan_to_num(wat)<10)&np.isfinite(imp)
hot=land&(imp>=80); cool=land&(can>=70)
rows=[]
for i in np.flatnonzero(use):
    a=st[i]; ok=np.isfinite(a)
    h=a[hot&ok]; c=a[cool&ok]
    if h.size<500 or c.size<500: continue
    x=imp[land&ok]; y=a[land&ok]
    rows.append({"scene":sc.scene_id[i],"sensor":sc.scene_id[i][:4],"year":sc.year[i],"doy":pd.Timestamp(sc.scene_id[i][17:25]).dayofyear,"tair":sc.tair_C[i],"prcp3d":sc.prcp_prev3d_mm[i],
                 "contrast":np.median(h)-np.median(c),"sd":np.nanstd(y),"slope_per10":np.polyfit(x,y,1)[0]*10})
d=pd.DataFrame(rows); pd.set_option("display.width",200)
print(d.round(2).to_string(index=False))
for f in ["contrast ~ year","contrast ~ year + tair","contrast ~ year + tair + C(sensor)","slope_per10 ~ year + tair"]:
    m=smf.ols(f,data=d).fit(); print(f"{f:40s}", " | ".join(f"{k} {m.params[k]:+.3f} (p {m.pvalues[k]:.3f})" for k in m.params.index if k!="Intercept"), f"| n {int(m.nobs)} r2 {m.rsquared:.2f}")
print("---")
for f in ["contrast ~ doy","contrast ~ doy + year","contrast ~ doy + year + tair + C(sensor)"]:
    m=smf.ols(f,data=d).fit(); print(f"{f:42s}", " | ".join(f"{k} {m.params[k]:+.3f} (p {m.pvalues[k]:.3f})" for k in m.params.index if k!="Intercept"), f"| r2 {m.rsquared:.2f}")
print("mean doy by period: 2013-2018 %.0f | 2019-2021 %.0f | 2022-2025 %.0f" % tuple(d[(d.year>=a)&(d.year<=b)].doy.mean() for a,b in ((2013,2018),(2019,2021),(2022,2025))))
print("doy ~ year:", smf.ols("doy ~ year",data=d).fit().params.year.round(2), "days/yr")
