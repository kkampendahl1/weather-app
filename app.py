import json
import os

import pydeck as pdk
import streamlit as st

st.set_page_config(page_title="Weather App – Direct GeoJSON Test", layout="wide")
st.title("Weather App – Direct GeoJSON Test")


# --- Get path from env ---

GEOJSON_PATH = os.environ.get("GEOJSON_PATH")

st.markdown(f"**GEOJSON_PATH env:** `{GEOJSON_PATH}`")

if not GEOJSON_PATH:
    st.error(
        "GEOJSON_PATH is not set.\n\n"
        "Check app.yaml env:\n"
        "  - name: GEOJSON_PATH\n"
        "    value: \"/Volumes/inv_weather_dev/forecasts/tropical_bi/tracks/model_tracks (1) (1).geojson\""
    )
    st.stop()

if not os.path.exists(GEOJSON_PATH):
    st.error(
        f"Path does **not** exist on the app filesystem:\n\n`{GEOJSON_PATH}`\n\n"
        "If this is surprising, double-check:\n"
        "• The UC volume path is correct.\n"
        "• The app has a UC volume resource and was redeployed after changes."
    )
    st.stop()


# --- Load GeoJSON ---

@st.cache_data(show_spinner=True)
def load_geojson(path: str):
    with open(path, "r") as f:
        return json.load(f)


geojson = load_geojson(GEOJSON_PATH)

st.subheader("Raw GeoJSON (preview)")
st.json(geojson, expanded=False)


# --- Compute a simple map view center ---

def compute_view_state(geojson_dict: dict) -> pdk.ViewState:
    lats, lons = [], []

    def walk_coords(coords):
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
        return pdk.ViewState(latitude=0, longitude=0, zoom=1)

    return pdk.ViewState(
        latitude=sum(lats) / len(lats),
        longitude=sum(lons) / len(lons),
        zoom=6,
    )


# --- Show map ---

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
    tooltip={"text": "{name}"},  # change property key once you see your data
)

st.pydeck_chart(deck)


