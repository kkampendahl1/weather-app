import json
import os

import pydeck as pdk
import streamlit as st


st.set_page_config(page_title="Weather App – GeoJSON Map", layout="wide")
st.title("Weather App – GeoJSON from Unity Catalog Volume")


# --- Environment configuration ---

VOLUME_ROOT = os.environ.get("VOLUME_PATH")  # from app.yaml valueFrom: volume
DEFAULT_REL_PATH = os.environ.get(
    "GEOJSON_REL_PATH", "tracks/model_tracks (1) (1).geojson"
)

if not VOLUME_ROOT:
    st.error(
        "VOLUME_PATH is not set.\n\n"
        "Make sure:\n"
        "1. The app has a UC volume resource (inv_weather_dev.forecasts.tropical_bi) "
        "   with resource key `volume` in Configure → App resources.\n"
        "2. app.yaml defines env:\n"
        "   - name: VOLUME_PATH\n"
        "     valueFrom: volume"
    )
    st.stop()


@st.cache_data(show_spinner=True)
def list_geojson_files(root: str):
    """Return relative paths of all .geojson files under the volume."""
    matches = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.lower().endswith(".geojson"):
                full = os.path.join(dirpath, name)
                rel = os.path.relpath(full, root)
                matches.append(rel)
    return sorted(matches)


@st.cache_data(show_spinner=True)
def load_geojson(path: str):
    with open(path, "r") as f:
        return json.load(f)


def compute_view_state(geojson: dict) -> pdk.ViewState:
    """Compute a simple center for the geometry."""
    lats, lons = [], []

    def walk_coords(coords):
        if isinstance(coords[0], (float, int)):
            lon, lat = coords[:2]
            lons.append(lon)
            lats.append(lat)
        else:
            for c in coords:
                walk_coords(c)

    for feature in geojson.get("features", []):
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


st.markdown(
    f"**Volume root:** `{VOLUME_ROOT}`  \n"
    "This app reads GeoJSON files from that Unity Catalog volume and plots them."
)

# --- Choose GeoJSON file inside the volume ---

with st.expander("Choose GeoJSON file", expanded=True):
    files = list_geojson_files(VOLUME_ROOT)

    if files:
        # Default to the env-specified file if present
        default_index = files.index(DEFAULT_REL_PATH) if DEFAULT_REL_PATH in files else 0
        rel_path = st.selectbox(
            "GeoJSON file in the volume",
            options=files,
            index=default_index,
        )
    else:
        st.warning(
            "No `.geojson` files found in the volume. "
            "Upload one to the volume and redeploy/refresh."
        )
        rel_path = st.text_input(
            "Relative path to GeoJSON file", value=DEFAULT_REL_PATH
        )

GEOJSON_PATH = os.path.join(VOLUME_ROOT, rel_path)

st.caption(f"Full path: `{GEOJSON_PATH}`")

# --- Load and display the GeoJSON ---

try:
    geojson = load_geojson(GEOJSON_PATH)
except FileNotFoundError:
    st.error(f"GeoJSON file not found at {GEOJSON_PATH}")
    st.stop()
except Exception as e:
    st.error(f"Error loading GeoJSON: {e}")
    st.stop()

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
    tooltip={"text": "{name}"},  # change 'name' to a property in your GeoJSON
)

st.pydeck_chart(deck)

st.subheader("Raw GeoJSON (preview)")
st.json(geojson, expanded=False)


