import time
from pathlib import Path

import fire
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# list of drugs to monitor
drugs_regex_dict: dict[str, str] = {
    "Methylphenidate": r"\bmethylphenidat",
    "Lisdexamfetamine": r"\blisdexam(?:f|ph)etamin",
    "Dexamfetamine": r"\bdexam(?:f|ph)etamin",
    "Atomoxetine": r"\batomoxetin",
    "Guanfacine": r"\bguanfacin",
    "Clonidine": r"\bclonidin"
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

    if disable_cache:
        load_df = _load_df
    else:
        from joblib import Memory
        mem = Memory("cache", verbose=0)
        load_df = mem.cache(_load_df)

    p(f"Disabled cache: {bool(disable_cache)}")

    p(f"Loading source {source}")
    df = load_df(source=source)
    p("Done loading.")

    eu_countries = sorted(list(set(df["Country"].tolist())))

    drugs_country_list = {}
    for drug_name, drug_regex in drugs_regex_dict.items():
        p(f"Filtering data for {drug_name}")
        drug_df = df[df["Name"].str.contains(drug_regex, case=False)]

        # get the list of each country for each drug
        countries = list(set(drug_df["Country"].tolist()))
        for ic, c in enumerate(countries):
            if c.lower().strip() == "european union":
                code = "Europe"
            else:
                code = c
            countries[ic] = code
        drugs_country_list[drug_name] = sorted(countries)

    p("Loading Europe map")
    geomap = pd.DataFrame(eu_countries, columns=["country"])

    geomap["medications"] = ""
    geomap = geomap.reset_index().set_index("country")
    for drug_name, countries in drugs_country_list.items():
        p(f"Adding {drug_name} to the map")

        geomap.loc[:, drug_name] = "Missing"
        geomap.loc[:, f"color_{drug_name}"] = 0

        for cnt in countries:
            if cnt == "Europe":
                for cnt in eu_countries:
                    if drug_name in geomap.loc[cnt, "medications"]:
                        continue
                    if geomap.loc[cnt, "medications"] == "":
                        geomap.loc[cnt, "medications"] = drug_name
                    else:
                        geomap.loc[cnt, "medications"] += ", " + drug_name
                    geomap.loc[cnt, f"color_{drug_name}"] = 1
            else:
                if drug_name in geomap.loc[cnt, "medications"]:
                    continue
                if geomap.loc[cnt, "medications"] == "":
                    geomap.loc[cnt, "medications"] = drug_name
                else:
                    geomap.loc[cnt, "medications"] += ", " + drug_name

            geomap.loc[cnt, drug_name] = "Available"
            geomap.loc[cnt, f"color_{drug_name}"] = 1


    p("Creating the plot")
    figs = make_subplots(
        rows=1,
        cols=1,
        subplot_titles=["European ADHD medication"],
        specs=[[{"type": "geo"}]],
    )
    steps = []
    geomap = geomap.reset_index().set_index("index")
    colorscale = [[0, "rgb(255, 0, 0)"], [1, "rgb(0, 255, 0)"]]
    colorscale_all_1 = [[0, "rgb(0, 255, 0)"], [1, "rgb(0, 255, 0)"]]
    colorscale_all_0 = [[0, "rgb(255, 0, 0)"], [1, "rgb(255, 0, 0)"]]

    list_of_figs = []

    for drug_name in drugs_country_list:
        fig = go.Choropleth(
            locations=geomap["country"],
            locationmode="country names",
            z=geomap[f"color_{drug_name}"],
            hoverinfo="text",
            text=[f"{a}<br>{b}" for a, b in zip(geomap["country"], geomap["medications"])],
            showscale=False,
        )

        # set colorscale
        vals = list(set(geomap[f"color_{drug_name}"].tolist()))
        if len(vals) == 1:
            # use uniquecolor colorscale if it's the same z value for all countries
            if vals[0] == 0:
                fig.colorscale=colorscale_all_0
            elif vals[0] == 1:
                fig.colorscale=colorscale_all_1
            else:
                raise ValueError(vals)
        else:
            fig.colorscale=colorscale

        list_of_figs.append(fig) # for png storage

        figs.add_trace(fig, row=1, col=1)

        # Only show the current medication and hide all the others
        visible = [drug_name == name for name in drugs_country_list]

        step = dict(
            method="update",
            args=[{"visible": visible},
                {"title": drug_name}],
            label=drug_name,
        )
        steps.append(step)

    figs.update_geos(scope='europe')
    sliders = [dict(
        active=0,
        currentvalue={"prefix": "Select medication: "},
        steps=steps
    )]
    figs.update_layout(sliders=sliders)

    if show_or_export in ["export", "both"]:
        exp_time = str(int(time.time()))
        exp_dir = Path() / f"export_{exp_time}"
        exp_dir.mkdir(exist_ok=False)
        exp_path = exp_dir.resolve().absolute().__str__() + "/"
        p("Exporting as html")
        figs.write_html(f"{exp_path}map_export.html")
        p("Exporting as json")
        figs.write_json(f"{exp_path}map_export.json")
        # p("Exporting as pdf")
        # figs.write_image(f"{exp_path}map_export.pdf")
        p("Exporting each medication as png")
        for drug, fig in zip(drugs_country_list.keys(), list_of_figs):
            fig = go.Figure(fig)
            fig.update_layout(title_text=drug.title())
            fig.update_geos(scope='europe')
            fig.write_image(f"{exp_path}map_export_{drug}.png")
    if show_or_export in ["show", "both"]:
        p("Showing map, press ctrl+c to exit")
        try:
            figs.show()
        except KeyboardInterrupt:
            p("Continuing")

    p("Done")

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
