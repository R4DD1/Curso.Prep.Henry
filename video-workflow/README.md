# Video Workflow · Generación IA

Mini app para generar videos con tu avatar IA usando la API de Siray (Wan 3.0, Seedance, Kling).

## Requisitos

- Python 3.10+
- Una API key de [Siray](https://console.siray.ai)

## Instalación y uso

```bash
cd video-workflow
pip install -r requirements.txt
python main.py
```

Abrí el navegador en `http://localhost:8000`.

## Flujo de uso

1. Pegá tu API key de Siray y guardala
2. Subí la imagen de tu avatar
3. Escribí el prompt de movimiento
4. Elegí el motor (Wan 3.0 recomendado)
5. Ajustá duración y resolución
6. Activá "Escalar a 1080p" para mejor calidad final
7. Hacé click en **Crear video**

## Costo estimado por video

| Configuración | Costo aprox. |
|---|---|
| Wan 3.0 · 480p · 15s | ~$0.60 |
| Wan 3.0 · 480p · 15s + escalado 1080p | ~$0.71 ✅ |
| Seedance · 480p · 10s | ~$1.34 |
| Kling · 720p · 10s | ~$0.90 |

## Modelos disponibles

| Motor | Ideal para | Precio/s |
|---|---|---|
| **Wan 3.0** ⭐ | Cámara compleja, diálogo, manos | $0.040 |
| Wan 3.0 Spicy | Sin restricciones de contenido | $0.045 |
| Seedance Edit | Físicas complejas, movimientos rápidos | $0.134 |
| Kling Motion Control | Bailes, cámara fija | $0.090 |

## Escalado a 1080p

Usa el escalador de ByteDance via [fal.ai](https://fal.ai) a $0.0072/s.
Añade ~$0.108 por 15 segundos de video.
