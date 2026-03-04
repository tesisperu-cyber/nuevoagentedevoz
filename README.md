[README.md](https://github.com/user-attachments/files/25748040/README.md)
# 🎙️ Agente de Voz · Groq + LLaMA

Agente conversacional con entrada por **voz y texto**, respuesta por **audio y texto**, powered by **Groq API** con **LLaMA 3.3 70B** y transcripción con **Whisper**.

---

## ✨ Características

- 🎙️ **Entrada por voz** — graba desde el micrófono, transcribe con Groq Whisper
- ⌨️ **Entrada por texto** — escribe tu pregunta directamente
- 🔊 **Respuesta por audio** — síntesis de voz con gTTS (autoplay)
- 💬 **Respuesta por texto** — historial de conversación completo con contexto
- 🤖 **LLaMA 3.3 70B** — vía Groq (ultra rápido, gratis)
- ⚙️ **Configurable** — modelo, velocidad de voz, prompt del sistema

---

## 🚀 Deploy en Streamlit Cloud

### 1. Fork / sube a GitHub

```
agente-voz/
├── app.py
├── requirements.txt
└── README.md
```

### 2. Ve a [share.streamlit.io](https://share.streamlit.io)

- Conecta tu cuenta de GitHub
- Selecciona el repositorio
- Archivo principal: `app.py`
- Clic en **Deploy**

### 3. Configura el secreto (opcional pero recomendado)

En Streamlit Cloud → Settings → Secrets:

```toml
GROQ_API_KEY = "gsk_xxxxxxxxxxxxxxxxxxxx"
```

Si configuras el secreto, puedes pre-cargar la key en `app.py` agregando al inicio:

```python
import os
api_key = st.sidebar.text_input(...) or os.environ.get("GROQ_API_KEY", "")
```

---

## 💻 Ejecución local

### Requisitos

- Python 3.9+
- Cuenta en [console.groq.com](https://console.groq.com) (gratis)

### Instalación

```bash
# Clona el repositorio
git clone https://github.com/tu-usuario/agente-voz.git
cd agente-voz

# Crea entorno virtual
python -m venv venv
source venv/bin/activate        # Linux/Mac
venv\Scripts\activate           # Windows

# Instala dependencias
pip install -r requirements.txt

# Ejecuta
streamlit run app.py
```

Abre tu navegador en `http://localhost:8501`

---

## 🔑 Obtener Groq API Key

1. Ve a [console.groq.com](https://console.groq.com)
2. Crea una cuenta gratuita
3. Ve a **API Keys** → **Create API Key**
4. Copia la key (empieza con `gsk_`)
5. Pégala en el panel lateral de la app

---

## 📦 Stack técnico

| Componente | Tecnología |
|---|---|
| Frontend | Streamlit |
| LLM | LLaMA 3.3 70B via Groq |
| Transcripción voz → texto | Groq Whisper Large v3 |
| Síntesis texto → voz | gTTS (Google Text-to-Speech) |
| Grabación en browser | audio-recorder-streamlit |

---

## 🎛️ Modelos disponibles

| Modelo | Velocidad | Calidad |
|---|---|---|
| `llama-3.3-70b-versatile` | ⚡⚡⚡ | ⭐⭐⭐⭐⭐ |
| `llama-3.1-8b-instant` | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ |
| `llama3-70b-8192` | ⚡⚡⚡ | ⭐⭐⭐⭐ |
| `llama3-8b-8192` | ⚡⚡⚡⚡⚡ | ⭐⭐⭐ |

---

## 📁 Estructura del proyecto

```
agente-voz/
├── app.py              # Aplicación Streamlit principal
├── requirements.txt    # Dependencias Python
└── README.md           # Este archivo
```

---

## 📝 Licencia

MIT — libre de usar, modificar y distribuir.
