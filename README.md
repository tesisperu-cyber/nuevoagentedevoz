
[README.md](https://github.com/user-attachments/files/25748544/README.md)
# 🎙️ Agente de Voz · Groq + LLaMA + edge-tts

Asistente de voz en español construido con Streamlit, la API de Groq (LLaMA 3.3) y síntesis de voz neural mediante edge-tts.

---

## ✨ Características

- **Entrada por voz** — graba tu pregunta con el micrófono del navegador
- **Entrada por texto** — escribe directamente con soporte de Enter para enviar
- **Respuesta en audio** — síntesis de voz neural con 7 voces en español (México, España, Argentina, Perú, Colombia)
- **Streaming del LLM** — las respuestas se generan token a token para menor latencia
- **Historial de conversación** — contexto completo enviado en cada petición
- **Sin recargas de página** — comunicación directa con `Streamlit.setComponentValue`

---

## 🚀 Instalación

### 1. Clonar / descargar el proyecto

```bash
git clone <tu-repo>
cd agente-voz
```

### 2. Crear entorno virtual (recomendado)

```bash
python -m venv .venv
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 4. Ejecutar

```bash
streamlit run app.py
```

La app abrirá en `http://localhost:8501`.

---

## 🔑 Configuración

| Parámetro | Dónde | Descripción |
|---|---|---|
| **Groq API Key** | Sidebar | Obtén la tuya gratis en [console.groq.com](https://console.groq.com) |
| **Modelo** | Sidebar | `llama-3.3-70b-versatile` (más capaz) o `llama-3.1-8b-instant` (más rápido) |
| **Voz** | Sidebar | 7 voces neurales en español |
| **Velocidad** | Sidebar | De −20% a +20% |
| **Audio activado** | Sidebar | Toggle para activar/desactivar TTS |
| **Comportamiento** | Sidebar | System prompt personalizable |

---

## 📁 Estructura

```
.
├── app.py              # Aplicación principal
├── requirements.txt    # Dependencias Python
└── README.md           # Este archivo
```

---

## 📦 Dependencias

```
streamlit>=1.32.0    # Framework web
groq>=0.9.0          # Cliente Groq (LLM + Whisper STT)
edge-tts>=6.1.9      # Síntesis de voz neural (Microsoft Edge TTS)
```

---

## 🏗️ Arquitectura

```
Navegador (iframe)
  │
  ├─ Graba audio  ──► MediaRecorder API ──► base64
  │
  └─ Streamlit.setComponentValue({type, payload})
                          │
                    st.session_state.pending
                          │
                    st.rerun()
                          │
              ┌─────────────────────┐
              │      app.py         │
              │  STT (Whisper)      │  ← solo si type == "voice"
              │  LLM streaming      │  ← Groq completions
              │  TTS (edge-tts)     │  ← solo si audio activado
              └─────────────────────┘
                          │
                   response_text + response_audio (base64 mp3)
                          │
                   inyectado en el HTML del componente
```

**¿Por qué no `window.parent.location.href`?**
La versión anterior recargaba la página completa en cada mensaje, lo que causaba demoras de 2–4 segundos antes de siquiera empezar a procesar. Ahora se usa `Streamlit.setComponentValue` para comunicar el mensaje al backend sin ningún reload, y `st.rerun()` solo se dispara cuando hay un mensaje pendiente real.

---

## 🔒 Seguridad

- La API Key **nunca se guarda en disco** — vive solo en `st.session_state`
- El audio grabado se procesa en memoria y se borra del disco inmediatamente tras la transcripción
- No hay persistencia entre sesiones

---

## 🐛 Solución de problemas

| Problema | Solución |
|---|---|
| *"Sin acceso al micrófono"* | Permite el acceso al micrófono en el navegador (icono 🔒 en la barra de dirección) |
| *"Error en transcripción"* | Verifica que la API Key sea válida y tenga cuota disponible |
| *El audio no suena* | Algunos navegadores bloquean el autoplay; interactúa con la página primero |
| *Respuestas lentas* | Usa `llama-3.1-8b-instant` en lugar del modelo 70B |

---

## 📄 Licencia

MIT — úsalo libremente.
