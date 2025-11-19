import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from fastapi.middleware.cors import CORSMiddleware 
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from contextlib import asynccontextmanager
import datetime


# Guardo los datos en este arreglo para no estar haciendo web scraping cada rato
CACHE_PILOTOS = []

# BaseModel de fast api
class Piloto(BaseModel):
    posicion: int
    nombre: str
    team: str
    puntos: str 

class Clasificacion(BaseModel):
    clasificacion: List[Piloto]

class Torneo(BaseModel):
    id: int
    titulo: str
    imgLink: str
    descripcion: str
    fase: str
    estado: str


# web scraping
def extraer_clasificacion_pilotos() -> List[Piloto]:

    print(f"Ejecutando Scraping a las {datetime.datetime.now()}")
    URL = "https://www.formula1.com/en/results/2025/drivers" 
    # URL = "https://www.formula1.com/en/results/2024/drivers"
    
    TARGET_CLASS = 'Table-module_table__cKsW2'
    
    try:
        response = requests.get(URL)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        table = soup.find('table', class_=TARGET_CLASS)
        
        if not table:
            print("Error: Tabla no encontrada durante el scraping.")
            return []

        pilotos_data = []
        tbody = table.find('tbody')
        filas = tbody.find_all('tr') if tbody else table.find_all('tr')[1:]
        
        for fila in filas:
            celdas = fila.find_all(['th', 'td'])
            if len(celdas) < 5: continue 
            
            posicion_texto = celdas[0].get_text(strip=True)
            nombre_completo = celdas[1].get_text(strip=True)
            team_texto = celdas[3].get_text(strip=True)
            puntos_texto = celdas[4].get_text(strip=True)
            
            if posicion_texto and nombre_completo:
                try:
                    pilotos_data.append(Piloto(
                        posicion=int(posicion_texto),
                        nombre=nombre_completo,
                        team=team_texto,
                        puntos=puntos_texto
                    ))
                except ValueError:
                    continue 

        print(f"Datos actualizados: {len(pilotos_data)} pilotos encontrados.\n")
        return pilotos_data

    except Exception as e:
        print(f"Error en el scraping: {e}")
        return []


def actualizar_cache_pilotos():
    """
    Como no me interesa que haga web scraping todos los dias hice esta funcion
    que solo hace los Sabados y domingos a las 8hs y 20hs
    """
    global CACHE_PILOTOS
    nuevos_datos = extraer_clasificacion_pilotos()
    
    # Solo actualizo el arreglo si hay cambios
    if nuevos_datos:
        CACHE_PILOTOS = nuevos_datos



@asynccontextmanager
async def lifespan(app: FastAPI):
    
    scheduler = AsyncIOScheduler()
    trigger = CronTrigger(day_of_week="sat,sun", hour="8,20", minute="0") 
    
    scheduler.add_job(actualizar_cache_pilotos, trigger)
    scheduler.start()
    
    print("\n","Iniciando servidor".center(50,"-"),"\n")
    actualizar_cache_pilotos()
    
    yield 
    
    
    # scheduler.shutdown()
    #print("Apagando servidor.")




app = FastAPI(
    title="API Prode",
    lifespan=lifespan 
)


# Configuracion de middleware para saber quienes se pueden conectar a la api
origins = ["*"] 
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Datos de los torneos(Se borran cuando tenga la BD)
torneos_db = [
    {"id": 1, "titulo": "Copa del mundo 2026", "imgLink": "Mundial.jpeg", "descripcion": "Inicia Junio 2026", "fase": "Previa", "estado": "Proximo"},
    {"id": 2, "titulo": "F1 2026", "imgLink": "f1.webp", "descripcion": "Inicia Junio 2025", "fase": "Ultimas carreras", "estado": "Activo"},
    {"id": 3, "titulo": "Moto Gp 2025", "imgLink": "motoGp.jpg", "descripcion": "Finalizon en noviembre 2025", "fase": "Fases de grupos", "estado": "Activo"},
    
]



# Endpoints
@app.get("/pilotos", response_model=Clasificacion)
async def get_clasificacion_pilotos():
    """
    Devuelve los datos desde la MEMORIA (caché).
    ¡Ya no hace scraping en este momento! Es instantáneo.
    """
    global CACHE_PILOTOS
    
    if not CACHE_PILOTOS:
        # Si por alguna razón está vacío trata una vez más
        actualizar_cache_pilotos()
        if not CACHE_PILOTOS: # Si no mandamos el error
            raise HTTPException(status_code=404, detail="Datos no disponibles.")

    return {"clasificacion": CACHE_PILOTOS}

# enpoint de los torneos disponibles
@app.get("/torneos")
async def get_torneos():
    return torneos_db