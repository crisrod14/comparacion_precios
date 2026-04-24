# Publicar la app en Streamlit (compartir con otros)

Yo no puedo iniciar sesión en tu cuenta; tú lo haces en **~2 minutos**. El enlace público será tipo  
`https://TU-NOMBRE-DE-APP.streamlit.app` — cualquiera con el link puede abrirlo (sube su propio Excel).

## Antes: código en GitHub

1. Repo **público** (más simple) o privado con acceso dado a Streamlit (abajo).
2. Asegúrate de tener en el repo:
   - `streamlit_app.py`
   - `config/config.yaml`
   - `requirements.txt` (este proyecto ya está listo para la nube)
   - carpeta `src/` con el código

## Pasos en Streamlit Community Cloud

1. Entra en **[https://share.streamlit.io](https://share.streamlit.io)** e inicia sesión con **GitHub**.

2. **Create app** (o **New app**).

3. Completa:
   - **Repository**: elige `crisrodena/revision-precios-wom` (o el nombre de tu repo).
   - **Branch**: `main` (o `master`).
   - **Main file path**: `streamlit_app.py`.

4. **Advanced settings** (opcional):
   - **Python version**: 3.11 (recomendado).
   - **Requirements file**: deja **vacío** si usas el `requirements.txt` de la raíz (ya preparado para Streamlit).  
     Si prefieres el otro archivo: `requirements-streamlit.txt`.

5. **Deploy**. Espera el build (1–3 min).

6. **Compartir**: copia la URL que te muestra (ej. `https://revision-precios-wom.streamlit.app`) y pásala a quien quieras.

## Si el repo es privado y no aparece

1. GitHub → **Settings** → **Applications** → **Authorized OAuth Apps** → **Streamlit** → **Configure**.
2. En **Repository access**, elige **Only select repositories** y marca tu repo.
3. Guarda y vuelve a crear la app en Streamlit.

## Qué verán los demás

- La misma pantalla que en local: suben **su** Excel y ejecutan la comparación.
- Los datos del Excel **no** se guardan en el servidor de Streamlit.
- La lista de SKUs sale de `config/config.yaml` del repo; si quieres cambiarla, edita el YAML, haz **commit** y **push** — Streamlit redeploya solo o al pulsar “Reboot”.

## Límite del plan gratuito

- La app puede **dormir** si nadie la usa un rato; el primer acceso tarda un poco en despertar.
- Si necesitas siempre encendida, hay planes de pago en Streamlit.

## Desarrollo local (Flask + Playwright)

```bash
pip install -r requirements-full.txt
```

## Alternativa sin Streamlit Cloud

Ejecutar en tu PC y compartir red (menos ideal): `streamlit run streamlit_app.py` y exponer la red local; para compartir con mucha gente, mejor Cloud como arriba.
