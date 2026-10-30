"""Acta Clara API — prototipo de hackathon.

Expone la misma lógica de validación del demo para que otro sistema
(un canal de WhatsApp, el portal de un Registro Civil, un CRM de atención)
pueda revisar documentos y abrir una solicitud de corrección.

Local:
    pip install -r requirements.txt
    ACTA_CLARA_API_KEY=clave-local uvicorn api.index:app --reload
Vercel: ver README.md. Documentación interactiva en /docs
"""
import unicodedata
import os
import secrets
import uuid
from datetime import date
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Security
from fastapi.responses import HTMLResponse
from fastapi.security import APIKeyHeader
from pathlib import Path
from pydantic import BaseModel

app = FastAPI(title="Acta Clara API", version="0.1.0",
              description="Detecta errores entre acta de nacimiento, INE y CURP.")

FUENTE = {"nombre": "Plataforma Nacional del Registro Civil",
          "url": "https://www.miregistrocivil.gob.mx/",
          "consultado": "2026-10-30"}

ENT = {"AS": "Aguascalientes", "BC": "Baja California", "BS": "Baja California Sur",
       "CC": "Campeche", "CL": "Coahuila", "CM": "Colima", "CS": "Chiapas",
       "CH": "Chihuahua", "DF": "Ciudad de México", "DG": "Durango",
       "GT": "Guanajuato", "GR": "Guerrero", "HG": "Hidalgo", "JC": "Jalisco",
       "MC": "Estado de México", "MN": "Michoacán", "MS": "Morelos", "NT": "Nayarit",
       "NL": "Nuevo León", "OC": "Oaxaca", "PL": "Puebla", "QT": "Querétaro",
       "QR": "Quintana Roo", "SP": "San Luis Potosí", "SL": "Sinaloa", "SR": "Sonora",
       "TC": "Tabasco", "TS": "Tamaulipas", "TL": "Tlaxcala", "VZ": "Veracruz",
       "YN": "Yucatán", "ZS": "Zacatecas", "NE": "Nacido en el extranjero"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


class Acta(BaseModel):
    nombre: str
    primer_apellido: str
    segundo_apellido: str
    fecha_nacimiento: date
    sexo: str  # "Mujer" | "Hombre"
    entidad: str


class Credencial(BaseModel):
    nombre: str
    primer_apellido: str
    segundo_apellido: str
    curp: str


class ActaHijo(BaseModel):
    nombre_completo: str
    nombre_madre: Optional[str] = None
    nombre_padre: Optional[str] = None


class Revision(BaseModel):
    acta: Acta
    credencial: Credencial
    acta_hijo: Optional[ActaHijo] = None


class Solicitud(BaseModel):
    revision: Revision
    telefono_whatsapp: Optional[str] = None


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def requiere_api_key(key: Optional[str] = Security(api_key_header)):
    esperada = os.environ.get("ACTA_CLARA_API_KEY")
    if not esperada:
        raise HTTPException(503, "Falta configurar ACTA_CLARA_API_KEY en el servidor.")
    if not key or not secrets.compare_digest(key, esperada):
        raise HTTPException(401, "API key inválida o ausente (encabezado X-API-Key).")


SOLICITUDES: dict[str, dict] = {}  # en memoria: en Vercel no persiste entre llamadas; usar una base de datos


def norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return " ".join(s.upper().split())


def curp_valida(c: str) -> bool:
    dic = "0123456789ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"
    if len(c) != 18 or any(ch not in dic for ch in c):
        return False
    s = sum(dic.index(c[i]) * (18 - i) for i in range(17))
    return (10 - s % 10) % 10 == int(c[17]) if c[17].isdigit() else False


def fecha_txt(d: int, m: int, y: int) -> str:
    return f"{d} de {MESES[m - 1]} de {y}"


def revisar(r: Revision) -> list[dict]:
    a, i, c = r.acta, r.credencial, r.credencial.curp.upper()
    errores = []
    if not curp_valida(c):
        errores.append({"campo": "curp", "mensaje": "La CURP no pasa la verificación."})
    if norm(a.nombre) != norm(i.nombre):
        errores.append({"campo": "nombre",
                        "mensaje": f"En el acta dice “{a.nombre}” y en la credencial “{i.nombre}”."})
    if (norm(a.primer_apellido), norm(a.segundo_apellido)) != (norm(i.primer_apellido), norm(i.segundo_apellido)):
        errores.append({"campo": "apellidos", "mensaje": "Los apellidos no coinciden."})
    f = a.fecha_nacimiento
    try:
        cy, cm, cd = int(c[4:6]), int(c[6:8]), int(c[8:10])
        if (cy, cm, cd) != (f.year % 100, f.month, f.day):
            invertida = (cy, cm, cd) == (f.year % 100, f.day, f.month)
            msg = (f"El acta dice {fecha_txt(f.day, f.month, f.year)} y la CURP "
                   f"{fecha_txt(cd, cm, 1900 + cy)}.")
            if invertida:
                msg += " El día y el mes parecen invertidos."
            errores.append({"campo": "fecha_nacimiento", "mensaje": msg, "dia_mes_invertidos": invertida})
        sexo = {"H": "Hombre", "M": "Mujer"}.get(c[10], "No binario")
        if norm(sexo) != norm(a.sexo):
            errores.append({"campo": "sexo", "mensaje": f"Acta: {a.sexo}. CURP: {sexo}."})
        ent = ENT.get(c[11:13], "desconocido")
        if norm(ent) != norm(a.entidad):
            errores.append({"campo": "entidad", "mensaje": f"Acta: {a.entidad}. CURP: {ent}."})
    except (ValueError, IndexError):
        errores.append({"campo": "curp", "mensaje": "No se pudo leer la CURP."})
    if r.acta_hijo:
        titular = norm(f"{a.nombre} {a.primer_apellido} {a.segundo_apellido}")
        for rol in ("nombre_madre", "nombre_padre"):
            valor = getattr(r.acta_hijo, rol)
            if valor and norm(valor) != titular:
                errores.append({"campo": f"acta_hijo.{rol}",
                                "mensaje": f"En el acta de {r.acta_hijo.nombre_completo} aparece como “{valor}”."})
    return errores


@app.post("/v1/revisiones", summary="Revisar acta contra credencial y CURP", dependencies=[Depends(requiere_api_key)])
def crear_revision(r: Revision):
    errores = revisar(r)
    return {"tiene_errores": bool(errores), "errores": errores, "fuente": FUENTE}


@app.post("/v1/solicitudes", status_code=201, summary="Abrir solicitud de corrección", dependencies=[Depends(requiere_api_key)])
def crear_solicitud(s: Solicitud):
    errores = revisar(s.revision)
    if not errores:
        raise HTTPException(422, "No se encontraron errores; no hay nada que corregir.")
    folio = f"RC-{date.today().year}-{uuid.uuid4().hex[:6].upper()}"
    SOLICITUDES[folio] = {"folio": folio, "estado": "preparada", "errores": errores,
                          "curp": s.revision.credencial.curp.upper(),
                          "telefono_whatsapp": s.telefono_whatsapp, "fuente": FUENTE}
    return SOLICITUDES[folio]


@app.get("/v1/solicitudes/{folio}", summary="Consultar estado de una solicitud", dependencies=[Depends(requiere_api_key)])
def ver_solicitud(folio: str):
    if folio not in SOLICITUDES:
        raise HTTPException(404, "Folio no encontrado.")
    return SOLICITUDES[folio]


DEMO = Path(__file__).resolve().parent.parent / "index.html"


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def demo():
    if not DEMO.exists():
        raise HTTPException(404, "No se encontró index.html.")
    return HTMLResponse(DEMO.read_text(encoding="utf-8"))


@app.get("/v1/salud")
def salud():
    return {"ok": True}
