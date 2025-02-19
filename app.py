from flask import Flask, render_template, request
import pandas as pd
import folium
import os
from io import BytesIO

app = Flask(__name__)

@app.route("/mapa")
def mostrar_mapa():
    return render_template("mapa.html")

def extract_lat_lon(gps_column):
    latitudes, longitudes = [], []
    for value in gps_column:
        try:
            lat, lon = map(float, str(value).split())
            latitudes.append(lat)
            longitudes.append(lon)
        except:
            latitudes.append(None)
            longitudes.append(None)
    return latitudes, longitudes

def generar_mapa(data):
    df = pd.read_excel(BytesIO(data))  # Leer el archivo directamente desde memoria

    # Procesar coordenadas
    df["Latitud Cliente"], df["Longitud Cliente"] = extract_lat_lon(df["GPS cliente"])
    df["Latitud Pedido"], df["Longitud Pedido"] = extract_lat_lon(df["GPS pedido"])
    df_valid = df.dropna(subset=["Latitud Cliente", "Longitud Cliente", "Latitud Pedido", "Longitud Pedido"])

    # Crear el mapa
    map_center = [df_valid["Latitud Cliente"].mean(), df_valid["Longitud Cliente"].mean()]
    mapa = folium.Map(location=map_center, zoom_start=12, tiles="CartoDB positron")

    for _, row in df_valid.iterrows():
        folium.Marker(
            location=[row["Latitud Cliente"], row["Longitud Cliente"]],
            popup=f"Cliente: {row['NombreClienteCorto']}",
            tooltip=f"Cliente: {row['NombreClienteCorto']}",
            icon=folium.Icon(color="green", icon="home")
        ).add_to(mapa)

        folium.Marker(
            location=[row["Latitud Pedido"], row["Longitud Pedido"]],
            popup=f"Pedido para {row['NombreClienteCorto']}",
            tooltip="Pedido",
            icon=folium.Icon(color="red", icon="shopping-cart")
        ).add_to(mapa)

        folium.PolyLine(
            locations=[
                (row["Latitud Cliente"], row["Longitud Cliente"]),
                (row["Latitud Pedido"], row["Longitud Pedido"])
            ],
            color="blue",
            weight=2.5,
            opacity=0.7
        ).add_to(mapa)

    # Guardar el mapa en memoria
    mapa_path = os.path.join("templates", "mapa.html")
    mapa.save(mapa_path)
    return "mapa.html"

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return "No file part"
    
    file = request.files["file"]
    if file.filename == "":
        return "No selected file"
    
    # Leer el archivo en memoria
    excel_data = file.read()

    # Generar el mapa desde el archivo cargado
    mapa_file = generar_mapa(excel_data)
    return render_template("mapa.html", mapa_file=mapa_file)

if __name__ == "__main__":
    app.run(debug=True)
