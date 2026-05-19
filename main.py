import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import StreamingResponse
import geopandas as gpd
from shapely.geometry import LineString
import io
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="ESRIJSON to GPX Converter")
# Abilita CORS per permettere a WordPress di interrogare l'API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In produzione sostituisci "*" con l'URL del tuo sito WordPress (es: "https://tuosito.com")
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/convert-json-to-gpx/")
async def convert_json_to_gpx(file: UploadFile = File(...)):
    # 1. Verifica il tipo di file
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Il file deve essere un JSON.")
    if file.size > 1 * 1024 * 1024:  # 1 MB
        raise HTTPException(status_code=400, detail="Il file è troppo grande.")

    try:
        # 2. Leggi il contenuto del file caricato
        contents = await file.read()
        data = json.loads(contents)
        
        # 3. Estrai le geometrie (stessa logica del tuo script)
        features = []
        for item in data:
            if "geometry" in item and "paths" in item["geometry"]:
                # Estrae le coordinate del primo tracciato
                coords = item["geometry"]["paths"][0]
                line = LineString(coords)

                # Recupera gli attributi
                attributes = item.get("attributes", {})

        # Il driver GPX richiede il campo 'name' per nominare la traccia
        # Sostituisci 'Nome_Attributo_JSON' con la chiave reale del tuo JSON
                track_name = attributes.get("Nome_Attributo_JSON", "Tracciato")

                features.append({"geometry": line, "name": track_name})
            # if "geometry" in item and "paths" in item["geometry"]:
            #     coords = item["geometry"]["paths"]
            #     line = LineString(coords)
            #     attributes = item.get("attributes", {})
                
            #     # Mappa il nome (usa una chiave di fallback se non esiste)
            #     track_name = attributes.get("Nome_Attributo_JSON", "Tracciato")
            #     features.append({"geometry": line, "name": track_name})
        
        if not features:
            raise HTTPException(status_code=422, detail="Nessuna geometria valida trovata nel JSON.")
        
        # 4. Crea GeoDataFrame e riproietta
        gdf = gpd.GeoDataFrame(features, crs="EPSG:3857")
        gdf_gpx = gdf.to_crs("EPSG:4326")
        
        # 5. Salva il GPX in un buffer di memoria (senza scrivere sul disco del server)
        gpx_buffer = io.BytesIO()
        gdf_gpx.to_file(
            gpx_buffer,
            driver="GPX",
            layer="tracks",
            dataset_options=["GPX_USE_EXTENSIONS=YES"]
        )
        gpx_buffer.seek(0) # Riposiziona il cursore all'inizio del file in memoria
        
        # 6. Ritorna il file come download stream
        return StreamingResponse(
            gpx_buffer,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": f"attachment; filename=percorso_output.gpx"}
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="File ESRI JSON non valido o corrotto.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore durante la conversione: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
