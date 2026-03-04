"""
Agente de Voz · Groq LLaMA + edge-tts
Usa st.audio_input (Streamlit >= 1.37) para grabar voz — sin iframes, sin FastAPI.
"""
import streamlit as st
from groq import Groq
import asyncio, os, tempfile

st.set_page_config(page_title="Agente de Voz · Groq", page_icon="🎙️", layout="centered")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&display=swap');
.stApp { background:#0a0a0f; }
header[data-testid="stHeader"] { background:transparent; }
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
for k, v in [("messages", []), ("groq_client", None), ("api_key", "")]:
    if k not in st.session_state:
        st.session_state[k] = v

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
        st.session_state.messages = []
        st.rerun()

# ── TTS ───────────────────────────────────────────────────────────────────────
async def _tts(text, voice, rate):
    import edge_tts
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    await edge_tts.Communicate(text, voice, rate=rate, pitch="+0Hz").save(path)
    data = open(path, "rb").read()
    os.unlink(path)
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

# ── STT ───────────────────────────────────────────────────────────────────────
def stt(audio_bytes, client):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(audio_bytes)
        path = f.name
    try:
        with open(path, "rb") as f:
            r = client.audio.transcriptions.create(
                file=("audio.wav", f, "audio/wav"),
                model="whisper-large-v3-turbo",
                language="es",
                response_format="text")
        return (r if isinstance(r, str) else r.text).strip()
    except Exception as e:
        return f"ERROR:{e}"
    finally:
        os.unlink(path)

# ── LLM streaming ─────────────────────────────────────────────────────────────
def llm_stream(user_msg, client, mdl, sys_p):
    msgs = [{"role": "system", "content": sys_p}]
    for m in st.session_state.messages:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})
    stream = client.chat.completions.create(
        model=mdl, messages=msgs,
        max_tokens=1024, temperature=0.7, stream=True)
    for chunk in stream:
        d = chunk.choices[0].delta.content
        if d:
            yield d

# ── Procesar mensaje ──────────────────────────────────────────────────────────
def process_message(user_text):
    client = st.session_state.groq_client
    if not client:
        st.warning("⚠️ Ingresa tu Groq API Key en el panel lateral.")
        return

    with st.chat_message("user"):
        st.write(user_text)
    st.session_state.messages.append({"role": "user", "content": user_text})

    with st.chat_message("assistant"):
        reply = st.write_stream(llm_stream(user_text, client, model, system_prompt))
    st.session_state.messages.append({"role": "assistant", "content": reply})

    if tts_on:
        audio_bytes = tts(reply, voice_name, tts_rate)
        if audio_bytes:
            st.audio(audio_bytes, format="audio/mp3", autoplay=True)

# ── Historial ─────────────────────────────────────────────────────────────────
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.write(m["content"])

# ── Entrada de voz (st.audio_input nativo) ────────────────────────────────────
audio = st.audio_input("🎙️ Grabá tu mensaje")
if audio is not None:
    client = st.session_state.groq_client
    if not client:
        st.warning("⚠️ Ingresa tu Groq API Key primero.")
    else:
        with st.spinner("🎙️ Transcribiendo..."):
            user_text = stt(audio.read(), client)
        if user_text.startswith("ERROR:"):
            st.error("❌ " + user_text)
        elif user_text:
            process_message(user_text)

# ── Entrada de texto ──────────────────────────────────────────────────────────
if prompt := st.chat_input("Escribe tu pregunta..."):
    process_message(prompt)
