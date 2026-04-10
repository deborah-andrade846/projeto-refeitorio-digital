import streamlit as st
import pandas as pd
import os
from datetime import datetime

# 1. CONFIGURAÇÃO VISUAL
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

st.markdown("""
    <style>
    div.stButton > button {
        height: 100px;
        font-size: 20px !important;
        font-weight: bold;
        border-radius: 15px;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("🚀 Registro de Refeições e Bebidas")

# 2. BASE DE DADOS
lista_nomes = ["DÉBORAH SILVA", "EMANOEL SANTOS", "JOÃO PEDRO", "MARIA SOUZA", "OUTRO..."]
nome_selecionado = st.selectbox("NOME DO COLABORADOR:", lista_nomes, index=None, placeholder="Selecione seu nome...")

if nome_selecionado:
    st.write(f"### Olá, **{nome_selecionado}**!")
    
    # Criando 4 colunas para os botões principais
    col1, col2, col3, col4 = st.columns(4)
    
    registro_tipo = None
    volume = "N/A" # Padrão para marmita/almoço

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

    # 3. LÓGICA DO SELECIONADOR DE LITROS (Aparece apenas para Café ou Chá)
    if 'tipo' in st.session_state:
        tipo = st.session_state.tipo
        
        if tipo in ["CAFÉ", "CHÁ"]:
            st.warning(f"Quantos litros de **{tipo}** você está retirando?")
            
            # Botões de litragem rápida para não precisar digitar
            c1, c2, c3, c4 = st.columns(4)
            if c1.button("0.5 L"): volume = "0.5"
            if c2.button("1.0 L"): volume = "1.0"
            if c3.button("1.5 L"): volume = "1.5"
            if c4.button("2.0 L"): volume = "2.0"
            
            if volume != "N/A":
                registro_tipo = tipo # Ativa o salvamento
        else:
            # Para Marmita e Almoço, o salvamento é imediato após o clique
            registro_tipo = tipo

    # 4. SALVAMENTO DOS DADOS
    if registro_tipo:
        arquivo_dados = "registros_refeitorio.csv"
        agora = datetime.now()
        
        novo_dado = {
            "DATA": agora.strftime("%d/%m/%Y"),
            "HORA": agora.strftime("%H:%M:%S"),
            "COLABORADOR": nome_selecionado,
            "TIPO": registro_tipo,
            "LITROS": volume
        }
        
        df_novo = pd.DataFrame([novo_dado])
        if os.path.exists(arquivo_dados):
            df_novo.to_csv(arquivo_dados, mode='a', index=False, header=False)
        else:
            df_novo.to_csv(arquivo_dados, index=False)

        st.success(f"REGISTRADO: {registro_tipo} ({volume}L)")
        # Limpa o estado para o próximo usuário
        del st.session_state.tipo
        st.balloons()