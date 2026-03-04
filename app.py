"""
Agente de Voz · Groq LLaMA + edge-tts
Usa st.chat_input nativo (texto) + componente HTML mínimo solo para grabar voz.
Sin reruns innecesarios, streaming real del LLM.
"""
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import asyncio, base64, os, tempfile

st.set_page_config(page_title="Agente de Voz · Groq", page_icon="🎙️", layout="centered")

# ── CSS global ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono&display=swap');
.stApp { background:#0a0a0f; }
header[data-testid="stHeader"]{ background:transparent; }
section[data-testid="stChatInput"] textarea {
    background:#12121a !important; color:#e8e8f0 !important;
    border:1px solid #2a2a3d !important; border-radius:12px !important;
}
section[data-testid="stChatInput"] textarea:focus {
    border-color:#7c6aff !important;
}
[data-testid="stChatMessage"] { background:#12121a; border:1px solid #1e1e2e; border-radius:12px; }
</style>
<div style="text-align:center;padding:10px 0 4px">
  <h1 style="font-family:'Syne',sans-serif;font-weight:800;color:#e8e8f0;
             font-size:32px;margin:0;letter-spacing:-1px;">🎙️ Agente de Voz</h1>
  <p style="color:#7878a0;font-family:'Space Mono',monospace;font-size:11px;margin-top:4px;">
    Groq · LLaMA 3.3 · edge-tts Neural
  </p>
</div>
""", unsafe_allow_html=True)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"    not in st.session_state: st.session_state.messages    = []
if "groq_client" not in st.session_state: st.session_state.groq_client = None
if "api_key"     not in st.session_state: st.session_state.api_key     = ""
if "last_audio"  not in st.session_state: st.session_state.last_audio  = None

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Groq API Key")
    api_key = st.text_input("", type="password", placeholder="gsk_...",
                            label_visibility="collapsed",
                            value=st.session_state.api_key)
    if api_key != st.session_state.api_key:
        st.session_state.api_key     = api_key
        st.session_state.groq_client = Groq(api_key=api_key) if api_key else None
    if st.session_state.groq_client:
        st.success("✓ Conectado a Groq")

    st.markdown("---")
    model = st.selectbox("🤖 Modelo", [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "llama3-70b-8192",
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
        st.session_state.messages  = []
        st.session_state.last_audio = None
        st.rerun()

# ── TTS ───────────────────────────────────────────────────────────────────────
async def _tts(text: str, voice: str, rate: str) -> bytes:
    import edge_tts
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    await edge_tts.Communicate(text, voice, rate=rate, pitch="+0Hz").save(path)
    data = open(path,"rb").read(); os.unlink(path)
    return data

def tts(text: str, voice: str, rate: str) -> bytes | None:
    clean = text.replace("*","").replace("_","").replace("#","").replace("`","").strip()
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop.run_until_complete(_tts(clean, voice, rate))
    except Exception:
        return None
    finally:
        loop.close()

# ── STT ───────────────────────────────────────────────────────────────────────
def stt(audio_b64: str, client: Groq) -> str:
    raw = base64.b64decode(audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(raw); path = f.name
    try:
        with open(path,"rb") as f:
            r = client.audio.transcriptions.create(
                file=("audio.webm", f, "audio/webm"),
                model="whisper-large-v3-turbo",
                language="es", response_format="text")
        return (r if isinstance(r, str) else r.text).strip()
    except Exception as e:
        return f"ERROR:{e}"
    finally:
        os.unlink(path)

# ── LLM streaming ─────────────────────────────────────────────────────────────
def llm_stream(user_msg: str, client: Groq, mdl: str, sys: str):
    msgs = [{"role":"system","content":sys}]
    for m in st.session_state.messages:
        msgs.append({"role":m["role"],"content":m["content"]})
    msgs.append({"role":"user","content":user_msg})
    stream = client.chat.completions.create(
        model=mdl, messages=msgs,
        max_tokens=1024, temperature=0.7, stream=True)
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta: yield delta

# ── Función central: procesar un mensaje ─────────────────────────────────────
def process_message(user_text: str):
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

# ── Historial previo ──────────────────────────────────────────────────────────
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# ── Componente de grabación (solo mic, devuelve base64 via setComponentValue) ──
MIC_COMPONENT = """<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{background:transparent;font-family:'Segoe UI',sans-serif;padding:6px 0}
#btn{width:100%;padding:11px;background:linear-gradient(135deg,#7c6aff,#ff6a9a);
  border:none;color:#fff;border-radius:10px;font-size:14px;font-weight:600;
  cursor:pointer;transition:.15s}
#btn:hover{opacity:.85}
#btn.rec{background:linear-gradient(135deg,#ff4444,#ff6a9a);animation:p 1s infinite}
#btn:disabled{opacity:.35;cursor:default}
@keyframes p{0%,100%{box-shadow:0 0 0 0 rgba(255,68,68,.4)}50%{box-shadow:0 0 0 8px rgba(255,68,68,0)}}
#st{font-size:11px;color:#7878a0;text-align:center;margin-top:5px;min-height:15px}
</style></head><body>
<button id="btn" onclick="toggle()">🎙️ Pulsa para grabar</button>
<div id="st">Pulsa el botón para hablar</div>
<script>
let mr=null,chunks=[],rec=false,busy=false;
const btn=document.getElementById('btn'),st=document.getElementById('st');
function setS(t){st.textContent=t}
async function toggle(){if(busy)return;if(!rec)await start();else stop();}
async function start(){
  try{
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    chunks=[];
    const mime=['audio/webm;codecs=opus','audio/webm','audio/ogg'].find(t=>MediaRecorder.isTypeSupported(t))||'';
    mr=new MediaRecorder(stream,mime?{mimeType:mime}:{});
    mr.ondataavailable=e=>{if(e.data.size>0)chunks.push(e.data)};
    mr.onstop=async()=>{
      stream.getTracks().forEach(t=>t.stop());
      const blob=new Blob(chunks,{type:mr.mimeType||'audio/webm'});
      const buf=await blob.arrayBuffer();
      const bytes=new Uint8Array(buf);
      let b64='';const SZ=8192;
      for(let i=0;i<bytes.length;i+=SZ) b64+=String.fromCharCode(...bytes.subarray(i,i+SZ));
      busy=true;btn.disabled=true;setS('⚡ Enviando...');
      Streamlit.setComponentValue(btoa(b64));
    };
    mr.start(250);rec=true;
    btn.textContent='⏹ Detener';btn.classList.add('rec');setS('🔴 Grabando...');
  }catch(e){setS('❌ Sin acceso al micrófono');}
}
function stop(){if(mr&&rec){mr.stop();rec=false;btn.textContent='🎙️ Pulsa para grabar';btn.classList.remove('rec');setS('⏳ Procesando...');}}
</script></body></html>"""

audio_b64 = components.html(MIC_COMPONENT, height=75)

if audio_b64 and isinstance(audio_b64, str) and audio_b64 != st.session_state.last_audio:
    st.session_state.last_audio = audio_b64
    client = st.session_state.groq_client
    if client:
        with st.spinner("🎙️ Transcribiendo..."):
            user_text = stt(audio_b64, client)
        if user_text.startswith("ERROR:"):
            st.error("❌ " + user_text)
        elif user_text:
            process_message(user_text)
    else:
        st.warning("⚠️ Ingresa tu Groq API Key primero.")

# ── Chat input nativo ─────────────────────────────────────────────────────────
if prompt := st.chat_input("Escribe tu pregunta..."):
    process_message(prompt)
