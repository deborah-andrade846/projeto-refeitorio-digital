import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# 1. CONFIGURAÇÃO DA LIGAÇÃO
st.set_page_config(page_title="Totem Digital", layout="centered")

# Cria a ligação com o Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Função para ler os dados existentes
def get_data():
    return conn.read(worksheet="Folha1", usecols=[0,1,2,3,4])

st.title("🚀 Registo Digital - Refeitório")

# 2. INTERFACE
lista_nomes = ["DÉBORAH SILVA", "EMANOEL SANTOS", "JOÃO PEDRO", "MARIA SOUZA", "OUTRO..."]
nome_selecionado = st.selectbox("NOME DO COLABORADOR:", lista_nomes, index=None)

if nome_selecionado:
    st.write(f"### Olá, **{nome_selecionado}**!")
    
    col1, col2, col3, col4 = st.columns(4)
    registro_tipo = None
    volume = "N/A"

    with col1:
        if st.button("☕\nCAFÉ", use_container_width=True):
            st.session_state.tipo = "CAFÉ"
    with col2:
        if st.button("🍵\nCHÁ", use_container_width=True):
            st.session_state.tipo = "CHÁ"
    with col3:
        if st.button("🍱\nMARMITA", use_container_width=True):
            st.session_state.tipo = "MARMITA"
    with col4:
        if st.button("🍽️\nALMOÇO", use_container_width=True):
            st.session_state.tipo = "ALMOÇO"

    if 'tipo' in st.session_state:
        tipo = st.session_state.tipo
        if tipo in ["CAFÉ", "CHÁ"]:
            st.warning(f"Quantos litros de {tipo}?")
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("0.5 L"): volume = "0.5"
            if c2.button("1.0 L"): volume = "1.0"
            if c3.button("1.5 L"): volume = "1.5"
            if c4.button("2.0 L"): volume = "2.0"
            
            if volume != "N/A":
                registro_tipo = tipo
        else:
            registro_tipo = tipo

    # 3. GRAVAR NO GOOGLE SHEETS
    if registro_tipo:
        # Lê os dados atuais
        df_atual = get_data()
        
        # Cria a nova linha
        agora = datetime.now()
        nova_linha = pd.DataFrame([{
            "DATA": agora.strftime("%d/%m/%Y"),
            "HORA": agora.strftime("%H:%M:%S"),
            "COLABORADOR": nome_selecionado,
            "TIPO": registro_tipo,
            "LITROS": volume
        }])
        
        # Junta os dados novos aos antigos
        df_final = pd.concat([df_atual, nova_linha], ignore_index=True)
        
        # Atualiza a Google Sheet
        conn.update(worksheet="Folha1", data=df_final)
        
        st.success(f"Registo enviado para a nuvem: {registro_tipo}")
        del st.session_state.tipo
        st.balloons()
