import os
import math
import pandas as pd
import folium
from flask import Flask, render_template, request, session, redirect, url_for, Response
from geopy.distance import geodesic
from io import BytesIO

app = Flask(__name__)
app.secret_key = "SUPER_SECRETO"  # Cambia esto por algo aleatorio y seguro

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

@app.route("/")
def index():
    """Página inicial: muestra el formulario para subir Excel."""
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    """Recibe el Excel, parsea y muestra lista de clientes con checkboxes."""
    if "file" not in request.files:
        return "No file part"

    file = request.files['file']
    if file.filename == "":
        return "No selected file"

    # Leer Excel en memoria
    excel_data = file.read()

    # Parsear en DataFrame
    df = pd.read_excel(BytesIO(excel_data))

    # Extraer lat/lon
    df['Latitud Cliente'], df['Longitud Cliente'] = extract_lat_lon(df['GPS cliente'])
    df['Latitud Pedido'], df['Longitud Pedido'] = extract_lat_lon(df['GPS pedido'])

    # Filtro para filas válidas
    df_valid = df.dropna(subset=['Latitud Cliente','Longitud Cliente','Latitud Pedido','Longitud Pedido'])

    # Guardar en session
    session['df_data'] = df_valid.to_dict(orient='records')

    # Máximo de 200 filas para mostrar en la tabla
    max_rows = 200
    df_display = df_valid.head(max_rows)

    # Renderiza la plantilla "seleccionar.html", pasándole df_display como "df"
    return render_template("seleccionar.html", df=df_display)

@app.route("/seleccionar", methods=["POST"])
def seleccionar():
    """Recibe los IDs de los clientes seleccionados y genera el mapa con capas individuales."""
    if 'df_data' not in session:
        return "No data in session. Please upload again."

    df_records = session['df_data']
    df_valid = pd.DataFrame(df_records)

    # Recibir lista de índices seleccionados
    seleccion_indices = request.form.getlist("selected_clients")

    # Límite de 20
    if len(seleccion_indices) > 20:
        return "Has seleccionado más de 20 clientes. Vuelve atrás e inténtalo de nuevo."

    if not seleccion_indices:
        return "No has seleccionado ningún cliente."

    # Convertir índices a int
    seleccion_indices = list(map(int, seleccion_indices))

    # Filtrar DataFrame
    df_seleccionados = df_valid.iloc[seleccion_indices]
    if df_seleccionados.empty:
        return "No has seleccionado ningún cliente válido."

    # Generar el mapa, con cada cliente en su propia capa
    mapa_html = generar_mapa_capas(df_seleccionados)
    return Response(mapa_html, content_type="text/html")

def generar_mapa_capas(df):
    """
    Genera el mapa Folium con un FeatureGroup por cliente,
    de modo que en el LayerControl cada cliente aparezca
    como una capa independiente.
    """
    if df.empty:
        return "<h3>DataFrame vacío</h3>"

    # Calcular centro
    map_center = [
        df['Latitud Cliente'].mean(),
        df['Longitud Cliente'].mean()
    ]
    mapa = folium.Map(location=map_center, zoom_start=10, tiles="CartoDB positron")

    # Diccionario para el offset de marcadores
    used_positions = {}

    def get_offset_position(lat, lon, threshold=0.00003):
        key = (round(lat, 5), round(lon, 5))
        count = used_positions.get(key, 0)
        angle = math.radians(45 * count)
        lat_off = lat + threshold * math.cos(angle)
        lon_off = lon + threshold * math.sin(angle)
        used_positions[key] = count + 1
        return lat_off, lon_off

    # Agrupamos por cliente, para que cada uno tenga su propia capa
    rango_maximo_metros = 300

    # Obtener lista de clientes únicos en df seleccionado
    clientes_unicos = df['NombreClienteCorto'].unique()

    for cliente in clientes_unicos:
        # Crear un FeatureGroup para este cliente
        fg_cliente = folium.FeatureGroup(name=str(cliente), show=True)
        fg_cliente.add_to(mapa)

        # Filtrar las filas de df que correspondan a este cliente
        df_cli = df[df['NombreClienteCorto'] == cliente]

        for _, row in df_cli.iterrows():
            nombre_cliente = row.get('NombreClienteCorto', 'SinNombre')
            codigo_cliente = row.get('CódigoCliente', '000')
            lat_cli = row['Latitud Cliente']
            lon_cli = row['Longitud Cliente']
            lat_ped = row['Latitud Pedido']
            lon_ped = row['Longitud Pedido']

            # Offset cliente
            lat_cli_off, lon_cli_off = get_offset_position(lat_cli, lon_cli)
            # Offset pedido
            lat_ped_off, lon_ped_off = get_offset_position(lat_ped, lon_ped)

            # Marcador cliente
            folium.Marker(
                location=[lat_cli_off, lon_cli_off],
                popup=(
                    f"<b>Cliente:</b> {nombre_cliente}<br>"
                    f"<b>Código:</b> {codigo_cliente}"
                ),
                icon=folium.Icon(color="green", icon="home")
            ).add_to(fg_cliente)

            # Círculo alrededor del cliente
            folium.Circle(
                location=[lat_cli_off, lon_cli_off],
                radius=rango_maximo_metros,
                color='blue',
                fill=True,
                fill_opacity=0.2,
                popup=f"Rango de {nombre_cliente}"
            ).add_to(fg_cliente)

            # Distancia real
            distancia_km = geodesic((lat_cli, lon_cli),(lat_ped, lon_ped)).kilometers
            color_icono = "blue" if distancia_km <= (rango_maximo_metros/1000) else "orange"

            # Marcador pedido
            folium.Marker(
                location=[lat_ped_off, lon_ped_off],
                popup=(f"<b>Pedido de:</b> {nombre_cliente}<br>"
                       f"<b>Distancia:</b> {distancia_km:.2f} km"),
                icon=folium.Icon(color=color_icono, icon="shopping-cart")
            ).add_to(fg_cliente)

            # Línea
            folium.PolyLine(
                locations=[(lat_cli_off, lon_cli_off),(lat_ped_off, lon_ped_off)],
                color='blue', weight=3, opacity=0.7,
                popup=f"Línea {nombre_cliente}"
            ).add_to(fg_cliente)

    # Al final, agregamos el LayerControl
    folium.LayerControl().add_to(mapa)

    return mapa._repr_html_()

if __name__ == "__main__":
    app.run(debug=True)
