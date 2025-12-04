import json
import os

import pydeck as pdk
import requests
import streamlit as st

st.set_page_config(page_title="SPC Outlook Map Test", layout="wide")
st.title("SPC Convective Outlook – GeoJSON Map Test")

# --- SPC endpoints ---

# Default from env, but we’ll also offer presets:
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


def compute_view_state(geojson_dict: dict) -> pdk.ViewState:
    """Compute a simple center point for polygons."""
    lats, lons = [], []

    def walk_coords(coords):
        # handle nested list structures for polygons/multipolygons
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
        return pdk.ViewState(latitude=39.5, longitude=-98.35, zoom=3)  # CONUS-ish

    return pdk.ViewState(
        latitude=sum(lats) / len(lats),
        longitude=sum(lons) / len(lons),
        zoom=4,
    )


st.markdown(
    """
This page fetches **live SPC convective outlook GeoJSON** from `spc.noaa.gov`
and renders it on an interactive map.

If this works, we know:
- Outbound HTTP from the app is allowed
- GeoJSON + pydeck + Streamlit are wired correctly
"""
)

# --- UI controls ---

with st.expander("SPC GeoJSON selection", expanded=True):
    labels = list(SPC_OPTIONS.keys())

    # Try to make the env default the selected option; otherwise use first
    default_index = 0
    if SPC_DEFAULT_URL in SPC_OPTIONS.values():
        default_index = labels.index(
            [k for k, v in SPC_OPTIONS.items() if v == SPC_DEFAULT_URL][0]
        )

    label = st.selectbox("SPC outlook type", options=labels, index=default_index)
    url = SPC_OPTIONS[label]

    st.write("**Selected URL:**")
    st.code(url, language="text")

# --- Fetch GeoJSON ---

try:
    geojson = load_geojson_from_url(url)
except requests.exceptions.RequestException as e:
    st.error(
        "Error fetching GeoJSON from SPC.\n\n"
        "This may mean outbound internet is blocked from the app environment, "
        "or the SPC service is temporarily unavailable.\n\n"
        f"Details: {e}"
    )
    st.stop()

st.subheader("Raw GeoJSON (preview)")
st.json(geojson, expanded=False)

# --- Build map ---

st.subheader("Interactive map")

view_state = compute_view_state(geojson)

layer = pdk.Layer(
    "GeoJsonLayer",
    data=geojson,
    pickable=True,
    stroked=True,
    filled=True,
    auto_highlight=True,
)

deck = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    # Property names in SPC GeoJSON vary; once you see the JSON above,
    # you can change this to something specific (e.g. {risk} or {DN}).
    tooltip={"text": "{LABEL}"},
)

st.pydeck_chart(deck)


