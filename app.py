import streamlit as st
import pandas as pd
import re
import json
import io

st.set_page_config(
    page_title="Consulta Catálogo CAT",
    page_icon="🔧",
    layout="wide"
)

st.markdown("""
<style>
    .block-container { padding-top: 2rem; }
    .header-box {
        background: linear-gradient(135deg, #0d1b2a 0%, #1e2a35 100%);
        border-radius: 12px;
        padding: 1.5rem 2rem;
        margin-bottom: 2rem;
        border-left: 5px solid #4fc3f7;
    }
    .header-box h1 { color: #ffffff; font-size: 1.8rem; margin: 0; }
    .header-box p  { color: #90a4ae; margin: 0.3rem 0 0; font-size: 0.95rem; }
    .script-box {
        background: #0d1117;
        color: #58a6ff;
        font-family: monospace;
        font-size: 12px;
        padding: 1rem;
        border-radius: 8px;
        overflow-x: auto;
        white-space: pre;
        max-height: 300px;
        overflow-y: auto;
        border: 1px solid #30363d;
    }
    .step-header {
        background: #1e2a35;
        border-left: 4px solid #4fc3f7;
        padding: 0.6rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
        font-weight: 700;
        font-size: 1rem;
        color: #e0f7ff !important;
    }
    .instruccion {
        background: #1a2744;
        border: 1px solid #1e3a5f;
        border-radius: 8px;
        padding: 0.75rem 1rem;
        font-size: 0.9rem;
        margin-bottom: 1rem;
        color: #cfd8dc;
        line-height: 1.8;
    }
    .tanda-info {
        font-size: 1.05rem;
        font-weight: 700;
        color: #ffffff !important;
        margin-bottom: 0.5rem;
        background: #1e2a35;
        padding: 0.5rem 0.75rem;
        border-radius: 6px;
        display: inline-block;
    }
    .footer {
        text-align: center;
        color: #546e7a;
        font-size: 0.8rem;
        margin-top: 3rem;
        padding-top: 1rem;
        border-top: 1px solid #1e2a35;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="header-box">
    <h1>🔧 Consulta Catálogo CAT</h1>
    <p>Interlog Comercio Exterior · Consulta masiva de descripciones en parts.cat.com</p>
</div>
""", unsafe_allow_html=True)

# ─── Helpers ────────────────────────────────────────────────────────────────
HEADERS_VALIDOS = [
    "part number", "part_number", "partnumber",
    "codigo de parte", "código de parte",
    "codigo de material", "código de material",
    "codigo", "código", "code", "part", "parte",
    "numero de parte", "número de parte",
    "item", "referencia", "ref"
]

def detectar_columna(df):
    for col in df.columns:
        if str(col).strip().lower() in HEADERS_VALIDOS:
            return col
    return df.columns[0]

def normalizar(raw):
    s = str(raw).strip().upper()
    s = re.sub(r'\s+', '', s)
    if not s or s in ('NAN', 'NONE', ''):
        return None
    if re.match(r'^\d{7,}$', s):
        return s[:-4] + '-' + s[-4:]
    m = re.match(r'^([A-Z0-9]{2,4})(\d{4,})$', s)
    if m:
        return m.group(1) + '-' + m.group(2)
    if '-' in s:
        return s
    return s

def armar_url(cod):
    return f"https://parts.cat.com/es/catcorp/product/{cod}"

def generar_script(tanda_codigos, idx, pausa, variacion, corte):
    urls = [armar_url(c) for c in tanda_codigos]
    return f"""(async () => {{
  const urls = {json.dumps(urls)};
  const cods = {json.dumps(tanda_codigos)};
  const pausa = {int(pausa * 1000)};
  const variacion = {int(variacion * 1000)};
  const maxErrores = {corte};
  const resultados = [];
  let errores403 = 0;

  function esperar(ms) {{ return new Promise(r => setTimeout(r, ms)); }}

  for (let i = 0; i < urls.length; i++) {{
    const url = urls[i];
    const cod = cods[i];
    console.log(`[${{i+1}}/${{urls.length}}] Consultando ${{cod}}...`);
    try {{
      const res = await fetch(url, {{ headers: {{ 'Accept': 'text/html' }} }});
      if (res.status === 403) {{
        errores403++;
        console.warn(`403 en ${{cod}} (${{errores403}} seguidos)`);
        resultados.push({{ codigo: cod, url, estado: '403', descripcion: '' }});
        if (errores403 >= maxErrores) {{
          console.error('Corte por 403. Descargando parcial...');
          break;
        }}
      }} else if (res.status === 404) {{
        errores403 = 0;
        resultados.push({{ codigo: cod, url, estado: '404', descripcion: 'No encontrado' }});
      }} else {{
        errores403 = 0;
        const html = await res.text();
        const parser = new DOMParser();
        const doc = parser.parseFromString(html, 'text/html');
        const titleraw = doc.querySelector('title')?.textContent?.trim() || '';
        let descripcion = titleraw;
        if (titleraw.includes(':')) descripcion = titleraw.split(':').slice(1).join(':').trim();
        if (descripcion.includes('|')) descripcion = descripcion.split('|')[0].trim();
        resultados.push({{ codigo: cod, url, estado: 'ok', descripcion }});
      }}
    }} catch(e) {{
      resultados.push({{ codigo: cod, url, estado: 'error', descripcion: e.message }});
    }}
    if (i < urls.length - 1) {{
      const ms = pausa + (Math.random() * 2 - 1) * variacion;
      await esperar(Math.max(ms, 1000));
    }}
  }}

  const csv = ['codigo;url;estado;descripcion'].concat(
    resultados.map(r => [r.codigo, r.url, r.estado, r.descripcion.replace(/;/g, ',')].join(';'))
  ).join('\\n');

  const blob = new Blob(['\uFEFF' + csv], {{ type: 'text/csv;charset=utf-8;' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'cat_tanda_{idx+1}.csv';
  a.click();
  console.log('\\n✅ Tanda {idx+1} completa. CSV descargado.');
}})();"""

# ─── Session state ───────────────────────────────────────────────────────────
for key, val in [('codigos_raw', []), ('unicos', []), ('tandas', []), ('tandas_done', set()), ('procesado', False)]:
    if key not in st.session_state:
        st.session_state[key] = val

# ════════════════════════════════════════════════════════════════════════════
# PASO 1 — CARGAR CÓDIGOS
# ════════════════════════════════════════════════════════════════════════════
st.markdown('<div class="step-header">📂 Paso 1 — Cargar códigos de parte</div>', unsafe_allow_html=True)

metodo = st.radio("Método de carga", ["Subir Excel / CSV", "Pegar códigos"], horizontal=True)
codigos_raw = []

if metodo == "Subir Excel / CSV":
    archivo = st.file_uploader("Subí tu archivo", type=["xlsx", "xls", "csv"])
    if archivo:
        try:
            if archivo.name.endswith(".csv"):
                df_raw = pd.read_csv(archivo, header=None, dtype=str)
                primera = str(df_raw.iloc[0, 0]).strip().lower()
                if primera in HEADERS_VALIDOS:
                    archivo.seek(0)
                    df = pd.read_csv(archivo, dtype=str)
                    col = detectar_columna(df)
                else:
                    df = df_raw
                    col = df.columns[0]
            else:
                df_raw = pd.read_excel(archivo, header=None, dtype=str)
                primera = str(df_raw.iloc[0, 0]).strip().lower()
                if primera in HEADERS_VALIDOS:
                    archivo.seek(0)
                    df = pd.read_excel(archivo, dtype=str)
                    col = detectar_columna(df)
                else:
                    df = df_raw
                    col = df.columns[0]

            codigos_raw = df[col].dropna().astype(str).tolist()
            st.success(f"✅ {len(codigos_raw)} filas cargadas — columna detectada: **{col}**")
        except Exception as e:
            st.error(f"Error al leer el archivo: {e}")
else:
    texto = st.text_area(
        "Pegá los códigos — uno por línea",
        height=180,
        placeholder="2530857\n1P0459\n4T2584\n2530857"
    )
    if texto.strip():
        codigos_raw = [l.strip() for l in texto.splitlines() if l.strip()]

btn_procesar = st.button("▶ Procesar códigos", type="primary", disabled=(len(codigos_raw) == 0))
if btn_procesar and codigos_raw:
    st.session_state.codigos_raw = codigos_raw
    st.session_state.procesado = True
    st.session_state.tandas_done = set()

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN + SCRIPTS
# ════════════════════════════════════════════════════════════════════════════
if st.session_state.procesado and st.session_state.codigos_raw:

    codigos_raw = st.session_state.codigos_raw

    st.divider()
    st.markdown('<div class="step-header">⚙️ Configuración de tandas</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="instruccion">
    <strong>Códigos por tanda:</strong> cuántos códigos consulta el script de una vez.<br>
    <strong>Pausa entre requests:</strong> segundos que espera entre cada consulta. Más pausa = menos riesgo de bloqueo.<br>
    <strong>Variación aleatoria:</strong> hace que la pausa no sea fija sino aleatoria (ej: 5 ± 2 = entre 3 y 7 seg). Simula comportamiento humano.<br>
    <strong>Corte por 403:</strong> si CAT bloquea N veces seguidas, el script para y descarga lo que pudo.
    </div>
    """, unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    tam_tanda = c1.number_input("Códigos por tanda",        min_value=10,  max_value=1000, value=80,  step=10)
    pausa     = c2.number_input("Pausa entre requests (seg)", min_value=2.0, max_value=30.0, value=5.0, step=0.5)
    variacion = c3.number_input("Variación aleatoria (±seg)", min_value=0.0, max_value=10.0, value=2.0, step=0.5)
    corte_403 = c4.number_input("Corte por 403 seguidos",   min_value=1,   max_value=10,  value=3)

    unicos_dict = {}
    for r in codigos_raw:
        n = normalizar(r)
        if n and n not in unicos_dict:
            unicos_dict[n] = True
    unicos = list(unicos_dict.keys())
    repetidos = len(codigos_raw) - len(unicos)
    tandas = [unicos[i:i+int(tam_tanda)] for i in range(0, len(unicos), int(tam_tanda))]

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Líneas totales",   len(codigos_raw))
    m2.metric("Códigos únicos",   len(unicos))
    m3.metric("Repetidos",        repetidos)
    m4.metric("Tandas generadas", len(tandas))

    with st.expander("Vista previa — primeros 10 códigos normalizados"):
        prev = [{"Original": r, "Normalizado": normalizar(r), "URL": armar_url(normalizar(r))}
                for r in codigos_raw[:10] if normalizar(r)]
        st.dataframe(pd.DataFrame(prev), use_container_width=True, hide_index=True)

    # ════════════════════════════════════════════════════════════════════════
    # PASO 2 — SCRIPTS
    # ════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown('<div class="step-header">📋 Paso 2 — Scripts por tanda</div>', unsafe_allow_html=True)

    st.markdown("""
    <div class="instruccion">
    1. Abrí <strong>parts.cat.com</strong> en tu navegador corporativo (cualquier página del sitio)<br>
    2. Presioná <strong>F12</strong> → hacé click en la pestaña <strong>Console</strong><br>
    3. Copiá el script de la tanda con el botón y pegalo en la consola → presioná <strong>Enter</strong><br>
    4. Esperá que termine — se descarga un CSV automáticamente con los resultados<br>
    5. Repetí para cada tanda. Cuando termines todas, pasá al Paso 3.
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([f"Tanda {i+1}  ({len(t)} cód.)" for i, t in enumerate(tandas)])

    for i, (tab, tanda) in enumerate(zip(tabs, tandas)):
        with tab:
            t_min = int(len(tanda) * max(pausa - variacion, 1))
            t_max = int(len(tanda) * (pausa + variacion))

            col_a, col_b = st.columns([4, 1])
            col_a.markdown(
                f'<div class="tanda-info">📦 {len(tanda)} códigos únicos &nbsp;·&nbsp; ⏱ Tiempo estimado: {t_min}–{t_max} seg</div>',
                unsafe_allow_html=True
            )

            script = generar_script(tanda, i, pausa, variacion, int(corte_403))
            st.markdown(f'<div class="script-box">{script}</div>', unsafe_allow_html=True)

            import json as _json
            script_json = _json.dumps(script)
            st.components.v1.html(f'''
            <script>var scriptContent_{i} = {script_json};</script>
            <button id="cb{i}" onclick="
                navigator.clipboard.writeText(scriptContent_{i}).then(function() {{
                    var b = document.getElementById(\'cb{i}\');
                    b.innerText = \'✅ Copiado\';
                    b.style.color = \'#4caf50\';
                    b.style.borderColor = \'#4caf50\';
                    setTimeout(function() {{
                        b.innerText = \'📋 Copiar script Tanda {i+1}\';
                        b.style.color = \'#4fc3f7\';
                        b.style.borderColor = \'#4fc3f7\';
                    }}, 2500);
                }});
            " style="background:transparent;border:2px solid #4fc3f7;color:#4fc3f7;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px;">
                📋 Copiar script Tanda {i+1}
            </button>
            ''', height=60)

    # ════════════════════════════════════════════════════════════════════════
    # PASO 3 — CONSOLIDAR
    # ════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown('<div class="step-header">📊 Paso 3 — Consolidar resultados</div>', unsafe_allow_html=True)

    st.markdown('''
    <div class="instruccion">
    1. Descargá los CSV que generó el script en cada tanda<br>
    2. Subílos acá todos juntos (podés seleccionar varios a la vez)<br>
    3. La app consolida el resultado y lo cruza con tu listado original<br>
    4. Si quedaron códigos <strong>sin consultar o bloqueados (403)</strong>, aparece automáticamente un <strong>script de recuperación</strong> — lo corrés en CAT y volvés a subir el CSV resultante acá
    </div>
    ''', unsafe_allow_html=True)

    csvs = st.file_uploader(
        "Subí los CSV descargados por el navegador (podés seleccionar varios a la vez)",
        type=["csv"],
        accept_multiple_files=True,
        key="csvs_resultado"
    )

    if csvs:
        frames = []
        for f in csvs:
            try:
                frames.append(pd.read_csv(f, sep=';'))
            except Exception as e:
                st.warning(f"No se pudo leer {f.name}: {e}")

        if frames:
            df_res = pd.concat(frames, ignore_index=True)
            df_res.columns = [c.lower().strip() for c in df_res.columns]

            mapa = {}
            for _, row in df_res.iterrows():
                cod = str(row.get('codigo', '')).strip()
                if cod:
                    mapa[cod] = {
                        'estado':      row.get('estado', ''),
                        'descripcion': row.get('descripcion', ''),
                        'url':         row.get('url', '')
                    }

            filas = []
            for raw in st.session_state.codigos_raw:
                norm = normalizar(raw)
                res  = mapa.get(norm, {})
                filas.append({
                    'Código original':    raw,
                    'Código normalizado': norm or raw,
                    'Estado':             res.get('estado', 'no consultado'),
                    'Descripción':        res.get('descripcion', ''),
                    'URL':                res.get('url', armar_url(norm) if norm else '')
                })

            df_final = pd.DataFrame(filas)

            ok      = (df_final['Estado'] == 'ok').sum()
            no_enc  = (df_final['Estado'] == '404').sum()
            bloq    = (df_final['Estado'] == '403').sum()
            no_cons = (df_final['Estado'] == 'no consultado').sum()

            r1, r2, r3, r4 = st.columns(4)
            r1.metric("✅ Encontrados",          ok)
            r2.metric("❌ No encontrados (404)", no_enc)
            r3.metric("🚫 Bloqueados (403)",     bloq)
            r4.metric("⏳ Sin consultar",         no_cons)

            st.dataframe(df_final, use_container_width=True, hide_index=True)

            col_csv, col_xlsx = st.columns(2)
            with col_csv:
                st.download_button(
                    label="⬇️ Exportar CSV final",
                    data=df_final.to_csv(index=False).encode('utf-8'),
                    file_name="cat_resultado_final.csv",
                    mime="text/csv"
                )
            with col_xlsx:
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    df_final.to_excel(writer, index=False, sheet_name='Resultado CAT')
                st.download_button(
                    label="⬇️ Exportar Excel final",
                    data=buf.getvalue(),
                    file_name="cat_resultado_final.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

            # ── Recuperar faltantes ──────────────────────────────────────
            faltantes = df_final[
                df_final['Estado'].isin(['no consultado', '403'])
            ]['Código normalizado'].dropna().unique().tolist()

            if faltantes:
                st.divider()
                st.markdown('<div class="step-header">🔄 Recuperar códigos faltantes</div>', unsafe_allow_html=True)
                st.markdown(f'''
                <div class="instruccion">
                Hay <strong>{len(faltantes)} códigos</strong> sin consultar o bloqueados (403).<br>
                Generá el script de recuperación, pegálo en la consola de CAT y después subí el CSV resultante nuevamente al Paso 3.
                </div>
                ''', unsafe_allow_html=True)

                c1r, c2r, c3r, c4r = st.columns(4)
                tam_rec   = c1r.number_input("Códigos por tanda", min_value=10, max_value=200, value=min(80, len(faltantes)), step=10, key="rec_tam")
                pausa_rec = c2r.number_input("Pausa (seg)", min_value=2.0, max_value=30.0, value=6.0, step=0.5, key="rec_pausa")
                var_rec   = c3r.number_input("Variación (±seg)", min_value=0.0, max_value=10.0, value=2.0, step=0.5, key="rec_var")
                corte_rec = c4r.number_input("Corte por 403", min_value=1, max_value=10, value=3, key="rec_corte")

                tandas_rec = [faltantes[i:i+int(tam_rec)] for i in range(0, len(faltantes), int(tam_rec))]
                st.markdown(f"**{len(faltantes)} códigos faltantes · {len(tandas_rec)} tanda(s) de recuperación**")

                tabs_rec = st.tabs([f"Recuperación {i+1} ({len(t)} cód.)" for i, t in enumerate(tandas_rec)])

                for i, (tab_r, tanda_r) in enumerate(zip(tabs_rec, tandas_rec)):
                    with tab_r:
                        t_min_r = int(len(tanda_r) * max(pausa_rec - var_rec, 1))
                        t_max_r = int(len(tanda_r) * (pausa_rec + var_rec))
                        st.markdown(
                            f'<div class="tanda-info">📦 {len(tanda_r)} códigos · ⏱ {t_min_r}–{t_max_r} seg</div>',
                            unsafe_allow_html=True
                        )
                        script_rec = generar_script(tanda_r, i, pausa_rec, var_rec, int(corte_rec))
                        st.markdown(f'<div class="script-box">{script_rec}</div>', unsafe_allow_html=True)
                        import json as _json
                        script_rec_json = _json.dumps(script_rec)
                        st.components.v1.html(f'''
                        <script>var recScript_{i} = {script_rec_json};</script>
                        <button id="reccb{i}" onclick="
                            navigator.clipboard.writeText(recScript_{i}).then(function() {{
                                var b = document.getElementById(\'reccb{i}\');
                                b.innerText = \'✅ Copiado\';
                                b.style.color = \'#4caf50\';
                                b.style.borderColor = \'#4caf50\';
                                setTimeout(function() {{
                                    b.innerText = \'📋 Copiar script Recuperación {i+1}\';
                                    b.style.color = \'#4fc3f7\';
                                    b.style.borderColor = \'#4fc3f7\';
                                }}, 2500);
                            }});
                        " style="background:transparent;border:2px solid #4fc3f7;color:#4fc3f7;padding:10px 24px;border-radius:8px;font-size:14px;font-weight:600;cursor:pointer;margin-top:8px;">
                            📋 Copiar script Recuperación {i+1}
                        </button>
                        ''', height=60)

st.markdown('<div class="footer">Interlog Comercio Exterior · consulta-catalogo-cat · Grupo 8</div>',
            unsafe_allow_html=True)
