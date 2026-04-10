import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import uuid # Biblioteca para gerar um código de rastreio único

# 1. CONFIGURAÇÃO VISUAL E SUPABASE (Mantenha sua conexão igual)
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erro ao conectar no banco de dados.")

st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

# 2. INTERFACE DE IDENTIFICAÇÃO
lista_nomes = ["DÉBORAH SILVA", "EMANOEL SANTOS", "JOÃO PEDRO", "MARIA SOUZA", "OUTRO..."]
nome_selecionado = st.selectbox("NOME DO COLABORADOR:", lista_nomes, index=None)

if nome_selecionado:
    
    # Se ainda não escolheu o item, mostra os botões principais
    if 'item_selecionado' not in st.session_state:
        st.write(f"### Olá, **{nome_selecionado}**! O que vai retirar?")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("☕\nCAFÉ", use_container_width=True): st.session_state.item_selecionado = "CAFÉ"
        with col2:
            if st.button("🍵\nCHÁ", use_container_width=True): st.session_state.item_selecionado = "CHÁ"
        with col3:
            if st.button("🍱\nMARMITA", use_container_width=True): st.session_state.item_selecionado = "MARMITA"
        with col4:
            if st.button("🍽️\nALMOÇO", use_container_width=True): st.session_state.item_selecionado = "ALMOÇO"

    # 3. TELA DE CONFIRMAÇÃO E AUDITORIA (Evita erros)
    else:
        item = st.session_state.item_selecionado
        
        st.warning("⚠️ **VERIFIQUE SEU PEDIDO ANTES DE CONFIRMAR**")
        st.write(f"**Colaborador:** {nome_selecionado}")
        st.write(f"**Item selecionado:** {item}")
        
        # Logica de litros para bebidas
        volume = "N/A"
        if item in ["CAFÉ", "CHÁ"]:
            volume = st.radio("Selecione os litros:", ["0.5 L", "1.0 L", "1.5 L", "2.0 L"], horizontal=True)

        st.markdown("---")
        
        # ASSINATURA ELETRÔNICA (Para Auditoria)
        assinatura = st.checkbox("Declaro que estou retirando este item (Assinatura Eletrônica)")
        
        # Botões lado a lado para Confirmar ou Cancelar
        c_confirma, c_cancela = st.columns(2)
        
        with c_cancela:
            if st.button("❌ CANCELAR E VOLTAR", use_container_width=True):
                del st.session_state.item_selecionado
                st.rerun() # Atualiza a tela

        with c_confirma:
            # O botão só funciona se a pessoa marcar a caixinha de assinatura
            if st.button("✅ CONFIRMAR E REGISTRAR", use_container_width=True, disabled=not assinatura):
                try:
                    codigo_auditoria = str(uuid.uuid4())[:8].upper() # Gera um código único (ex: A4B2C9)
                    
                    novo_registro = {
                        "data": datetime.now().strftime("%d/%m/%Y"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "colaborador": nome_selecionado,
                        "tipo": item,
                        "litros": volume,
                        "codigo_auditoria": codigo_auditoria # Salva o código rastreável
                    }
                    
                    supabase.table("registros").insert(novo_registro).execute()
                    
                    st.success(f"Registrado com sucesso! Cód. Auditoria: {codigo_auditoria}")
                    del st.session_state.item_selecionado
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
