# Acta Clara

Asistente tipo WhatsApp para que personas mayores detecten y corrijan errores
en su acta de nacimiento sin ir a una oficina. Proyecto del Hackathon por México
(30/10/2026).

## Problema
Un punto o una letra distinta entre el acta, la INE, la CURP o las actas de los
hijos basta para que, ante la ley, no sea la misma persona. Eso detiene
testamentos, herencias, seguros y pensiones. El trámite de corrección ya existe
en línea (miregistrocivil.gob.mx), pero exige Llave MX y navegar un portal.

## Qué contiene
- `index.html`: demo del chat con 5 casos ficticios, validación de CURP en vivo
  y voz automática (se puede apagar).
- `api/index.py`: API FastAPI con la misma lógica, para conectar otros sistemas.

## Qué es real y qué es simulado
- Real: validación de CURP (formato y dígito verificador), comparación de
  nombre, apellidos, fecha (incluye día/mes invertidos), sexo, entidad y nombre
  de la madre en el acta del hijo.
- Simulado: lectura de fotos, verificación de identidad, envío al Registro Civil
  y acta corregida. En un piloto requieren un convenio con el Registro Civil y
  la integración con Llave MX por parte de la dependencia.

## Publicar en Vercel
1. Importa este repositorio en https://vercel.com/new
2. En Environment Variables agrega `ACTA_CLARA_API_KEY` con una clave larga.
3. Deploy.
- Demo: `https://TU-PROYECTO.vercel.app/`
- API: `https://TU-PROYECTO.vercel.app/docs` (rutas /v1 piden encabezado `X-API-Key`)

## API
- `POST /v1/revisiones`: revisa acta, credencial y opcionalmente acta del hijo.
- `POST /v1/solicitudes`: abre una solicitud de corrección con folio.
- `GET /v1/solicitudes/{folio}`: estado de la solicitud.
- `GET /v1/salud`: verificación de servicio.

Limitación: las solicitudes se guardan en memoria; en Vercel no persisten entre
llamadas. Para un piloto, conectar una base de datos.

## Fuentes
- Plataforma Nacional del Registro Civil, miregistrocivil.gob.mx (consultado 30/10/2026)
- RENAPO: estructura de la CURP
- INEGI, ENCIG 2025

Todos los documentos y CURP del demo son ficticios.
