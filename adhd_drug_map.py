import json
import pycountry
from joblib import Memory
import plotly.express as px
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go


mem = Memory("cache", verbose=0)

# list of drugs to monitor
drugs_regex_dict = {
        "Atomoxetine": ["Atomoxetin.*", {"case": True}],
        "Clonidine": ["Clonidine.*", {"case": True}],
        "Dexamfetamine": ["Dexamfetamin.*", {"case": True}],
        "Guanfacine": ["Guanfacin.*", {"case": True}],
        "Lisdexamfetamine": ["Lisdexamfetamine.*", {"case": True}],
        "Methylphenidate": ["Methylphenidat.*", {"case": True}],
    }

# up to date URL
url = "https://www.ema.europa.eu/en/documents/other/article-57-product-data_en.xlsx"
# local file
local_file = "./article-57-product-data_en-copy.xlsx"

@mem.cache
def get_country(fullname: str) -> str:
    "turn France into FRA"
    return pycountry.countries.search_fuzzy(fullname)[0].alpha_3

@mem.cache
def load_df(source):
    "cached loading of dataframe"
    print(f"Loading {source}")
    df = pd.read_excel(source, skiprows=19)

    # rename columns then filter
    df.columns = [col.splitlines()[0] for col in df.columns]
    df = df.loc[:, ["Active substance", "Product authorisation country"]]
    df.columns = ["Name", "Country"]

    return df

df = load_df(source=local_file)

# filter by the regex
drugs_df = {}
for k, v in drugs_regex_dict.items():
    drugs_df[k] = df[df["Name"].str.contains(v[0], **v[1])]

# get the list of each country for each drug
drugs_country_list = {}
for k, v in drugs_df.items():
    countries = set(v["Country"].tolist())
    countries = [c.split("(")[0].strip() for c in countries]
    for ic, c in enumerate(countries):
        if c.lower().strip() == "european union":
            code = "Europe"
        else:
            try:
                code = get_country(c)
            except Exception as err:
                print(err)
                breakpoint()
        countries[ic] = code
    drugs_country_list[k] = sorted(countries)

# load starting map
# 2007 is the most recent from that dataset
map = px.data.gapminder().query(f"year==2007")
# restrict to Europe
map = map[map.loc[:, "continent"] == "Europe"]
# remove useless columns
map = map.loc[:, ["country", "iso_alpha"]]

# add missing countries
map = pd.concat([map, pd.DataFrame([{"country": "Estonia", "iso_alpha": "EST"}])])
map = pd.concat([map, pd.DataFrame([{"country": "Lithuania", "iso_alpha": "LTU"}])])
map = pd.concat([map, pd.DataFrame([{"country": "Luxemburg", "iso_alpha": "LUX"}])])
map = pd.concat([map, pd.DataFrame([{"country": "Malta", "iso_alpha": "MLT"}])])
map = pd.concat([map, pd.DataFrame([{"country": "Chypria", "iso_alpha": "CYP"}])])
map = pd.concat([map, pd.DataFrame([{"country": "Liechtenstein", "iso_alpha": "LIE"}])])
map = pd.concat([map, pd.DataFrame([{"country": "Latvia", "iso_alpha": "LVA"}])])
assert not map.empty

map_iso = sorted(map["iso_alpha"].tolist())

map["medications"] = ""
map = map.reset_index().set_index("iso_alpha")
for i, medication in enumerate(drugs_country_list):
    countries = drugs_country_list[medication]
    map.loc[:, medication] = 0

    for cnt in countries:
        assert cnt in map_iso + ["Europe"], f"{cnt} not in {map_iso}"
        if cnt == "Europe":
            for cnt in map_iso:
                if medication in map.loc[cnt, "medications"]:
                    continue
                if map.loc[cnt, "medications"] == "":
                    map.loc[cnt, "medications"] = medication
                else:
                    map.loc[cnt, "medications"] += ", " + medication
        else:
            if medication in map.loc[cnt, "medications"]:
                continue
            if map.loc[cnt, "medications"] == "":
                map.loc[cnt, "medications"] = medication
            else:
                map.loc[cnt, "medications"] += ", " + medication

        map.loc[cnt, medication] = 1

map = map.reset_index().set_index("index")

figs = make_subplots(
    rows=1,
    cols=1,
    subplot_titles=["European ADHD medication"],
    specs=[[{"type": "geo"}]],
)
steps = []

for i, medication in enumerate(drugs_country_list):
    fig = go.Choropleth(
        locations=map["iso_alpha"],
        z=map[medication],
        colorscale=["white", "green"],
        hoverinfo="text",
        text=[f"{a}<br>{b}" for a, b in zip(map["country"], map["medications"])],
        showscale=False,
    )
    figs.add_trace(fig, row=1, col=1)
    step = dict(
        method="update",
        args=[{"visible": [False] * len(drugs_country_list)},
              {"title": medication}],
        label=medication,
    )
    step["args"][0]["visible"][i] = True  # Toggle i-th trace to "visible"
    steps.append(step)


figs.update_geos(scope='europe')
sliders = [dict(
    active=0,
    currentvalue={"prefix": "Select medication: "},
    steps=steps
)]
figs.update_layout(sliders=sliders)
figs.show()

import code ; code.interact(local=locals())

