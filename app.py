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

# ─── Estilos ────────────────────────────────────────────────────────────────
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
    .step-header {
        background: #1e2a35;
        border-left: 4px solid #4fc3f7;
        padding: 0.6rem 1rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 1rem;
        font-weight: 600;
        font-size: 1rem;
        color: #e0f2fe;
    }
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

# ─── Header ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-box">
    <h1>🔧 Consulta Catálogo CAT</h1>
    <p>Interlog Comercio Exterior · Consulta masiva de descripciones en parts.cat.com · Sin instalar nada</p>
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
        const titulo = doc.querySelector('h1')?.textContent?.trim() || '';
        const meta = doc.querySelector('meta[name="description"]')?.content || '';
        const og = doc.querySelector('meta[property="og:title"]')?.content || '';
        const descripcion = titulo || og || meta || '';
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

  const csv = ['codigo,url,estado,descripcion'].concat(
    resultados.map(r => [r.codigo, r.url, r.estado, '"' + r.descripcion.replace(/"/g, '""') + '"'].join(','))
  ).join('\\n');

  const blob = new Blob([csv], {{ type: 'text/csv' }});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'cat_tanda_{idx+1}.csv';
  a.click();
  console.log('\\n✅ Tanda {idx+1} completa. CSV descargado.');
}})();"""

# ─── Session state ──────────────────────────────────────────────────────────
for key, val in [('codigos_raw', []), ('unicos', []), ('tandas', []), ('tandas_done', set())]:
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

# ════════════════════════════════════════════════════════════════════════════
# PROCESAMIENTO + CONFIGURACIÓN
# ════════════════════════════════════════════════════════════════════════════
if codigos_raw:
    st.divider()
    st.markdown('<div class="step-header">⚙️ Configuración</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    tam_tanda  = c1.number_input("Códigos por tanda",        min_value=10,  max_value=300, value=100, step=10)
    pausa      = c2.number_input("Pausa entre requests (s)", min_value=2.0, max_value=30.0, value=5.0, step=0.5)
    variacion  = c3.number_input("Variación aleatoria (±s)", min_value=0.0, max_value=10.0, value=2.0, step=0.5)
    corte_403  = c4.number_input("Corte por 403 seguidos",   min_value=1,   max_value=10,  value=3)

    # Normalizar y deduplicar
    unicos_dict = {}
    for r in codigos_raw:
        n = normalizar(r)
        if n and n not in unicos_dict:
            unicos_dict[n] = True
    unicos = list(unicos_dict.keys())
    repetidos = len(codigos_raw) - len(unicos)
    tandas = [unicos[i:i+int(tam_tanda)] for i in range(0, len(unicos), int(tam_tanda))]

    st.session_state.codigos_raw = codigos_raw
    st.session_state.unicos      = unicos
    st.session_state.tandas      = tandas

    # Métricas
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
    <strong>Instrucciones:</strong><br>
    1. Abrí <strong>parts.cat.com</strong> en tu navegador corporativo (cualquier página del sitio)<br>
    2. Presioná <strong>F12</strong> → hacé click en la pestaña <strong>Console</strong><br>
    3. Copiá el script de la tanda y pegalo → presioná <strong>Enter</strong><br>
    4. Esperá que termine — se descarga un CSV automáticamente<br>
    5. Repetí para cada tanda y volvé al Paso 3 para consolidar
    </div>
    """, unsafe_allow_html=True)

    tabs = st.tabs([f"Tanda {i+1}  ({len(t)} códigos)" for i, t in enumerate(tandas)])

    for i, (tab, tanda) in enumerate(zip(tabs, tandas)):
        with tab:
            t_min = int(len(tanda) * max(pausa - variacion, 1))
            t_max = int(len(tanda) * (pausa + variacion))
            done  = i in st.session_state.tandas_done

            col_a, col_b = st.columns([4, 1])
            col_a.markdown(f"**{len(tanda)} códigos únicos** · Tiempo estimado: {t_min}–{t_max} seg")
            if done:
                col_b.success("✅ Completada")
            else:
                if col_b.button("Marcar hecha ✓", key=f"done_{i}"):
                    st.session_state.tandas_done.add(i)
                    st.rerun()

            script = generar_script(tanda, i, pausa, variacion, int(corte_403))
            st.markdown(f'<div class="script-box">{script}</div>', unsafe_allow_html=True)

            st.download_button(
                label="⬇️ Descargar script (.txt)",
                data=script,
                file_name=f"cat_script_tanda_{i+1}.txt",
                mime="text/plain",
                key=f"dl_{i}"
            )

    # ════════════════════════════════════════════════════════════════════════
    # PASO 3 — CONSOLIDAR
    # ════════════════════════════════════════════════════════════════════════
    st.divider()
    st.markdown('<div class="step-header">📊 Paso 3 — Consolidar resultados</div>', unsafe_allow_html=True)

    csvs = st.file_uploader(
        "Subí los CSV descargados por el navegador (podés seleccionar varios a la vez)",
        type=["csv"],
        accept_multiple_files=True,
        key="csvs"
    )

    if csvs:
        frames = []
        for f in csvs:
            try:
                frames.append(pd.read_csv(f))
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
                    'Código original':   raw,
                    'Código normalizado': norm or raw,
                    'Estado':            res.get('estado', 'no consultado'),
                    'Descripción':       res.get('descripcion', ''),
                    'URL':               res.get('url', armar_url(norm) if norm else '')
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

st.markdown('<div class="footer">Interlog Comercio Exterior · consulta-catalogo-cat · Grupo 8</div>',
            unsafe_allow_html=True)
