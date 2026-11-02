"""BeautyPulse Premium: Streamlit + MongoDB Atlas, CRUD y cinco gráficos."""

import base64
import binascii
import hmac
import html
import io
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, UnidentifiedImageError
from pymongo import MongoClient, ReturnDocument
from pymongo.errors import DuplicateKeyError, PyMongoError

# =====================================================
# 1. CONFIGURACIÓN Y ESTILO BEAUTY
# =====================================================
st.set_page_config(
    page_title="BeautyPulse Premium", page_icon="💄",
    layout="wide", initial_sidebar_state="expanded"
)

st.markdown("""
<style>
.stApp {background:linear-gradient(120deg,#faeded,#fffafa 82%);color:#34252a}
section[data-testid="stSidebar"] {
    background:linear-gradient(180deg,#f5dddd,#fcf5f3);
    border-right:1px solid #ecd6d8;
}
h1,h2,h3 {color:#342329}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:18px}
.stButton>button[kind="primary"], [data-testid="stFormSubmitButton"] button {
    border-radius:11px;background:#c88c92;border:1px solid #c88c92;
    color:white;font-weight:650;
}
.stButton>button[kind="primary"]:hover,
[data-testid="stFormSubmitButton"] button:hover {
    background:#ac717b;border-color:#ac717b;color:white;
}
.bp-banner {background:linear-gradient(100deg,#f3d9db,#fff5f3);
    border:1px solid #ead0d3;border-radius:19px;padding:20px 26px;margin-bottom:14px}
.bp-banner h1 {margin:0;font-size:2.15rem}
.bp-banner p {margin:6px 0 0;color:#785963}
.bp-kpi {background:#fff;border:1px solid #e9d5d9;border-radius:16px;
    padding:17px;min-height:115px;box-shadow:0 5px 19px #95646b12}
.bp-kpi-label {color:#866b72;font-size:.87rem}
.bp-kpi-value {color:#33232a;font-size:1.85rem;font-weight:760;margin-top:7px}
.bp-title {font-size:1.12rem;font-weight:760;color:#312329}
.bp-sub {font-size:.87rem;color:#856a74;margin:5px 0 9px}
.bp-pill {display:inline-block;border-radius:999px;padding:4px 10px;
    font-size:.75rem;font-weight:650;margin:2px 4px 8px 0}
.bp-blue {background:#e3f0f6;color:#4e7186}
.bp-pink {background:#f7dce4;color:#a25472}
.bp-gold {background:#f7ebcc;color:#8d6818}
.bp-stat {font-size:.91rem;color:#402d34;font-weight:650}
.bp-stat-small {color:#89747b;font-size:.75rem}
/* ÚNICA ACCIÓN EN LAS TARJETAS */
.bp-detalles {position:relative;display:block;text-align:center;
    background:linear-gradient(90deg,#ca969d,#b9808b);border:1px solid #bb858f;
    border-radius:11px;padding:12px 10px;color:white;font-weight:700;
    cursor:help;outline-offset:3px}
.bp-detalles:hover,.bp-detalles:focus-visible {background:#af7580}
.bp-tooltip {position:absolute;z-index:99999;right:0;bottom:calc(100% + 12px);
    width:300px;max-width:75vw;padding:14px 16px;background:white;
    border:1px solid #e2c7cf;border-radius:13px;color:#533d46;
    box-shadow:0 12px 28px #58344236;text-align:left;
    font-size:.88rem;font-weight:400;line-height:1.55;overflow-wrap:anywhere;
    opacity:0;visibility:hidden;pointer-events:none;transform:translateY(5px);
    transition:opacity .15s,transform .15s}
.bp-tooltip strong {display:block;color:#a66b7c;margin-bottom:5px}
.bp-detalles:hover .bp-tooltip,.bp-detalles:focus-visible .bp-tooltip {
    opacity:1;visibility:visible;transform:translateY(0)}
/* Tarjetas compactas de tendencias en el Dashboard */
.bp-mini-title {font-size:.93rem;font-weight:720;color:#35252c;line-height:1.2;margin:0 0 3px}
.bp-mini-meta {font-size:.76rem;color:#8b6c74;margin:0 0 4px}
.bp-mini-stats {font-size:.76rem;color:#705159;margin-top:4px}
.bp-mini-detail {position:relative;display:block;padding:8px 5px;
    background:#f8e4e7;color:#8b5261;border:1px solid #edcfd5;
    border-radius:9px;text-align:center;font-size:.75rem;font-weight:700;
    cursor:help;outline-offset:3px}
.bp-mini-detail:hover,.bp-mini-detail:focus-visible {background:#eccdd5}
.bp-mini-detail .bp-tooltip {bottom:calc(100% + 9px);width:260px}
/* Dejar visible la ventana flotante fuera del borde de la tarjeta */
[data-testid="stVerticalBlockBorderWrapper"]:has(.bp-detalles) {overflow:visible !important}
</style>
""", unsafe_allow_html=True)

PLATAFORMAS = ["TikTok", "Instagram", "Pinterest", "YouTube", "Facebook", "Otras"]
CATEGORIAS = ["Maquillaje", "Skincare", "Cabello", "Uñas", "Accesorios", "Otros"]
ESTADOS = ["En tendencia", "En observación", "Archivada"]
COLORES = ["#c58d9c", "#e2b3b6", "#e8c7a5", "#a9bdbc", "#a698c2", "#795b76"]
# =====================================================
# 2. ACCESO Y CONEXIÓN CON MONGODB ATLAS
# =====================================================
try:
    MONGO_URI = st.secrets["MONGO_URI"]
    APP_PASSWORD = st.secrets["APP_PASSWORD"]
except (KeyError, FileNotFoundError):
    st.error("Configura MONGO_URI y APP_PASSWORD en .streamlit/secrets.toml")
    st.stop()

if not st.session_state.get("autorizado", False):
    st.title("💄 BeautyPulse")
    st.write("Ingresa para acceder al panel de tendencias beauty.")
    with st.form("form_login"):
        clave = st.text_input("Contraseña de BeautyPulse", type="password")
        entrar = st.form_submit_button("Ingresar")
    if entrar:
        if hmac.compare_digest(clave, APP_PASSWORD):
            st.session_state["autorizado"] = True
            st.rerun()
        else:
            st.error("Contraseña incorrecta")
    st.stop()

@st.cache_resource(show_spinner=False)
def conectar(uri):
    cliente = MongoClient(uri, serverSelectionTimeoutMS=8000)
    cliente.admin.command("ping")
    return cliente

try:
    cliente = conectar(MONGO_URI)
    db = cliente["beautypulse_db"]
    coleccion = db["tendencias"]
    contadores = db["contadores"]
    coleccion.create_index("codigo", unique=True)
except PyMongoError:
    st.error("No se pudo conectar con MongoDB Atlas. Revisa la URI, permisos y acceso de red.")
    st.stop()


def obtener_registros(filtro=None):
    consulta = filtro or {}
    return list(coleccion.find(consulta).sort("fecha_registro", -1))


def url_valida(url):
    if not url:
        return False
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return False
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def resolver_imagen(doc):
    imagen_b64 = doc.get("imagen_base64")
    if imagen_b64:
        try:
            pixeles = base64.b64decode(imagen_b64)
            return Image.open(io.BytesIO(pixeles))
        except (ValueError, TypeError, OSError, UnidentifiedImageError):
            pass
    url = str(doc.get("imagen_url") or "").strip()
    return url if url and url_valida(url) else None


def indice(lista, valor):
    try:
        return lista.index(valor) if valor in lista else 0
    except ValueError:
        return 0


def generar_codigo():
    ultimo = contadores.find_one_and_update(
        {"_id": "codigo_tendencia"},
        {"$inc": {"valor": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    numero = int((ultimo or {}).get("valor", 1))
    return f"BP-{numero:03d}"


def comprimir_imagen(archivo):
    if archivo is None:
        return None
    try:
        archivo.seek(0)
        imagen = Image.open(archivo)
        imagen = imagen.convert("RGB")
        buffer = io.BytesIO()
        imagen.save(buffer, format="JPEG", quality=80, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except (UnidentifiedImageError, ValueError, OSError):
        raise ValueError("La imagen no es válida o no se pudo procesar.")


def estilo_figura(fig, altura, donut=False):
    fig.update_layout(
        height=altura,
        template="plotly_white",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=20, b=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    if donut:
        fig.update_traces(textinfo="percent+label", insidetextorientation="radial")
    return fig


def cambiar_pagina(pagina):
    # Callback del botón: se ejecuta antes de que Streamlit cree el menú radio.
    st.session_state["menu"] = pagina


def tarjeta_producto(doc):
    """Una sola acción visible: Ver detalles por hover/foco."""
    codigo = str(doc.get("codigo", ""))
    producto = str(doc.get("producto", "Sin nombre"))
    marca = str(doc.get("marca", "Sin marca"))
    categoria = str(doc.get("categoria", "Otros"))
    plataforma = str(doc.get("plataforma", "Otras"))
    estado = str(doc.get("estado", "En observación"))
    detalle = str(doc.get("descripcion") or doc.get("observaciones") or "Sin descripción registrada.")
    detalle_seguro = html.escape(detalle).replace("\n", "<br>")
    imagen = resolver_imagen(doc)

    with st.container(border=True):
        foto, info, accion = st.columns([1.1, 3.0, 1.2], gap="medium")
        with foto:
            if imagen is None:
                st.caption("📷 Sin imagen")
            else:
                st.image(imagen, use_container_width=True)
        with info:
            st.markdown(
                f'<div class="bp-title">{html.escape(producto)}</div>'
                f'<div class="bp-sub">{html.escape(marca)} · '
                f'{html.escape(plataforma)} · {html.escape(codigo)}</div>'
                f'<span class="bp-pill bp-blue">{html.escape(categoria)}</span>'
                f'<span class="bp-pill bp-pink">{html.escape(plataforma)}</span>'
                f'<span class="bp-pill bp-gold">{html.escape(estado)}</span>',
                unsafe_allow_html=True
            )
            a, b, c = st.columns(3)
            for columna, icono, etiqueta, campo in [
                (a, "👁️", "Visualizaciones", "visualizaciones"),
                (b, "❤️", "Likes", "likes"),
                (c, "🔖", "Guardados", "guardados"),
            ]:
                cantidad = int(doc.get(campo) or 0)
                with columna:
                    st.markdown(
                        f'<div class="bp-stat">{icono} {cantidad:,}</div>'
                        f'<div class="bp-stat-small">{etiqueta}</div>',
                        unsafe_allow_html=True
                    )
        with accion:
            st.caption("Acción")
            st.markdown(
                '<div class="bp-detalles" tabindex="0" role="note">'
                '🔎 Ver detalles'
                '<div class="bp-tooltip">'
                '<strong>💄 Descripción del producto</strong>'
                + detalle_seguro +
                '</div></div>', unsafe_allow_html=True
            )


def tarjeta_producto_compacta(doc):
    """Vista corta para el dashboard: imagen, datos y tooltip al pasar el cursor."""
    producto = html.escape(str(doc.get("producto") or "Sin nombre"))
    marca = html.escape(str(doc.get("marca") or "Sin marca"))
    codigo = html.escape(str(doc.get("codigo") or ""))
    red = html.escape(str(doc.get("plataforma") or ""))
    detalle = str(doc.get("descripcion") or doc.get("observaciones") or "Sin descripción registrada.")
    detalle_titulo = html.escape(detalle, quote=True)
    detalle = html.escape(detalle).replace("\n", "<br>")
    imagen = resolver_imagen(doc)
    vistas = int(doc.get("visualizaciones") or 0)
    likes = int(doc.get("likes") or 0)

    with st.container(border=True):
        foto, info, accion = st.columns([0.85, 3.3, 1.45], gap="small", vertical_alignment="center")
        with foto:
            if imagen is not None:
                st.image(imagen, width=66)
            else:
                st.caption("📷")
        with info:
            st.markdown(
                f'<div class="bp-mini-title">{producto}</div>'
                f'<div class="bp-mini-meta">{marca} · {red} · {codigo}</div>'
                f'<div class="bp-mini-stats">👁️ {vistas:,} &nbsp; ❤️ {likes:,}</div>',
                unsafe_allow_html=True
            )
        with accion:
            st.markdown(
                f'<div class="bp-mini-detail" tabindex="0" title="{detalle_titulo}">🔎 Ver detalles'
                '<div class="bp-tooltip"><strong>Descripción del producto</strong>'
                + detalle + '</div></div>',
                unsafe_allow_html=True
            )


def tabla_productos(documentos):
    columnas = {
        "codigo": "Código", "producto": "Producto", "marca": "Marca",
        "categoria": "Categoría", "plataforma": "Plataforma", "estado": "Estado",
        "visualizaciones": "Visualizaciones", "likes": "Likes", "guardados": "Guardados",
    }
    filas = [{etiqueta: d.get(clave, "") for clave, etiqueta in columnas.items()} for d in documentos]
    st.dataframe(pd.DataFrame(filas, columns=list(columnas.values())),
                 hide_index=True, use_container_width=True)

def dashboard_graficos(documentos):
    """Cuadrícula 2x3: 5 gráficos y una lista compacta de tendencias."""
    if not documentos:
        st.info("Registra productos para visualizar gráficos y tendencias.")
        return

    df = pd.DataFrame([{
        "codigo": str(d.get("codigo") or ""),
        "producto": str(d.get("producto") or "Sin nombre"),
        "plataforma": str(d.get("plataforma") or "Otras"),
        "categoria": str(d.get("categoria") or "Otros"),
        "estado": str(d.get("estado") or "Sin estado"),
        "visualizaciones": int(d.get("visualizaciones") or 0),
        "likes": int(d.get("likes") or 0),
        "guardados": int(d.get("guardados") or 0),
    } for d in documentos])

    # Fila 1: plataformas + tendencias compactas
    izq, der = st.columns(2, gap="medium")
    with izq:
        with st.container(border=True):
            st.markdown("**🍩 Distribución por plataforma**")
            conteo = df["plataforma"].value_counts()
            fig = go.Figure(go.Pie(
                labels=conteo.index.tolist(),
                values=conteo.values.tolist(),
                hole=0.62, marker=dict(colors=COLORES),
                textinfo="percent"
            ))
            st.plotly_chart(estilo_figura(fig, 303, True), use_container_width=True,
                            key="grafico_plataformas")
    with der:
        with st.container(border=True):
            st.markdown("**💄 Tendencias de Belleza Activas**")
            activos = [d for d in documentos if d.get("estado") != "Archivada"]
            with st.container(height=313, border=False):
                if not activos:
                    st.info("No hay tendencias activas.")
                for doc in activos:
                    tarjeta_producto_compacta(doc)

    # Fila 2: top 5 + interacciones
    izq, der = st.columns(2, gap="medium")
    with izq:
        with st.container(border=True):
            st.markdown("**🏆 Top 5 productos por visualizaciones**")
            top = df.nlargest(5, "visualizaciones").copy()
            # Etiqueta corta: al pasar el cursor se ve el nombre completo
            top["etiqueta"] = top["codigo"] + " · " + top["producto"].str.slice(0, 20)
            top = top.sort_values("visualizaciones")
            fig = go.Figure(go.Bar(
                x=top["visualizaciones"], y=top["etiqueta"], orientation="h",
                marker_color="#c58c98",
                customdata=top["producto"],
                hovertemplate="%{customdata}<br>%{x:,} visualizaciones<extra></extra>"
            ))
            fig.update_layout(xaxis_title="Visualizaciones", yaxis_title=None)
            st.plotly_chart(estilo_figura(fig, 303), use_container_width=True,
                            key="top_5")
    with der:
        with st.container(border=True):
            st.markdown("**❤️ Likes y guardados por red social**")
            totales = df.groupby("plataforma", as_index=False)[["likes", "guardados"]].sum()
            fig = go.Figure()
            fig.add_bar(x=totales["plataforma"], y=totales["likes"],
                        name="Likes", marker_color="#c88795")
            fig.add_bar(x=totales["plataforma"], y=totales["guardados"],
                        name="Guardados", marker_color="#e3baa8")
            fig.update_layout(barmode="group", xaxis_title=None, yaxis_title="Interacciones")
            st.plotly_chart(estilo_figura(fig, 303), use_container_width=True,
                            key="likes_guardados")

    # Fila 3: estado + categorías
    izq, der = st.columns(2, gap="medium")
    with izq:
        with st.container(border=True):
            st.markdown("**🌸 Estado de las tendencias**")
            conteo = df["estado"].value_counts()
            fig = go.Figure(go.Pie(
                labels=conteo.index.tolist(), values=conteo.values.tolist(),
                hole=0.62, marker=dict(colors=COLORES), textinfo="percent"
            ))
            st.plotly_chart(estilo_figura(fig, 303, True), use_container_width=True,
                            key="estados_tendencias")
    with der:
        with st.container(border=True):
            st.markdown("**💄 Productos por categoría beauty**")
            conteo = df["categoria"].value_counts()
            fig = go.Figure(go.Bar(
                x=conteo.index.tolist(), y=conteo.values.tolist(),
                marker_color="#d3a4b6", text=conteo.values.tolist(),
                textposition="outside"
            ))
            fig.update_layout(xaxis_title=None, yaxis_title="Cantidad de productos")
            st.plotly_chart(estilo_figura(fig, 303), use_container_width=True,
                            key="categorias_productos")

    st.caption("Los gráficos usan los datos guardados en MongoDB Atlas. "
               "Las métricas iniciales son ficticias para la actividad académica.")
# =====================================================
# 5. MENÚ Y ENCABEZADO
# =====================================================
with st.sidebar:
    st.title("💄 BeautyPulse")
    st.caption("Sistema de gestión de tendencias beauty")
    st.success("MongoDB Atlas conectado")
    if st.button("Cerrar sesión"):
        st.session_state["autorizado"] = False
        st.rerun()
    menu = st.radio("Menú", ["Dashboard", "Registrar", "Consultar", "Actualizar", "Eliminar"],
                    key="menu")

if menu != "Dashboard":
    st.markdown(
        '<div class="bp-banner"><h1>BeautyPulse</h1>'
        '<p>Gestión de tendencias beauty · MongoDB Atlas</p></div>',
        unsafe_allow_html=True
    )
# =====================================================
# 6. DASHBOARD: SOLO GRÁFICOS Y TENDENCIAS COMPACTAS
# =====================================================
if menu == "Dashboard":
    st.header("📊 Dashboard de tendencias BeautyPulse")
    docs = obtener_registros()
    dashboard_graficos(docs)
# =====================================================
# 7. CREATE: REGISTRAR CON CÓDIGO AUTOMÁTICO
# =====================================================
elif menu == "Registrar":
    st.header("Registrar nueva tendencia")
    st.info("El código BP-007, BP-008, BP-009... se genera automáticamente.")
    with st.form("form_registrar", clear_on_submit=True):
        a, b = st.columns(2)
        with a:
            producto = st.text_input("Nombre del producto")
            marca = st.text_input("Marca")
            categoria = st.selectbox("Categoría", CATEGORIAS)
            plataforma = st.selectbox("Red social", PLATAFORMAS)
        with b:
            estado = st.selectbox("Estado", ESTADOS)
            vistas = st.number_input("Visualizaciones", min_value=0, step=1)
            likes = st.number_input("Likes", min_value=0, step=1)
            guardados = st.number_input("Guardados", min_value=0, step=1)
        observaciones = st.text_area("Descripción / observaciones")
        imagen = st.file_uploader("Imagen del producto", type=["jpg", "jpeg", "png", "webp"])
        url = st.text_input("O URL de imagen (opcional)")
        guardar = st.form_submit_button("Guardar producto", type="primary")

    if guardar:
        if not producto.strip() or not marca.strip():
            st.warning("Es obligatorio ingresar el producto y la marca.")
        elif not url_valida(url.strip()):
            st.warning("La URL de imagen debe comenzar por http:// o https://")
        else:
            try:
                imagen_b64 = comprimir_imagen(imagen)
                codigo = generar_codigo()
                coleccion.insert_one({
                    "codigo": codigo, "producto": producto.strip(), "marca": marca.strip(),
                    "categoria": categoria, "plataforma": plataforma, "estado": estado,
                    "visualizaciones": int(vistas), "likes": int(likes), "guardados": int(guardados),
                    "observaciones": observaciones.strip(), "imagen_base64": imagen_b64,
                    "imagen_mime": "image/jpeg" if imagen_b64 else None,
                    "imagen_url": url.strip() if not imagen_b64 else None,
                    "fecha_registro": datetime.now(timezone.utc),
                })
                st.success(f"Producto registrado correctamente con código {codigo}.")
            except ValueError as exc:
                st.error(str(exc))
            except DuplicateKeyError:
                st.error("El código ya existe. Intenta registrar nuevamente.")
            except PyMongoError:
                st.error("No se pudo guardar el producto en MongoDB Atlas.")
# =====================================================
# 8. READ: CONSULTAR Y FILTRAR
# =====================================================
elif menu == "Consultar":
    st.header("Consultar tendencias")
    texto = st.text_input("Buscar por producto, marca o código")
    a, b = st.columns(2)
    with a:
        plataforma = st.selectbox("Red social", ["Todas"] + PLATAFORMAS)
    with b:
        categoria = st.selectbox("Categoría", ["Todas"] + CATEGORIAS)
    condiciones = []
    if texto.strip():
        patron = {"$regex": re.escape(texto.strip()), "$options": "i"}
        condiciones.append({"$or": [
            {"producto": patron}, {"marca": patron}, {"codigo": patron}
        ]})
    if plataforma != "Todas":
        condiciones.append({"plataforma": plataforma})
    if categoria != "Todas":
        condiciones.append({"categoria": categoria})
    filtro = {"$and": condiciones} if condiciones else {}
    docs = obtener_registros(filtro)
    st.caption(f"Resultados encontrados: {len(docs)}")
    tarjetas, tabla = st.tabs(["Tarjetas con imágenes", "Tabla"])
    with tarjetas:
        if docs:
            for d in docs:
                tarjeta_producto(d)
        else:
            st.info("No se encontraron productos.")
    with tabla:
        tabla_productos(docs)
# =====================================================
# 9. UPDATE: ACTUALIZAR PRODUCTOS Y MÉTRICAS
# =====================================================
elif menu == "Actualizar":
    st.header("Actualizar tendencia")
    docs = obtener_registros()
    if not docs:
        st.info("No hay registros para actualizar.")
    else:
        codigo = st.selectbox("Código del producto", [d["codigo"] for d in docs])
        actual = next(d for d in docs if d["codigo"] == codigo)
        imagen_actual = resolver_imagen(actual)
        if imagen_actual is not None:
            st.image(imagen_actual, width=170)
        with st.form(f"form_editar_{codigo}"):
            a, b = st.columns(2)
            with a:
                producto = st.text_input("Producto", value=actual.get("producto", ""))
                marca = st.text_input("Marca", value=actual.get("marca", ""))
                categoria = st.selectbox("Categoría", CATEGORIAS,
                                         index=indice(CATEGORIAS, actual.get("categoria")))
                plataforma = st.selectbox("Red social", PLATAFORMAS,
                                          index=indice(PLATAFORMAS, actual.get("plataforma")))
            with b:
                estado = st.selectbox("Estado", ESTADOS,
                                      index=indice(ESTADOS, actual.get("estado")))
                vistas = st.number_input("Visualizaciones", min_value=0,
                                         value=int(actual.get("visualizaciones") or 0))
                likes = st.number_input("Likes", min_value=0,
                                        value=int(actual.get("likes") or 0))
                guardados = st.number_input("Guardados", min_value=0,
                                            value=int(actual.get("guardados") or 0))
            observaciones = st.text_area("Descripción / observaciones",
                                         value=actual.get("observaciones", ""))
            nueva_imagen = st.file_uploader("Cambiar imagen (opcional)",
                                            type=["jpg", "jpeg", "png", "webp"])
            url = st.text_input("URL de imagen", value=actual.get("imagen_url") or "")
            guardar = st.form_submit_button("Guardar cambios", type="primary")

        if guardar:
            if not producto.strip() or not marca.strip():
                st.warning("El producto y la marca son obligatorios.")
            elif not url_valida(url.strip()):
                st.warning("Introduce una URL http(s) válida.")
            else:
                try:
                    cambios = {
                        "producto": producto.strip(), "marca": marca.strip(),
                        "categoria": categoria, "plataforma": plataforma, "estado": estado,
                        "visualizaciones": int(vistas), "likes": int(likes),
                        "guardados": int(guardados), "observaciones": observaciones.strip(),
                        "fecha_actualizacion": datetime.now(timezone.utc),
                    }
                    if nueva_imagen is not None:
                        cambios["imagen_base64"] = comprimir_imagen(nueva_imagen)
                        cambios["imagen_mime"] = "image/jpeg"
                        cambios["imagen_url"] = None
                    elif url.strip() != str(actual.get("imagen_url") or ""):
                        cambios["imagen_url"] = url.strip() or None
                        if url.strip():
                            cambios["imagen_base64"] = None
                            cambios["imagen_mime"] = None
                    resultado = coleccion.update_one({"codigo": codigo}, {"$set": cambios})
                    if resultado.matched_count:
                        st.success("Producto actualizado correctamente.")
                    else:
                        st.warning("El producto ya no existe.")
                except ValueError as exc:
                    st.error(str(exc))
                except PyMongoError:
                    st.error("No se pudo actualizar el registro.")
# =====================================================
# 10. DELETE: ELIMINAR CON CONFIRMACIÓN
# =====================================================
elif menu == "Eliminar":
    st.header("Eliminar tendencia")
    docs = obtener_registros()
    if not docs:
        st.info("No hay registros para eliminar.")
    else:
        codigo = st.selectbox("Código a eliminar", [d["codigo"] for d in docs])
        actual = next(d for d in docs if d["codigo"] == codigo)
        st.warning(f"Se eliminará {actual.get('producto', '')} ({codigo}).")
        with st.form("form_eliminar"):
            confirmar = st.checkbox("Confirmo que deseo eliminar el registro")
            eliminar = st.form_submit_button("Eliminar definitivamente")
        if eliminar:
            if not confirmar:
                st.warning("Marca la confirmación para eliminar.")
            else:
                try:
                    resultado = coleccion.delete_one({"codigo": codigo})
                    if resultado.deleted_count:
                        st.success("Registro eliminado correctamente de MongoDB Atlas.")
                    else:
                        st.warning("El producto ya no existe.")
                except PyMongoError:
                    st.error("No se pudo eliminar el producto.")