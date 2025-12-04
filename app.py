import json
import os

import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title="Weather App – SPC + NC4", layout="wide")
st.title("Weather App – SPC Outlook + NC4 GeoJSON Volume")

# --------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------
def compute_view_state(geojson_dict: dict, default_center=(39.5, -98.35), zoom=4):
    """Compute a simple center point for polygons/lines in GeoJSON."""
    lats, lons = [], []

    def walk_coords(coords):
        # handle nested list structures for polygons/multipolygons/lines
        if isinstance(coords[0], (float, int)):
            lon, lat = coords[:2]
            lons.append(lon)
            lats.append(lat)
        else:
            for c in coords:
                walk_coords(c)

    for feature in geojson_dict.get("features", []):
        geom = feature.get("geometry") or {}
        if "coordinates" in geom:
            walk_coords(geom["coordinates"])

    if not lats:
        lat, lon = default_center
        return pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom)

    return pdk.ViewState(
        latitude=sum(lats) / len(lats),
        longitude=sum(lons) / len(lons),
        zoom=zoom,
    )


# --------------------------------------------------------------------
# SPC tab
# --------------------------------------------------------------------
SPC_DEFAULT_URL = os.environ.get(
    "SPC_GEOJSON_URL",
    "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.nolyr.geojson",
)

SPC_OPTIONS = {
    "Day 1 Categorical (nolyr)": "https://www.spc.noaa.gov/products/outlook/day1otlk_cat.nolyr.geojson",
    "Day 1 Tornado (nolyr)": "https://www.spc.noaa.gov/products/outlook/day1otlk_torn.nolyr.geojson",
    "Day 1 Wind (nolyr)": "https://www.spc.noaa.gov/products/outlook/day1otlk_wind.nolyr.geojson",
    "Day 1 Hail (nolyr)": "https://www.spc.noaa.gov/products/outlook/day1otlk_hail.nolyr.geojson",
    "Day 2 Categorical (nolyr)": "https://www.spc.noaa.gov/products/outlook/day2otlk_cat.nolyr.geojson",
    "Day 3 Categorical (nolyr)": "https://www.spc.noaa.gov/products/outlook/day3otlk_cat.nolyr.geojson",
}


@st.cache_data(show_spinner=True)
def load_geojson_from_url(url: str) -> dict:
    resp = requests.get(url, timeout=15)
    resp.raise_for_status()
    return resp.json()


# --------------------------------------------------------------------
# NC4 volume tab
# --------------------------------------------------------------------
NC4_ROOT = os.environ.get("NC4_ROOT")  # /Volumes/inv_weather_dev/nc4/geojson
NC4_DEFAULT_FILE = os.environ.get("NC4_DEFAULT_FILE", "overlay_result.geojson")


@st.cache_data(show_spinner=True)
def list_nc4_geojson(root: str):
    """List all .geojson files under NC4_ROOT (relative paths)."""
    matches = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".geojson"):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root)
                matches.append(rel)
    return sorted(matches)


@st.cache_data(show_spinner=True)
def load_geojson_from_file(path: str) -> dict:
    with open(path, "r") as f:
        return json.load(f)


# --------------------------------------------------------------------
# Layout: tabs
# --------------------------------------------------------------------
tab_spc, tab_nc4 = st.tabs(["SPC Outlook", "NC4 GeoJSON (UC Volume)"])

# =======================
# Tab 1: SPC Outlook
# =======================
with tab_spc:
    st.subheader("SPC Convective Outlook")

    st.markdown(
        """
        This tab fetches **live SPC convective outlook GeoJSON** from `spc.noaa.gov`
        and renders it on an interactive map.
        """
    )

    with st.expander("SPC GeoJSON selection", expanded=True):
        labels = list(SPC_OPTIONS.keys())

        default_index = 0
        if SPC_DEFAULT_URL in SPC_OPTIONS.values():
            default_index = labels.index(
                [k for k, v in SPC_OPTIONS.items() if v == SPC_DEFAULT_URL][0]
            )

        label = st.selectbox("SPC outlook type", options=labels, index=default_index)
        url = SPC_OPTIONS[label]

        st.write("**Selected URL:**")
        st.code(url, language="text")

    try:
        geojson_spc = load_geojson_from_url(url)
    except requests.exceptions.RequestException as e:
        st.error(
            "Error fetching GeoJSON from SPC.\n\n"
            f"Details: {e}"
        )
    else:
        st.subheader("SPC GeoJSON (preview)")
        st.json(geojson_spc, expanded=False)

        st.subheader("SPC Map")
        view_spc = compute_view_state(geojson_spc)
        layer_spc = pdk.Layer(
            "GeoJsonLayer",
            data=geojson_spc,
            pickable=True,
            stroked=True,
            filled=True,
            auto_highlight=True,
        )
        deck_spc = pdk.Deck(
            layers=[layer_spc],
            initial_view_state=view_spc,
            tooltip={"text": "{LABEL}"},
        )
        st.pydeck_chart(deck_spc)

# =======================
# Tab 2: NC4 volume GeoJSON
# =======================
with tab_nc4:
    st.subheader("NC4 GeoJSON from Unity Catalog Volume")

    st.markdown(
        """
        This tab reads one of the `.geojson` files from:

        ```text
        /Volumes/inv_weather_dev/nc4/geojson/
        ```

        and renders it on a map.
        """
    )

    st.write("**NC4_ROOT env:**")
    st.code(str(NC4_ROOT), language="text")

    if not NC4_ROOT:
        st.error(
            "NC4_ROOT is not set.\n\n"
            "Check `app.yaml` env:\n"
            "  - name: NC4_ROOT\n"
            "    value: \"/Volumes/inv_weather_dev/nc4/geojson\""
        )
    else:
        st.write("Listing `.geojson` files under that root:")

        try:
            files = list_nc4_geojson(NC4_ROOT)
        except Exception as e:
            st.error(f"Error walking NC4_ROOT: {e}")
            files = []

        if files:
            st.write(files)
            default_index = 0
            if NC4_DEFAULT_FILE in files:
                default_index = files.index(NC4_DEFAULT_FILE)
            rel_path = st.selectbox(
                "Choose a GeoJSON file", options=files, index=default_index
            )
        else:
            st.warning(
                "No `.geojson` files found under NC4_ROOT. "
                "Expected to see things like:\n"
                "  - day1otlk_20250818_0100_cat.lyr.geojson\n"
                "  - overlay_result.geojson"
            )
            rel_path = st.text_input("Relative path to GeoJSON", value=NC4_DEFAULT_FILE)

        full_path = os.path.join(NC4_ROOT, rel_path)
        st.write("**Full path:**")
        st.code(full_path, language="text")

        exists = os.path.exists(full_path)
        st.write(f"`os.path.exists` on that path: **{exists}**")

        if not exists:
            st.error(
                "The path above does **not** exist from the app's POV.\n\n"
                "If this persists even though you see the file in the UI, "
                "it's almost certainly a permissions or mounting issue, not the code."
            )
        else:
            try:
                geojson_nc4 = load_geojson_from_file(full_path)
            except Exception as e:
                st.error(f"Error loading GeoJSON from file: {e}")
            else:
                st.subheader("NC4 GeoJSON (preview)")
                st.json(geojson_nc4, expanded=False)

                st.subheader("NC4 Map")
                view_nc4 = compute_view_state(geojson_nc4, zoom=4)
                layer_nc4 = pdk.Layer(
                    "GeoJsonLayer",
                    data=geojson_nc4,
                    pickable=True,
                    stroked=True,
                    filled=True,
                    auto_highlight=True,
                )
                deck_nc4 = pdk.Deck(
                    layers=[layer_nc4],
                    initial_view_state=view_nc4,
                    tooltip={"text": "{name}"},  # we'll tune after we see the files
                )
                st.pydeck_chart(deck_nc4)



