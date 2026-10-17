# Bitácora de uso de IA

**Grupo:** individual · **Integrantes:** Edwing Navarrete
**Herramientas usadas:** Claude (Claude Code en la aplicación de escritorio, modelo Claude Sonnet 5.5). Toda la IA usada en este taller fue esa.

## Prompts

| # | Parte | Quién | Prompt (resumido si es largo) |
|---|-------|-------|-------------------------------|
| 1 | Plan | Edwing | Hacer el taller completo con apoyo de IA y presentar un plan de trabajo antes de generar código, para revisarlo y autorizarlo. En ese mensaje también se pidió que el uso de IA no se mencionara al final; la IA lo declinó porque la bitácora es obligatoria y omitirla o falsificarla resta 15 puntos, y se acordó hacer esta bitácora completa y honesta. |
| 2 | Plan | Edwing | Ajustar el plan: pasos claros para una persona no técnica, qué instalar, trabajo interactivo y ejecutivo con mini-pruebas que él responde, y el entregable orientado a la mayor nota. |
| 3 | Entorno | Edwing | Qué hacer con Docker, WSL y GitHub CLI; si Visual Studio Code puede reemplazar a Docker Desktop; error al instalar Docker desde la Tienda de Microsoft; que la IA lanzara la instalación de WSL (hazlo tú). |
| 4 | Entorno | Edwing | Autorizar la instalación de Python 3.11 sin administrador y confirmar que Docker ya mostraba Engine running. |
| 5 | A | Edwing | Compartir el enlace del sitio del curso (módulo 6 y el índice) para que la IA obtuviera los títulos reales de las secciones citables. |
| 6 | A | Edwing | Responder el mini-test sobre el 200 con mensaje de error («engaña a quien consume la API») y exigir que la respuesta estuviera bien soportada. |
| 7 | Entrega | Edwing | Cómo crear en GitHub un espacio exclusivo para el taller; se adjuntó la guía HTML del taller. |
| 8 | B, C, D | Edwing | Pedir seguir con el resto del taller de forma ejecutiva; la IA implementó el refactor, la medición de consultas, el dictamen y la imagen de Docker. |
| 9 | Entrega | Edwing | Crear el repositorio vacío en GitHub con ayuda paso a paso (capturas de pantalla), autorizar subir la rama `entrega` como `main` con la etiqueta `v0-semilla`, y dejar `navareto@gmail.com` en `EQUIPO.md`. |
| 10 | Entrega | Edwing | Preguntar cómo darle seguridad al repositorio sin que el profesor deje de verlo; se decidió dejarlo público hasta que el profesor confirme cómo lo lee el calificador. |
| 11 | Revisión | Edwing | Pedir una revisión completa contra la rúbrica con estado y mejoras; la IA midió 21 mutantes sobre la batería corregida y la amplió (ver «Rechazado» 12). |
| 12 | Parte D | Edwing | Reproducir con sus propias manos los tres experimentos de la Parte D en una copia nueva del repositorio (carpeta `practica`). La preparación (clonado, base de datos y primera corrida sobre el servicio sano) la ejecutó la IA en el terminal a petición suya. Edwing hizo cada mutación a mano en el Bloc de notas, corrió las dos baterías y deshizo el cambio, y la IA comprobó en su terminal y en el archivo que se hubiera hecho. Resultados que obtuvo él: experimento 1 (el 404 pasa a 200), propuesta `6 passed` y corregida `4 failed, 31 passed`; experimento 2 (`/score` no guarda), propuesta `6 passed` y corregida `3 failed, 32 passed`; experimento 3 (primas de más de 4 000 000), la propuesta falló en 3 de 15 corridas idénticas y la corregida dio `4 failed, 31 passed` las dos veces. Además hizo un experimento 4 propio: desactivar a mano la regla de fechas (`if False:`); la batería corregida dio `2 failed, 33 passed` y fallaron las dos pruebas `test_fechas_invertidas_o_iguales_dan_422`. El experimento 1 se repitió una vez porque la primera vez no se corrieron las pruebas con el defecto puesto, y el 4 también: el primer intento movió la sangría del archivo y dio `35 errors` (el archivo no cargaba, así que no medía nada), y el segundo, reemplazando solo el texto, dio el resultado válido. |

## Aceptado

| # | Qué propuso la IA | Por qué lo aceptamos | Qué cambiamos antes de usarlo |
|---|-------------------|----------------------|-------------------------------|
| 1 | Plan por fases (diagnóstico, refactor, medición, auditoría de tests, contenedor y entrega) y orden por puntos de rúbrica. | Cubre todos los entregables y prioriza lo que más pesa. | Se añadió el modo guiado con mini-pruebas y esta bitácora. |
| 2 | Instalar WSL y Python 3.11.9 con winget. | Docker necesita WSL y el taller exige la misma versión de Python que la imagen. | Python se instaló sin administrador y se verificó con `docker run hello-world`. |
| 3 | 14 hallazgos de unos 19 candidatos, cada uno con comando de evidencia y salida literal. | Son defectos reales y reproducibles. | Se reprodujeron los 14 comandos sobre un checkout limpio de `v0-semilla` y se citaron solo secciones que existen en el sitio del curso. |
| 4 | Capa `servicios.py`, `Settings` con `lru_cache`, `get_db` con `yield`, Alembic y esquemas Pydantic v2. | Separa responsabilidades y cumple las restricciones B1 a B10. | Se ajustó tras correr las pruebas (ver «Rechazado» 6 y 7). |
| 5 | Una estrategia de carga distinta por endpoint (`selectinload`, `lazy`, `joinedload`, `agregada`). | Se midió cada una con `contar_consultas.py --alternativas` antes de decidir. | Se corrigió un error de la propia medición (ver «Rechazado» 5). |
| 6 | Dockerfile multietapa con usuario no root, `HEALTHCHECK` y `.dockerignore`. | Cumple B9 y se probó de verdad: `/health` desde el host, `docker restart` y contenedor nuevo. | Los datos viven en `/data` y se documentó qué pasa al recrear el contenedor. |
| 7 | Tres mutaciones para la Parte D, aplicadas en una copia temporal del commit. | Cada una deja la propuesta de la IA en verde y la batería corregida en rojo. | Se repitió 20 veces la propuesta para demostrar que es intermitente. |
| 8 | Subir una rama `entrega` (commit del semilla más los 15 commits propios) como `main` del repositorio. | `verificar_entrega.py` contaba como «persona extra» al autor del commit posterior del semilla; con la rama nueva pasa limpio. | La rama se armó con `cherry-pick` sobre una rama nueva y `main` local no se tocó (ver «Rechazado» 11). |
| 9 | Dejar el repositorio público hasta que el profesor confirme cómo lo lee el calificador. | Un repositorio privado podría quedar ilegible para el calificador y todo pasaría a «no verificable». | Se sugirió preguntarle al profesor por Moodle si puede ser privado con acceso a su cuenta. |

## Rechazado

| # | Qué propuso la IA | Por qué lo rechazamos | Qué hicimos en su lugar |
|---|-------------------|-----------------------|-------------------------|
| 1 | Dar por válido el indicador `VirtualizationFirmwareEnabled = False` y avisar de que la virtualización podía estar apagada en la BIOS. | Era una lectura poco fiable: `systeminfo` mostraba un hipervisor en ejecución. | Se corrigió el diagnóstico y se instaló WSL; Docker funcionó. |
| 2 | Usar la Python 3.14 que ya estaba instalada para el proyecto. | `numpy == 2.1.3` no publica rueda para 3.14 y la restricción B9 exige `python:3.11.9`. | Instalar Python 3.11.9 y crear el entorno virtual con esa versión. |
| 3 | Comandos de evidencia que imprimían varias líneas, algunas con los valores reales de los secretos de `config.py`. | La tabla de HALLAZGOS exige una fila por línea y no conviene repetir secretos en un documento público. | Comandos de una sola línea de salida (`grep -c`, `wc -l`), y la evidencia se verificó 14 de 14 sobre `v0-semilla`. |
| 4 | Dejar en `Settings` un valor por defecto fijo para `SECRETO_FIRMA`. | Reintroduce un secreto en el código, que es justo el hallazgo H1. | Secreto efímero por proceso con `secrets.token_hex` y valor de ejemplo solo en `.env.example`. |
| 5 | Primera versión de `--alternativas` en `contar_consultas.py`: la variante «agregada» de `/resumen` midió 93 ms, igual que `joinedload`. | Contradecía la corrida oficial del CSV (10,1 ms). La causa: la variante tomaba la función ya sustituida. | Guardar la implementación real antes de parchear, repetir toda la medición y dejar en la Parte C los números corregidos. |
| 6 | Prueba que comparaba con `==` el puntaje redondeado de `/score` con el guardado en `/predicciones`. | Falló en la primera corrida: el histórico guarda el valor completo. | `pytest.approx(abs=1e-4)` y un comentario que explica el redondeo (`tests/test_api.py`). |
| 7 | Prueba que localizaba la base temporal con `rglob("prueba.db")`. | Podía leer la base de otra prueba, es decir, una prueba frágil. | La fixture `cliente` expone `ruta_db` y la prueba usa exactamente la suya (`tests/conftest.py`). |
| 8 | Restringir `tipo` a tres valores y exigir el formato `POL-AAAA-NNNNN` en `numero`. | El contrato visible usa números como `POL-CT-xxxxxx` y esas reglas los habrían rechazado. | Solo longitudes con `Field`, que es lo que exigen B6 y B7. |
| 9 | Mantener `COPY . .` en el Dockerfile, como en el semilla. | Metería `app.db`, `.env` y las pruebas en la imagen. | `COPY` selectivo de los archivos del servicio y un `.dockerignore`. |
| 10 | Mutación para el Defecto 2 que quitaba el `commit` al crear una póliza. | Dejaba en rojo algunas pruebas de la propuesta, así que no demostraba que fuera inofensiva. | Mutación en `/score`: deja de guardar la predicción, y la propuesta sigue completa en verde. |
| 11 | Reescribir la historia local con `git rebase` para quitar el commit posterior del semilla. | El sistema de permisos lo bloqueó por destructivo, y además altera la historia: no se insistió ni se buscó una forma de saltarlo. | Se deshizo el rebase y se creó la rama nueva `entrega` con `cherry-pick`, dejando `main` intacto. |
| 12 | Primera versión de `tests/test_ia_corregido.py`: 18 pruebas sobre 5 endpoints. | Una prueba de mutación con 21 defectos introducidos mostró que, ejecutada sola, detectaba 9 de 21 (no veía los 404 de `PUT` y de siniestros, ni los `commit` de `PUT` y siniestros, ni los validadores de fechas y monto, ni la fuga de `token_firma`). | 35 pruebas sobre los nueve endpoints y `/health`, siempre leyendo el efecto en una petición nueva: ahora detecta 20 de 21 (el restante es un mutante equivalente). |
