from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.responses import RedirectResponse
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


import pandas as pd
from datetime import datetime, timedelta
import folium
import simplekml
import geopandas as gpd
from folium.plugins import PolyLineTextPath
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd

scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]

import json
import os

creds_dict = json.loads(os.environ["GOOGLE_CREDS"])
creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)

client = gspread.authorize(creds)

sheet = client.open("Elephant_Data").sheet1

def dms_to_decimal(deg, minutes, seconds):
    return float(deg) + float(minutes)/60 + float(seconds)/3600

app = FastAPI()
templates = Jinja2Templates(directory="./templates")
app.mount("/static", StaticFiles(directory="static"), name="static")




@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
@app.get("/viewer", response_class=HTMLResponse)
def viewer(request: Request):
    return templates.TemplateResponse("viewer.html", {"request": request})

@app.post("/add")
def add_data(
    lat_deg: float = Form(...),
    lat_min: float = Form(...),
    lat_sec: float = Form(...),

    lon_deg: float = Form(...),
    lon_min: float = Form(...),
    lon_sec: float = Form(...),

    observation_time: str = Form(...),
    sign_type: str = Form(...),
    sign_age_hours: int = Form(...)
):
    latitude = dms_to_decimal(lat_deg, lat_min, lat_sec)
    longitude = dms_to_decimal(lon_deg, lon_min, lon_sec)

    obs_time = datetime.fromisoformat(observation_time)
    presence_time = obs_time - timedelta(hours=sign_age_hours)

    print("ADDING TO SHEET:", latitude, longitude)

    sheet.append_row([
        latitude,
        longitude,
        observation_time,
        sign_type,
        sign_age_hours,
        str(presence_time)
    ])

    return {"status": "added"}


@app.get("/map")
def generate_map():


    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    if df.empty:
        return HTMLResponse("<h2>No elephant movement data available</h2>")
    coords = list(zip(df.latitude, df.longitude))

    m = folium.Map(location=coords[0], zoom_start=12)

    gdf = gpd.read_file("static/COMPT_S_BGT_CORRECT.kml", layer="COMPT_S_BGT_CORRECT")

    folium.GeoJson(
        gdf,
        style_function=lambda x: {
            "fillColor": "transparent",
            "color": "green",
            "weight": 2
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["Name"],
            aliases=["Compartment:"]
        )
    ).add_to(m)
    
    for i, row in enumerate(df.itertuples()):

        if i == len(df) - 1:
            icon_color = "red"
            size = 36
        else:
            icon_color = "blue"
            size = 24
        folium.Marker(
            location=[row.latitude, row.longitude],
            popup=f"""
            Observation #{i+1}<br>
            Presence: {row.presence_time}
            """,
            icon=folium.DivIcon(
                html=f"""
                <div style="
                    font-size:14px;
                    font-weight:bold;
                    color:white;
                    background-color:{icon_color};
                    border-radius:50%;
                    width:{size}px;
                    height:{size}px;
                    text-align:center;
                    line-height:{size}px;
                    border:2px solid black;">
                {i+1}
                </div>
                """
            )
        ).add_to(m)        
    line = folium.PolyLine(coords, color="red", weight=3)
    line.add_to(m)
    PolyLineTextPath(
        line,
        "➤",
        repeat=True,
        offset=7,
        attributes={"font-size": "16", "fill": "red"}
    ).add_to(m)

    return HTMLResponse(m._repr_html_())
        def delete_entry(entry_id: int):
        cursor.execute("DELETE FROM elephant_data WHERE id=?", (entry_id,))
        conn.commit()
        return RedirectResponse(url="/map", status_code=303)
    @app.get("/data")
    def view_data():
        df = pd.read_sql_query("SELECT * FROM elephant_data ORDER BY datetime(presence_time)", conn)
        return HTMLResponse(df.to_html())

@app.get("/export_kml")
def export_kml():

    data = sheet.get_all_records()
    df = pd.DataFrame(data)
    kml = simplekml.Kml()

    coords = []

    for i, row in df.iterrows():

        pnt = kml.newpoint(
            name=f"Point {i+1}",
            coords=[(row.longitude, row.latitude)]
        )

        pnt.description = f"Presence time: {row.presence_time}"

        coords.append((row.longitude, row.latitude))

    if len(coords) > 1:
        line = kml.newlinestring(
            name="Elephant Movement Route",
            coords=coords
        )
        line.style.linestyle.width = 4
        line.style.linestyle.color = simplekml.Color.red
    kml_path = "static/elephant_route.kml"
    kml.save(kml_path)

    return FileResponse(
        kml_path,
        media_type="application/vnd.google-earth.kml+xml",
        filename="elephant_route.kml"
    )
