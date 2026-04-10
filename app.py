import streamlit as st
from supabase import create_client, Client
from datetime import datetime

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

# 2. CONECTANDO AO BANCO DE DADOS SUPABASE
@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erro ao conectar no banco de dados. Verifique os Secrets.")

st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

# 3. INTERFACE
lista_nomes = ["DÉBORAH SILVA", "EMANOEL SANTOS", "JOÃO PEDRO", "MARIA SOUZA", "OUTRO..."]
nome_selecionado = st.selectbox("NOME DO COLABORADOR:", lista_nomes, index=None)

if nome_selecionado:
    st.write(f"### Olá, **{nome_selecionado}**!")
    col1, col2, col3, col4 = st.columns(4)
    
    registro_tipo = None
    volume = "N/A"

    with col1:
        if st.button("☕\nCAFÉ"): st.session_state.tipo = "CAFÉ"
    with col2:
        if st.button("🍵\nCHÁ"): st.session_state.tipo = "CHÁ"
    with col3:
        if st.button("🍱\nMARMITA"): st.session_state.tipo = "MARMITA"
    with col4:
        if st.button("🍽️\nALMOÇO"): st.session_state.tipo = "ALMOÇO"

    if 'tipo' in st.session_state:
        tipo = st.session_state.tipo
        if tipo in ["CAFÉ", "CHÁ"]:
            st.info(f"Quantidade de {tipo}:")
            v_col1, v_col2, v_col3 = st.columns(3)
            if v_col1.button("1.0 L"): volume = "1.0"
            if v_col2.button("1.5 L"): volume = "1.5"
            if v_col3.button("2.0 L"): volume = "2.0"
            if volume != "N/A": registro_tipo = tipo
        else:
            registro_tipo = tipo

    # 4. SALVANDO NO BANCO DE DADOS
    if registro_tipo:
        try:
            novo_registro = {
                "data": datetime.now().strftime("%d/%m/%Y"),
                "hora": datetime.now().strftime("%H:%M:%S"),
                "colaborador": nome_selecionado,
                "tipo": registro_tipo,
                "litros": volume
            }
            
            # Comando mágico que envia para o Supabase
            supabase.table("registros").insert(novo_registro).execute()
            
            st.success("✅ Registrado com sucesso!")
            st.balloons()
            
            if 'tipo' in st.session_state:
                del st.session_state.tipo
                
        except Exception as e:
            st.error(f"Erro ao salvar no banco: {e}")
