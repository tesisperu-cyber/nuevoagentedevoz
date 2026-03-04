"""
Agente de Voz · Groq LLaMA + edge-tts
========================================
Arquitectura definitiva:
  - Texto: st.chat_input nativo (instantáneo)
  - Voz: El navegador hace fetch() directo a /stt (FastAPI corriendo en hilo aparte)
         FastAPI transcribe y devuelve el texto → JS escribe en el chat input
         → usuario presiona Enter (o auto-submit)

Para voz, NO se pasan datos binarios grandes a Streamlit.
El audio va directo al endpoint /stt en el mismo proceso Python.
"""
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import asyncio, base64, os, tempfile, threading

# ── FastAPI para recibir audio del navegador ──────────────────────────────────
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

_api_app = FastAPI()
_api_app.add_middleware(CORSMiddleware, allow_origins=["*"],
                        allow_methods=["*"], allow_headers=["*"])
_api_started = False

@_api_app.post("/stt")
async def transcribe(file: UploadFile = File(...), api_key: str = Form(...)):
    import tempfile, os
    data = await file.read()
    suffix = ".webm"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
        f.write(data); path = f.name
    try:
        client = Groq(api_key=api_key)
        with open(path,"rb") as f:
            r = client.audio.transcriptions.create(
                file=("audio.webm", f, "audio/webm"),
                model="whisper-large-v3-turbo",
                language="es", response_format="text")
        text = (r if isinstance(r, str) else r.text).strip()
        return {"text": text}
    except Exception as e:
        return {"error": str(e)}
    finally:
        os.unlink(path)

def _start_api():
    uvicorn.run(_api_app, host="127.0.0.1", port=8502, log_level="error")

def ensure_api():
    global _api_started
    if not _api_started:
        t = threading.Thread(target=_start_api, daemon=True)
        t.start()
        _api_started = True

ensure_api()

# ── Streamlit app ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Agente de Voz · Groq", page_icon="🎙️", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&display=swap');
.stApp { background:#0a0a0f; }
header[data-testid="stHeader"]{ background:transparent; }
[data-testid="stChatMessage"] {
    background:#12121a !important;
    border:1px solid #1e1e2e !important;
    border-radius:12px !important;
}
</style>
<div style="text-align:center;padding:10px 0 4px">
  <h1 style="font-family:'Syne',sans-serif;font-weight:800;color:#e8e8f0;
             font-size:32px;margin:0;letter-spacing:-1px;">🎙️ Agente de Voz</h1>
  <p style="color:#7878a0;font-family:monospace;font-size:11px;margin-top:4px;">
    Groq · LLaMA · edge-tts Neural
  </p>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
for k,v in [("messages",[]),("groq_client",None),("api_key",""),("voice_text","")]:
    if k not in st.session_state: st.session_state[k] = v

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Groq API Key")
    api_key = st.text_input("", type="password", placeholder="gsk_...",
                            label_visibility="collapsed",
                            value=st.session_state.api_key)
    if api_key != st.session_state.api_key:
        st.session_state.api_key = api_key
        st.session_state.groq_client = Groq(api_key=api_key) if api_key else None
    if st.session_state.groq_client:
        st.success("✓ Conectado a Groq")

    st.markdown("---")
    model = st.selectbox("🤖 Modelo", [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
    ])

    st.markdown("---")
    voice_map = {
        "🇲🇽 Jorge (México)"   : "es-MX-JorgeNeural",
        "🇲🇽 Dalia (México)"   : "es-MX-DaliaNeural",
        "🇪🇸 Alvaro (España)"  : "es-ES-AlvaroNeural",
        "🇪🇸 Elvira (España)"  : "es-ES-ElviraNeural",
        "🇦🇷 Tomas (Argentina)": "es-AR-TomasNeural",
        "🇵🇪 Alex (Perú)"      : "es-PE-AlexNeural",
        "🇨🇴 Salome (Colombia)": "es-CO-SalomeNeural",
    }
    voice_label = st.selectbox("🔊 Voz", list(voice_map.keys()))
    voice_name  = voice_map[voice_label]
    tts_rate    = st.select_slider("Velocidad", ["-20%","-10%","+0%","+10%","+20%"], value="+0%")
    tts_on      = st.toggle("Audio activado", value=True)

    st.markdown("---")
    system_prompt = st.text_area("💬 Comportamiento", height=100,
        value="Eres un asistente de voz amigable. Responde en español, de forma clara y concisa.")

    st.markdown("---")
    if st.button("🗑️ Nueva conversación", use_container_width=True):
        st.session_state.messages   = []
        st.session_state.voice_text = ""
        st.rerun()

# ── TTS ───────────────────────────────────────────────────────────────────────
async def _tts(text, voice, rate):
    import edge_tts
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    await edge_tts.Communicate(text, voice, rate=rate, pitch="+0Hz").save(path)
    data = open(path,"rb").read(); os.unlink(path)
    return data

def tts(text, voice, rate):
    clean = text.replace("*","").replace("_","").replace("#","").replace("`","").strip()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_tts(clean, voice, rate))
    except Exception:
        return None
    finally:
        loop.close()

# ── LLM streaming ─────────────────────────────────────────────────────────────
def llm_stream(user_msg, client, mdl, sys_p):
    msgs = [{"role":"system","content":sys_p}]
    for m in st.session_state.messages:
        msgs.append({"role":m["role"],"content":m["content"]})
    msgs.append({"role":"user","content":user_msg})
    stream = client.chat.completions.create(
        model=mdl, messages=msgs, max_tokens=1024, temperature=0.7, stream=True)
    for chunk in stream:
        d = chunk.choices[0].delta.content
        if d: yield d

# ── Procesar mensaje ───────────────────────────────────────────────────────────
def process_message(user_text):
    client = st.session_state.groq_client
    if not client:
        st.warning("⚠️ Ingresa tu Groq API Key en el panel lateral.")
        return
    with st.chat_message("user"):
        st.write(user_text)
    st.session_state.messages.append({"role":"user","content":user_text})

    with st.chat_message("assistant"):
        reply = st.write_stream(llm_stream(user_text, client, model, system_prompt))
    st.session_state.messages.append({"role":"assistant","content":reply})

    if tts_on:
        audio_bytes = tts(reply, voice_name, tts_rate)
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)

# ── Historial ─────────────────────────────────────────────────────────────────
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# ── Procesar voz transcrita si llegó ──────────────────────────────────────────
if st.session_state.voice_text:
    txt = st.session_state.voice_text
    st.session_state.voice_text = ""
    process_message(txt)

# ── Componente mic ─────────────────────────────────────────────────────────────
# El JS hace fetch a FastAPI en :8502/stt y devuelve el texto transcrito
# Luego lo pasa a Streamlit via setComponentValue (solo texto pequeño = funciona)
MIC = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:transparent;padding:4px 0;font-family:'Segoe UI',sans-serif}}
#btn{{width:100%;padding:11px;border:none;color:#fff;border-radius:10px;
  font-size:14px;font-weight:600;cursor:pointer;
  background:linear-gradient(135deg,#7c6aff,#ff6a9a)}}
#btn:hover{{opacity:.85}}
#btn.rec{{background:linear-gradient(135deg,#ff4444,#ff6a9a);animation:p 1s infinite}}
#btn:disabled{{opacity:.4;cursor:default}}
@keyframes p{{0%,100%{{box-shadow:0 0 0 0 rgba(255,68,68,.4)}}50%{{box-shadow:0 0 0 8px rgba(255,68,68,0)}}}}
#st{{font-size:11px;color:#7878a0;text-align:center;margin-top:5px;min-height:14px}}
</style></head><body>
<button id="btn" onclick="toggle()">🎙️ Pulsa para grabar</button>
<div id="st">Pulsa el botón y habla</div>
<script>
const API_KEY = {repr(st.session_state.api_key)};
let mr=null,chunks=[],rec=false;
const btn=document.getElementById('btn'),st=document.getElementById('st');

async function toggle(){{if(rec)stop();else await start();}}

async function start(){{
  try{{
    const stream=await navigator.mediaDevices.getUserMedia({{audio:true}});
    chunks=[];
    const mime=['audio/webm;codecs=opus','audio/webm','audio/ogg']
                .find(t=>MediaRecorder.isTypeSupported(t))||'';
    mr=new MediaRecorder(stream,mime?{{mimeType:mime}}:{{}});
    mr.ondataavailable=e=>{{if(e.data.size>0)chunks.push(e.data)}};
    mr.onstop=async()=>{{
      stream.getTracks().forEach(t=>t.stop());
      st.textContent='⚡ Transcribiendo...';
      btn.disabled=true;
      const blob=new Blob(chunks,{{type:mr.mimeType||'audio/webm'}});
      const fd=new FormData();
      fd.append('file', blob, 'audio.webm');
      fd.append('api_key', API_KEY);
      try{{
        const res=await fetch('http://127.0.0.1:8502/stt',{{method:'POST',body:fd}});
        const data=await res.json();
        if(data.error){{ st.textContent='❌ '+data.error; btn.disabled=false; return; }}
        st.textContent='✓ "'+data.text+'"';
        // Enviar texto (pequeño) a Streamlit
        Streamlit.setComponentValue(data.text);
      }}catch(e){{
        st.textContent='❌ Error conectando al servidor local';
        btn.disabled=false;
      }}
    }};
    mr.start(250);rec=true;
    btn.textContent='⏹ Detener';btn.classList.add('rec');
    st.textContent='🔴 Grabando...';
  }}catch(e){{st.textContent='❌ Sin acceso al micrófono';}}
}}

function stop(){{
  if(mr&&rec){{
    mr.stop();rec=false;
    btn.textContent='🎙️ Pulsa para grabar';
    btn.classList.remove('rec');
    st.textContent='⏳ Procesando...';
  }}
}}
</script></body></html>"""

voice_result = components.html(MIC, height=72)

if voice_result and isinstance(voice_result, str) and len(voice_result) > 1:
    st.session_state.voice_text = voice_result
    st.rerun()

# ── Chat input de texto ───────────────────────────────────────────────────────
if prompt := st.chat_input("Escribe tu pregunta..."):
    process_message(prompt)
