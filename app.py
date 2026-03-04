"""
Agente de Voz · Groq LLaMA + edge-tts
Arquitectura corregida: usa st.session_state + st.rerun() con fragmentos,
comunicación via Streamlit.setComponentValue (no location.href),
y streaming del LLM para respuestas más rápidas.
"""
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import asyncio, base64, os, tempfile, json

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agente de Voz · Groq",
    page_icon="🎙️",
    layout="centered",
)

# ── Session state ─────────────────────────────────────────────────────────────
if "messages"    not in st.session_state: st.session_state.messages    = []
if "groq_client" not in st.session_state: st.session_state.groq_client = None
if "api_key"     not in st.session_state: st.session_state.api_key     = ""
if "pending"     not in st.session_state: st.session_state.pending     = None  # {type, payload}

# ── Sidebar config ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 🔑 Groq API Key")
    api_key = st.text_input("", type="password", placeholder="gsk_...",
                            label_visibility="collapsed",
                            value=st.session_state.api_key)
    if api_key and api_key != st.session_state.api_key:
        st.session_state.api_key     = api_key
        st.session_state.groq_client = Groq(api_key=api_key)
    if st.session_state.groq_client:
        st.success("✓ Conectado a Groq")

    st.markdown("---")
    model = st.selectbox("🤖 Modelo", [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
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
        value="Eres un asistente de voz amigable. Responde en español, de forma clara y concisa, en párrafos breves y naturales.")

    st.markdown("---")
    if st.button("🗑️ Nueva conversación", use_container_width=True):
        st.session_state.messages = []
        st.session_state.pending  = None
        st.rerun()

# ── TTS ───────────────────────────────────────────────────────────────────────
async def _tts(text: str, voice: str, rate: str) -> bytes:
    import edge_tts
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        path = f.name
    await edge_tts.Communicate(text, voice, rate=rate, pitch="+0Hz").save(path)
    data = open(path, "rb").read()
    os.unlink(path)
    return data

def tts(text: str, voice: str, rate: str) -> bytes | None:
    clean = (text.replace("*","").replace("_","")
                 .replace("#","").replace("`","").strip())
    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed(): raise RuntimeError
            return loop.run_until_complete(_tts(clean, voice, rate))
        except RuntimeError:
            return asyncio.run(_tts(clean, voice, rate))
    except Exception:
        return None

# ── STT ───────────────────────────────────────────────────────────────────────
def stt(audio_b64: str, client: Groq) -> str:
    raw = base64.b64decode(audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(raw); path = f.name
    try:
        with open(path, "rb") as f:
            r = client.audio.transcriptions.create(
                file=("audio.webm", f, "audio/webm"),
                model="whisper-large-v3-turbo",   # más rápido que large-v3
                language="es",
                response_format="text")
        return (r if isinstance(r, str) else r.text).strip()
    except Exception as e:
        return f"ERROR:{e}"
    finally:
        os.unlink(path)

# ── LLM (streaming) ───────────────────────────────────────────────────────────
def llm_stream(user_msg: str, client: Groq, mdl: str, sys: str):
    """Yield tokens one by one via streaming."""
    msgs = [{"role": "system", "content": sys}]
    for m in st.session_state.messages:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})
    stream = client.chat.completions.create(
        model=mdl, messages=msgs,
        max_tokens=1024, temperature=0.7,
        stream=True
    )
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            yield delta

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono&display=swap');
.stApp { background:#0a0a0f; }
header[data-testid="stHeader"] { background:transparent; }
/* Ocultar el borde del componente iframe */
iframe { border:none !important; }
</style>
<div style="text-align:center;padding:10px 0 4px">
  <h1 style="font-family:'Syne',sans-serif;font-weight:800;color:#e8e8f0;
             font-size:32px;margin:0;letter-spacing:-1px;">🎙️ Agente de Voz</h1>
  <p style="color:#7878a0;font-family:'Space Mono',monospace;font-size:11px;margin-top:4px;">
    Groq · LLaMA 3.3 · edge-tts Neural
  </p>
</div>
""", unsafe_allow_html=True)

# ── Procesar mensaje pendiente ANTES de renderizar el componente ───────────────
response_text  = ""
response_audio = ""

if st.session_state.pending and st.session_state.groq_client:
    p = st.session_state.pending
    st.session_state.pending = None   # consumir inmediatamente

    user_text = ""
    if p["type"] == "voice":
        with st.spinner("🎙️ Transcribiendo..."):
            user_text = stt(p["payload"], st.session_state.groq_client)
        if user_text.startswith("ERROR:"):
            st.error("❌ Error en transcripción: " + user_text)
            user_text = ""
    else:
        user_text = p["payload"]

    if user_text:
        st.session_state.messages.append({"role": "user", "content": user_text})

        # Streaming del LLM
        with st.spinner("🤖 Pensando..."):
            reply_chunks = []
            for token in llm_stream(user_text, st.session_state.groq_client, model, system_prompt):
                reply_chunks.append(token)
            reply = "".join(reply_chunks)

        st.session_state.messages.append({"role": "assistant", "content": reply})
        response_text = reply

        # TTS
        if tts_on:
            with st.spinner("🔊 Generando audio..."):
                audio_bytes = tts(reply, voice_name, tts_rate)
            if audio_bytes:
                response_audio = base64.b64encode(audio_bytes).decode()

# ── Construir historial HTML ──────────────────────────────────────────────────
history_html = ""
for m in st.session_state.messages:
    role_cls  = "user" if m["role"] == "user" else "assistant"
    role_icon = "👤" if m["role"] == "user" else "🤖"
    role_lbl  = "Tú" if m["role"] == "user" else "Agente"
    content   = m["content"].replace("<","&lt;").replace(">","&gt;").replace("\n","<br>")
    history_html += f"""
    <div class="role-label role-{role_cls}">{role_icon} {role_lbl}</div>
    <div class="chat-{role_cls}">{content}</div>"""

if not history_html:
    history_html = """
    <div class="empty-state">
      <div style="font-size:32px;opacity:0.3;margin-bottom:8px;">🤖</div>
      Inicia la conversación con voz o texto
    </div>"""

# ── Componente HTML/JS ────────────────────────────────────────────────────────
# Usa Streamlit.setComponentValue para comunicarse sin page reload
COMPONENT = f"""
<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing:border-box; margin:0; padding:0; }}
  body {{
    background:#0a0a0f; color:#e8e8f0;
    font-family:'Segoe UI',sans-serif; font-size:14px;
    padding:0; overflow-x:hidden;
  }}

  /* ── historial ── */
  #history {{
    padding:16px 16px 8px;
    display:flex; flex-direction:column; gap:4px;
    min-height:60px;
  }}
  .empty-state {{
    text-align:center; padding:32px 0;
    color:#7878a0; font-size:13px;
  }}
  .role-label {{
    font-size:10px; letter-spacing:2px; text-transform:uppercase;
    margin-top:10px; margin-bottom:3px;
  }}
  .role-user      {{ color:#ff6a9a; }}
  .role-assistant {{ color:#7c6aff; }}
  .chat-user {{
    background:#1c1c28; border:1px solid rgba(124,106,255,0.3);
    border-radius:16px 4px 16px 16px; padding:10px 14px; line-height:1.6;
  }}
  .chat-assistant {{
    background:#12121a; border:1px solid #2a2a3d;
    border-radius:4px 16px 16px 16px; padding:10px 14px; line-height:1.6;
  }}
  .chat-thinking {{
    background:#12121a; border:1px solid #2a2a3d;
    border-radius:4px 16px 16px 16px; padding:10px 14px;
    color:#7878a0; font-style:italic;
  }}

  /* dots animation */
  @keyframes blink {{ 0%,80%,100%{{opacity:0}} 40%{{opacity:1}} }}
  .dots span {{
    display:inline-block; width:6px; height:6px;
    border-radius:50%; background:#7878a0; margin:0 2px;
    animation:blink 1.2s infinite;
  }}
  .dots span:nth-child(2){{animation-delay:.2s}}
  .dots span:nth-child(3){{animation-delay:.4s}}

  /* ── controles ── */
  #controls {{
    position:sticky; bottom:0;
    background:#0a0a0f;
    border-top:1px solid #1e1e2e;
    padding:10px 16px 14px;
  }}
  #status {{
    font-size:11px; color:#7878a0; text-align:center;
    margin-bottom:8px; min-height:16px;
    font-family:'Space Mono',monospace;
  }}
  .tabs {{
    display:flex; gap:6px; margin-bottom:10px;
  }}
  .tab {{
    flex:1; padding:7px; border:1px solid #2a2a3d;
    background:#12121a; color:#7878a0; border-radius:8px;
    cursor:pointer; font-size:12px; transition:.15s;
  }}
  .tab:hover  {{ border-color:#7c6aff; color:#e8e8f0; }}
  .tab.active {{ background:#1c1c28; border-color:#7c6aff; color:#e8e8f0; }}

  .input-row {{
    display:flex; gap:8px;
  }}
  input[type=text] {{
    flex:1; background:#12121a; border:1px solid #2a2a3d;
    color:#e8e8f0; border-radius:10px; padding:10px 14px;
    font-size:14px; outline:none; transition:.15s;
  }}
  input[type=text]:focus {{ border-color:#7c6aff; }}
  input[type=text]:disabled {{ opacity:.4; }}

  .btn {{
    background:linear-gradient(135deg,#7c6aff,#ff6a9a);
    border:none; color:#fff; border-radius:10px;
    padding:10px 18px; cursor:pointer; font-size:14px;
    font-weight:600; transition:.15s; white-space:nowrap;
  }}
  .btn:hover    {{ opacity:.85; transform:translateY(-1px); }}
  .btn:disabled {{ opacity:.35; cursor:default; transform:none; }}
  .btn.recording {{
    background:linear-gradient(135deg,#ff4444,#ff6a9a);
    animation:pulse 1s infinite;
  }}
  @keyframes pulse {{
    0%,100%{{box-shadow:0 0 0 0 rgba(255,68,68,.4)}}
    50%{{box-shadow:0 0 0 8px rgba(255,68,68,0)}}
  }}
  #voicePanel, #textPanel {{ display:none; }}
  #voicePanel.visible, #textPanel.visible {{ display:block; }}

  #micBtn {{ width:100%; }}
</style>
</head>
<body>

<div id="history">{history_html}</div>

<div id="controls">
  <div id="status">Listo · escribe o pulsa el micrófono</div>

  <div class="tabs">
    <button class="tab active" id="tabText"  onclick="switchTab('text')">⌨️ Texto</button>
    <button class="tab"        id="tabVoice" onclick="switchTab('voice')">🎙️ Voz</button>
  </div>

  <div id="textPanel" class="visible">
    <div class="input-row">
      <input id="textInput" type="text" placeholder="Escribe tu pregunta..."
             onkeydown="if(event.key==='Enter' && !event.shiftKey)sendText()" />
      <button class="btn" id="sendBtn" onclick="sendText()">➤</button>
    </div>
  </div>

  <div id="voicePanel">
    <button class="btn" id="micBtn" onclick="toggleMic()">🎙️ Pulsa y habla</button>
  </div>
</div>

<script>
// ── Estado ────────────────────────────────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;
let isProcessing  = false;

// ── Respuesta del backend (inyectada en cada render) ──────────────────────────
const RESPONSE_TEXT  = {json.dumps(response_text)};
const RESPONSE_AUDIO = {json.dumps(response_audio)};

if (RESPONSE_TEXT) {{
  setProcessing(false);
  setStatus('✓ Listo');
}}
if (RESPONSE_AUDIO) {{
  playAudio(RESPONSE_AUDIO);
}}

// ── UI helpers ────────────────────────────────────────────────────────────────
function setStatus(msg) {{
  document.getElementById('status').textContent = msg;
}}

function setProcessing(val) {{
  isProcessing = val;
  document.getElementById('sendBtn').disabled  = val;
  document.getElementById('micBtn').disabled   = val;
  document.getElementById('textInput').disabled = val;
}}

function switchTab(tab) {{
  document.getElementById('textPanel').classList.toggle('visible', tab === 'text');
  document.getElementById('voicePanel').classList.toggle('visible', tab === 'voice');
  document.getElementById('tabText').classList.toggle('active', tab === 'text');
  document.getElementById('tabVoice').classList.toggle('active', tab === 'voice');
}}

// ── Audio playback ────────────────────────────────────────────────────────────
function playAudio(b64) {{
  const binary = atob(b64);
  const bytes  = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], {{type:'audio/mpeg'}});
  const url  = URL.createObjectURL(blob);
  const audio = new Audio(url);
  audio.onended = () => URL.revokeObjectURL(url);
  audio.play().catch(e => console.warn('Autoplay blocked:', e));
}}

// ── Enviar texto via Streamlit.setComponentValue ──────────────────────────────
function sendText() {{
  if (isProcessing) return;
  const inp = document.getElementById('textInput');
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = '';

  setProcessing(true);
  setStatus('⚡ Enviando...');

  // Comunicar a Streamlit sin reload de página
  Streamlit.setComponentValue({{type: 'text', payload: txt}});
}}

// ── Grabación de voz ──────────────────────────────────────────────────────────
async function toggleMic() {{
  if (isProcessing) return;
  if (!isRecording) await startRecording();
  else              stopRecording();
}}

async function startRecording() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{audio:true}});
    audioChunks  = [];

    // Elegir el mejor codec disponible
    const mimeType = ['audio/webm;codecs=opus','audio/webm','audio/ogg']
      .find(t => MediaRecorder.isTypeSupported(t)) || '';
    mediaRecorder = new MediaRecorder(stream, mimeType ? {{mimeType}} : {{}});

    mediaRecorder.ondataavailable = e => {{
      if (e.data.size > 0) audioChunks.push(e.data);
    }};

    mediaRecorder.onstop = async () => {{
      stream.getTracks().forEach(t => t.stop());
      const blob   = new Blob(audioChunks, {{type: mediaRecorder.mimeType || 'audio/webm'}});
      const buffer = await blob.arrayBuffer();

      // Convertir a base64 sin Stack Overflow en audios largos
      const bytes  = new Uint8Array(buffer);
      let b64 = '';
      const CHUNK  = 8192;
      for (let i = 0; i < bytes.length; i += CHUNK) {{
        b64 += String.fromCharCode(...bytes.subarray(i, i + CHUNK));
      }}
      b64 = btoa(b64);

      setProcessing(true);
      setStatus('⚡ Transcribiendo y procesando...');
      Streamlit.setComponentValue({{type: 'voice', payload: b64}});
    }};

    mediaRecorder.start(250);   // chunks cada 250ms → latencia baja
    isRecording = true;
    const btn = document.getElementById('micBtn');
    btn.textContent = '⏹ Detener grabación';
    btn.classList.add('recording');
    setStatus('🔴 Grabando... pulsa para detener');

  }} catch(e) {{
    setStatus('❌ Sin acceso al micrófono');
  }}
}}

function stopRecording() {{
  if (mediaRecorder && isRecording) {{
    mediaRecorder.stop();
    isRecording = false;
    const btn = document.getElementById('micBtn');
    btn.textContent = '🎙️ Pulsa y habla';
    btn.classList.remove('recording');
    setStatus('⏳ Procesando audio...');
  }}
}}

// ── Auto-scroll ───────────────────────────────────────────────────────────────
window.addEventListener('load', () => {{
  const last = document.querySelector('#history > *:last-child');
  if (last) last.scrollIntoView({{block:'end'}});
}});
</script>
</body>
</html>
"""

# ── Renderizar y capturar valor del componente ────────────────────────────────
component_value = components.html(COMPONENT, height=620, scrolling=False)

# Streamlit.setComponentValue envía el valor aquí — guardar y hacer rerun
if component_value and isinstance(component_value, dict):
    ctype   = component_value.get("type")
    payload = component_value.get("payload", "")
    if ctype in ("text", "voice") and payload:
        st.session_state.pending = {"type": ctype, "payload": payload}
        st.rerun()
