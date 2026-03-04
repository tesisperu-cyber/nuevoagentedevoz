"""
Agente de Voz · Groq LLaMA + edge-tts
Arquitectura: componente HTML/JS autónomo (mic + audio) +
              endpoints Streamlit para LLM y TTS.
Sin reruns que rompan el estado.
"""
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq
import asyncio, base64, io, os, tempfile, hashlib

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
    except Exception as e:
        return None

# ── STT ───────────────────────────────────────────────────────────────────────
def stt(audio_b64: str, client: Groq) -> str:
    raw = base64.b64decode(audio_b64)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(raw); path = f.name
    try:
        with open(path, "rb") as f:
            r = client.audio.transcriptions.create(
                file=("audio.wav", f, "audio/wav"),
                model="whisper-large-v3", language="es", response_format="text")
        return (r if isinstance(r, str) else r.text).strip()
    except Exception as e:
        return f"ERROR:{e}"
    finally:
        os.unlink(path)

# ── LLM ───────────────────────────────────────────────────────────────────────
def llm(user_msg: str, client: Groq, mdl: str, sys: str) -> str:
    msgs = [{"role": "system", "content": sys}]
    for m in st.session_state.messages:
        msgs.append({"role": m["role"], "content": m["content"]})
    msgs.append({"role": "user", "content": user_msg})
    r = client.chat.completions.create(model=mdl, messages=msgs,
                                       max_tokens=1024, temperature=0.7)
    return r.choices[0].message.content

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Syne:wght@700;800&family=Space+Mono&display=swap');
.stApp { background:#0a0a0f; }
header[data-testid="stHeader"] { background:transparent; }
</style>
<div style="text-align:center;padding:10px 0 4px">
  <h1 style="font-family:'Syne',sans-serif;font-weight:800;color:#e8e8f0;
             font-size:32px;margin:0;letter-spacing:-1px;">🎙️ Agente de Voz</h1>
  <p style="color:#7878a0;font-family:'Space Mono',monospace;font-size:11px;margin-top:4px;">
    Groq · LLaMA 3.3 · edge-tts Neural
  </p>
</div>
""", unsafe_allow_html=True)

# ── Manejo de mensajes entrantes (voz o texto desde el componente) ─────────────
# Streamlit recibe datos del componente JS via query params al hacer submit
query = st.query_params

action   = query.get("action",   "")
payload  = query.get("payload",  "")
src      = query.get("src",      "text")   # "voice" | "text"

response_text  = ""
response_audio = ""  # base64 mp3

if action == "ask" and payload and st.session_state.groq_client:
    # 1. Si viene de voz, transcribir primero
    if src == "voice":
        user_text = stt(payload, st.session_state.groq_client)
        if user_text.startswith("ERROR:"):
            response_text = "❌ Error en transcripción."
            user_text = ""
    else:
        user_text = payload

    if user_text:
        # 2. LLM
        reply = llm(user_text, st.session_state.groq_client, model, system_prompt)
        st.session_state.messages.append({"role": "user",      "content": user_text})
        st.session_state.messages.append({"role": "assistant", "content": reply})
        response_text = reply

        # 3. TTS
        if tts_on:
            audio_bytes = tts(reply, voice_name, tts_rate)
            if audio_bytes:
                response_audio = base64.b64encode(audio_bytes).decode()

    # Limpiar query params para no reprocesar
    st.query_params.clear()

# ── Construir historial HTML para pasar al componente ─────────────────────────
history_html = ""
for m in st.session_state.messages:
    role_cls  = "user" if m["role"] == "user" else "assistant"
    role_icon = "👤" if m["role"] == "user" else "🤖"
    role_lbl  = "Tú" if m["role"] == "user" else "Agente"
    content   = m["content"].replace("<","&lt;").replace(">","&gt;")
    history_html += f"""
    <div class="role-label role-{role_cls}">{role_icon} {role_lbl}</div>
    <div class="chat-{role_cls}">{content}</div>"""

if not history_html:
    history_html = """
    <div class="empty-state">
      <div style="font-size:32px;opacity:0.3;margin-bottom:8px;">🤖</div>
      Inicia la conversación con voz o texto
    </div>"""

# ── Componente HTML/JS autónomo ───────────────────────────────────────────────
# Este componente vive en un iframe — tiene su propio estado JS sin reruns
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
    font-family:'Space Mono',monospace;
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
    display:flex; align-items:center; gap:8px;
  }}

  /* ── dots loader ── */
  .dots span {{
    display:inline-block; width:6px; height:6px;
    background:#7c6aff; border-radius:50%;
    animation:dot 1.2s ease-in-out infinite;
    margin-right:3px;
  }}
  .dots span:nth-child(2){{ animation-delay:.2s }}
  .dots span:nth-child(3){{ animation-delay:.4s }}
  @keyframes dot{{ 0%,100%{{transform:translateY(0);opacity:.4}} 50%{{transform:translateY(-5px);opacity:1}} }}

  /* ── controles ── */
  #controls {{
    position:sticky; bottom:0;
    background:#0a0a0f;
    border-top:1px solid #1e1e2e;
    padding:12px 16px 16px;
    display:flex; flex-direction:column; gap:10px;
  }}

  /* tabs */
  .tabs {{ display:flex; gap:4px; }}
  .tab {{
    flex:1; background:transparent; border:1px solid #2a2a3d;
    border-radius:10px; padding:8px; color:#7878a0;
    font-size:13px; cursor:pointer; transition:all .2s;
  }}
  .tab.active {{ background:#1c1c28; color:#e8e8f0; border-color:#3a3a5a; }}

  /* input row */
  .input-row {{ display:flex; gap:8px; }}
  #textInput {{
    flex:1; background:#12121a; border:1px solid #2a2a3d;
    border-radius:12px; padding:10px 14px; color:#e8e8f0;
    font-size:14px; outline:none; font-family:inherit;
    transition:border-color .2s;
  }}
  #textInput:focus {{ border-color:#7c6aff; }}
  #textInput::placeholder {{ color:#7878a0; }}

  .btn {{
    border:none; border-radius:12px; padding:10px 18px;
    font-size:14px; cursor:pointer; transition:all .2s;
    font-family:inherit; font-weight:600;
  }}
  #sendBtn {{
    background:linear-gradient(135deg,#7c6aff,#5040cc);
    color:white; min-width:48px;
    box-shadow:0 2px 12px rgba(124,106,255,.3);
  }}
  #sendBtn:hover {{ transform:translateY(-1px); box-shadow:0 4px 18px rgba(124,106,255,.4); }}
  #sendBtn:disabled {{ opacity:.4; cursor:not-allowed; transform:none; }}

  /* mic button */
  #micBtn {{
    width:100%; padding:14px;
    background:linear-gradient(135deg,#7c6aff,#5040cc);
    color:white; border-radius:14px;
    font-size:15px; letter-spacing:.5px;
    box-shadow:0 2px 16px rgba(124,106,255,.3);
  }}
  #micBtn.recording {{
    background:linear-gradient(135deg,#cc3333,#801010);
    box-shadow:0 2px 20px rgba(200,50,50,.4);
    animation:pulse .8s ease-in-out infinite;
  }}
  @keyframes pulse{{ 0%,100%{{transform:scale(1)}} 50%{{transform:scale(1.02)}} }}

  /* status */
  #status {{
    font-family:'Space Mono',monospace; font-size:11px;
    color:#7878a0; text-align:center; letter-spacing:1px;
    min-height:16px;
  }}

  /* panel oculto */
  #voicePanel, #textPanel {{ display:none; }}
  #voicePanel.visible, #textPanel.visible {{ display:block; }}
</style>
</head>
<body>

<!-- historial -->
<div id="history">{history_html}</div>

<!-- controles fijos abajo -->
<div id="controls">
  <div id="status"></div>

  <!-- tabs -->
  <div class="tabs">
    <button class="tab active" id="tabText" onclick="switchTab('text')">⌨️ Texto</button>
    <button class="tab"        id="tabVoice" onclick="switchTab('voice')">🎙️ Voz</button>
  </div>

  <!-- texto -->
  <div id="textPanel" class="visible">
    <div class="input-row">
      <input id="textInput" type="text" placeholder="Escribe tu pregunta..."
             onkeydown="if(event.key==='Enter')sendText()" />
      <button class="btn" id="sendBtn" onclick="sendText()">➤</button>
    </div>
  </div>

  <!-- voz -->
  <div id="voicePanel">
    <button class="btn" id="micBtn" onclick="toggleMic()">
      🎙️ Pulsa y habla
    </button>
  </div>
</div>

<script>
// ── Estado JS (persiste sin reruns) ──────────────────────────────────────────
let mediaRecorder = null;
let audioChunks   = [];
let isRecording   = false;
let currentTab    = 'text';
let isProcessing  = false;

// ── Inyectar respuesta si viene del backend ───────────────────────────────────
const RESPONSE_TEXT  = {repr(response_text)};
const RESPONSE_AUDIO = {repr(response_audio)};

if (RESPONSE_TEXT) {{
  // Quitar el "pensando..." si existe
  const thinking = document.getElementById('thinking-bubble');
  if (thinking) thinking.remove();
  appendMessage('assistant', RESPONSE_TEXT);
  setStatus('✓ Listo');
  setProcessing(false);
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
  document.getElementById('sendBtn').disabled = val;
  document.getElementById('micBtn').disabled  = val;
}}

function switchTab(tab) {{
  currentTab = tab;
  document.getElementById('textPanel').classList.toggle('visible', tab === 'text');
  document.getElementById('voicePanel').classList.toggle('visible', tab === 'voice');
  document.getElementById('tabText').classList.toggle('active', tab === 'text');
  document.getElementById('tabVoice').classList.toggle('active', tab === 'voice');
}}

function appendMessage(role, text) {{
  const hist  = document.getElementById('history');
  // Quitar empty state si existe
  const empty = hist.querySelector('.empty-state');
  if (empty) empty.remove();

  const lbl  = document.createElement('div');
  lbl.className = `role-label role-${{role}}`;
  lbl.textContent = role === 'user' ? '👤 Tú' : '🤖 Agente';

  const bub  = document.createElement('div');
  bub.className = `chat-${{role}}`;
  bub.textContent = text;

  hist.appendChild(lbl);
  hist.appendChild(bub);
  bub.scrollIntoView({{behavior:'smooth', block:'end'}});
}}

function appendThinking() {{
  const hist = document.getElementById('history');
  const lbl  = document.createElement('div');
  lbl.className = 'role-label role-assistant';
  lbl.textContent = '🤖 Agente';
  lbl.id = 'thinking-label';

  const bub  = document.createElement('div');
  bub.className = 'chat-thinking';
  bub.id = 'thinking-bubble';
  bub.innerHTML = '<div class="dots"><span></span><span></span><span></span></div> Pensando...';

  hist.appendChild(lbl);
  hist.appendChild(bub);
  bub.scrollIntoView({{behavior:'smooth', block:'end'}});
}}

// ── Audio playback ─────────────────────────────────────────────────────────
function playAudio(b64) {{
  // Decodificar y usar Blob URL para reproducción suave sin buffering
  const binary = atob(b64);
  const bytes  = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  const blob = new Blob([bytes], {{type: 'audio/mpeg'}});
  const url  = URL.createObjectURL(blob);

  const audio = new Audio(url);
  audio.onended = () => URL.revokeObjectURL(url);
  audio.onerror = (e) => console.warn('Audio error', e);
  audio.play().catch(e => console.warn('Autoplay blocked:', e));
}}

// ── Enviar texto ──────────────────────────────────────────────────────────────
function sendText() {{
  if (isProcessing) return;
  const inp = document.getElementById('textInput');
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = '';

  appendMessage('user', txt);
  appendThinking();
  setProcessing(true);
  setStatus('⚡ Enviando...');

  // Comunicar a Streamlit via query params + reload del parent
  const params = new URLSearchParams({{
    action: 'ask',
    payload: txt,
    src: 'text',
    _ts: Date.now()   // evita cache
  }});
  window.parent.location.href = window.parent.location.pathname + '?' + params.toString();
}}

// ── Grabación de voz ──────────────────────────────────────────────────────────
async function toggleMic() {{
  if (isProcessing) return;
  if (!isRecording) await startRecording();
  else               stopRecording();
}}

async function startRecording() {{
  try {{
    const stream = await navigator.mediaDevices.getUserMedia({{audio:true}});
    audioChunks  = [];
    mediaRecorder = new MediaRecorder(stream, {{mimeType:'audio/webm'}});

    mediaRecorder.ondataavailable = e => {{
      if (e.data.size > 0) audioChunks.push(e.data);
    }};

    mediaRecorder.onstop = async () => {{
      stream.getTracks().forEach(t => t.stop());
      const blob   = new Blob(audioChunks, {{type:'audio/webm'}});
      const buffer = await blob.arrayBuffer();
      const b64    = btoa(String.fromCharCode(...new Uint8Array(buffer)));

      appendThinking();
      setProcessing(true);
      setStatus('⚡ Transcribiendo y procesando...');

      const params = new URLSearchParams({{
        action: 'ask',
        payload: b64,
        src: 'voice',
        _ts: Date.now()
      }});
      window.parent.location.href = window.parent.location.pathname + '?' + params.toString();
    }};

    mediaRecorder.start();
    isRecording = true;
    const btn = document.getElementById('micBtn');
    btn.textContent = '⏹ Detener grabación';
    btn.classList.add('recording');
    setStatus('🔴 Grabando... pulsa para detener');

  }} catch(e) {{
    setStatus('❌ Sin acceso al micrófono');
    console.error(e);
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

// ── Auto-scroll al cargar ─────────────────────────────────────────────────────
window.addEventListener('load', () => {{
  const last = document.querySelector('#history > *:last-child');
  if (last) last.scrollIntoView({{block:'end'}});
  setStatus('Listo · escribe o pulsa el micrófono');
}});
</script>
</body>
</html>
"""

# ── Renderizar componente ─────────────────────────────────────────────────────
components.html(COMPONENT, height=620, scrolling=False)
