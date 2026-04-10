import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

# Conectando à planilha (sem comandos, apenas via configuração do site)
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("Erro na conexão. Verifique os 'Secrets' no painel do Streamlit.")

st.title("🚀 Registro Digital - Refeitório")

# Interface simplificada
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

    if registro_tipo:
        try:
            # 1. DIGITE AQUI O NOME DA ABA QUE ESTÁ LÁ NO RODAPÉ DA PLANILHA
            nome_aba = "datetime.now().strftime("%B_%Y")" 

            try:
                # Tentamos ler a aba. Se der erro (aba vazia), ele cria o cabeçalho
                df_existente = conn.read(worksheet=nome_aba)
            except:
                df_existente = pd.DataFrame(columns=["DATA", "HORA", "COLABORADOR", "TIPO", "LITROS"])

            novo_dado = pd.DataFrame([{
                "DATA": datetime.now().strftime("%d/%m/%Y"),
                "HORA": datetime.now().strftime("%H:%M:%S"),
                "COLABORADOR": nome_selecionado,
                "TIPO": registro_tipo,
                "LITROS": volume
            }])

            # Limpa linhas vazias que o Google Sheets às vezes traz
            df_existente = df_existente.dropna(how='all')

            df_final = pd.concat([df_existente, novo_dado], ignore_index=True)
            
            # 2. AQUI TAMBÉM PRECISA DO NOME DA ABA
            conn.update(worksheet=nome_aba, data=df_final) 
            
            st.success("✅ Registrado com sucesso!")
            st.balloons()
            # Limpa o estado para o próximo colega usar
            if 'tipo' in st.session_state:
                del st.session_state.tipo
                
        except Exception as e:
            st.error(f"Erro técnico: {e}")
