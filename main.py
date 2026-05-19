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
    allow_origins=["*"],  # In produzione sostituisci "*" con l'URL del tuo sito WordPress
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/convert-json-to-gpx/")
async def convert_json_to_gpx(file: UploadFile = File(...)):
    # 1. Verifica il tipo di file
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Il file deve essere un JSON.")

    try:
        # 2. Leggi il contenuto del file caricato
        contents = await file.read()
        
        # Verifica la dimensione direttamente dai byte per massima compatibilità con Python 3.12
        if len(contents) > 1 * 1024 * 1024:  # 1 MB
            raise HTTPException(status_code=400, detail="Il file è troppo grande.")
            
        data = json.loads(contents)
        
        # Supporto sia per array diretti che per strutture ESRI standard avvolte in "features"
        if isinstance(data, dict) and "features" in data:
            data = data["features"]
        elif isinstance(data, dict):
            data = [data]
        
        # 3. Estrai le geometrie (CORRETTA INDENTAZIONE)
        features = []
        for item in data:
            if "geometry" in item and "paths" in item["geometry"] and item["geometry"]["paths"]:
                # Estrae le coordinate del primo tracciato
                coords = item["geometry"]["paths"][0]
                
                # Una linea ha bisogno di almeno 2 punti (coppie di coordinate)
                if len(coords) < 2:
                    continue
                    
                line = LineString(coords)

                # Recupera gli attributi
                attributes = item.get("attributes", {})

                # Il driver GPX richiede il campo 'name' per nominare la traccia
                # Sostituisci 'Nome_Attributo_JSON' con la chiave reale del tuo JSON
                track_name = attributes.get("Nome_Attributo_JSON", "Tracciato")

                # ORA È DENTRO L'IF: Viene eseguito solo se la geometria esiste ed è valida
                features.append({"geometry": line, "name": track_name})
        
        if not features:
            raise HTTPException(status_code=422, detail="Nessuna geometria valida trovata nel JSON.")
        
        # 4. Crea GeoDataFrame e riproietta
        gdf = gpd.GeoDataFrame(features, crs="EPSG:3857")
        gdf_gpx = gdf.to_crs("EPSG:4326")
        
        # 5. Salva il GPX in un buffer di memoria
        gpx_buffer = io.BytesIO()
        gdf_gpx.to_file(
            gpx_buffer,
            driver="GPX",
            layer="tracks",
            dataset_options={"GPX_USE_EXTENSIONS": "YES"}
        )
        gpx_buffer.seek(0) # Riposiziona il cursore all'inizio del file in memoria
        
        # 6. Ritorna il file come download stream
        return StreamingResponse(
            gpx_buffer,
            media_type="application/gpx+xml",
            headers={"Content-Disposition": "attachment; filename=percorso_output.gpx"}
        )

    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="File ESRI JSON non valido o corrotto.")
    except Exception as e:
        # Stampa l'errore nel terminale locale per aiutarti nel debug
        print(f"Errore interno: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Errore durante la conversione: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
