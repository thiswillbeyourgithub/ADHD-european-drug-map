import time
import fire

import pycountry
import plotly.express as px
import pandas as pd
from plotly.subplots import make_subplots
import plotly.graph_objects as go


# list of drugs to monitor
# Syntax:
# "DRUGNAME": ["REGEX for the drug name column", {options for pd.DataFrame.str.contains}]
drugs_regex_dict = {
    "Atomoxetine": ["Atomoxetin.*", {"case": True}],
    "Clonidine": ["Clonidine.*", {"case": True}],
    "Dexamfetamine": ["Dexamfetamin.*", {"case": True}],
    "Guanfacine": ["Guanfacin.*", {"case": True}],
    "Lisdexamfetamine": ["Lisdexamfetamine.*", {"case": True}],
    "Methylphenidate": ["Methylphenidat.*", {"case": True}],
}


def main(
    source: str = "https://www.ema.europa.eu/en/documents/other/article-57-product-data_en.xlsx",
    #source: = "./article-57-product-data_en-copy.xlsx",
    disable_cache: bool = False,
    verbose: bool = True,
    show_or_export="show",
    debug: bool = False,
    ) -> None:
    """
    Parameters
    ----------

    source: str, default "https://www.ema.europa.eu/en/documents/other/article-57-product-data_en.xlsx"
        url or path to the EMA file

    disable_cache: bool, default False

    verbose: bool, default True

    show_or_export: str, default "show"
        either show, to open the figure in the browser, or "export" to export
        as html, json and png or "both" to do both.

    debug: bool, default False
        open pdb if something fails
    """
    assert show_or_export in ["show", "export", "both"], (
        f"Invalid show_or_export: {show_or_export}")
    if verbose:
        def p(message: str) -> None:
            print(message)
    else:
        def p(message: str) -> None:
            pass

    if debug:
        import signal
        import pdb
        signal.signal(signal.SIGINT, (lambda signal, frame : pdb.set_trace()))
        print("Debugging mode enabled")

    if not disable_cache:
        from joblib import Memory
        mem = Memory("cache", verbose=0)
        load_df = mem.cache(_load_df)
        get_country = mem.cache(_get_country)
    else:
        load_df = _load_df
        get_country = _get_country

    p(f"Disabled cache: {bool(disable_cache)}")

    p(f"Loading source {source}")
    df = load_df(source=source)
    p("Done loading.")

    drugs_df = {}
    drugs_country_list = {}
    for k, v in drugs_regex_dict.items():
        p(f"Filtering data for {k}")
        drug_df = df[df["Name"].str.contains(v[0], **v[1])]
        drugs_df[k] = drug_df

        # get the list of each country for each drug
        countries = set(drug_df["Country"].tolist())
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

    p("Loading Europe map")
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
        p(f"Adding {medication} to the map")
        countries = drugs_country_list[medication]

        map.loc[:, medication] = "Missing"
        map.loc[:, f"color_{medication}"] = 0

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

            map.loc[cnt, medication] = "Available"
            map.loc[cnt, f"color_{medication}"] = 1


    p("Creating the plot")
    figs = make_subplots(
        rows=1,
        cols=1,
        subplot_titles=["European ADHD medication"],
        specs=[[{"type": "geo"}]],
    )
    steps = []
    map = map.reset_index().set_index("index")
    colorscale = [[0, "rgb(255, 0, 0)"], [1, "rgb(0, 255, 0)"]]
    colorscale = [
        [0, '#FF0000'],    # Red
        [0.33, '#FF0000'], # Red
        [0.33, '#0000FF'], # Blue
        [0.67, '#0000FF'], # Blue
        [0.67, '#008000'], # Green
        [1.0, '#008000']   # Green
    ]


    for i, medication in enumerate(drugs_country_list):
        fig = go.Choropleth(
            locations=map["iso_alpha"],
            z=map[f"color_{medication}"],
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

    if show_or_export in ["export", "both"]:
        p("Exporting as html")
        figs.write_html(f"map_export_{int(time.time())}.html")
        p("Exporting as json")
        figs.write_json(f"map_export_{int(time.time())}.json")
        p("Exporting as png")
        figs.write_image(f"map_export_{int(time.time())}.png")
    elif show_or_export in ["show", "both"]:
        p("Showing map, press ctrl+c to exit")
        try:
            figs.show()
        except KeyboardException:
            p("Continuing")
    else:
        raise ValueError(f"Invalid show_or_export: {show_or_export}")

    p("Done")


def _get_country(fullname: str) -> str:
    "turn France into FRA"
    return pycountry.countries.search_fuzzy(fullname)[0].alpha_3


def _load_df(source: str) -> pd.DataFrame:
    "loading of pandas dataframe, optionnaly cached"
    df = pd.read_excel(source, skiprows=19)
    # rename columns then filter
    df.columns = [col.splitlines()[0] for col in df.columns]
    df = df.loc[:, ["Active substance", "Product authorisation country"]]
    df.columns = ["Name", "Country"]
    return df

if __name__ == "__main__":
    fire.Fire(main)
