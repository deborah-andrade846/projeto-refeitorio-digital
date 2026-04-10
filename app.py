import streamlit as st
from supabase import create_client, Client
from datetime import datetime
import uuid

# 1. CONFIGURAÇÃO VISUAL E CONEXÃO
st.set_page_config(page_title="Totem Refeitório", layout="centered")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erro de conexão com o banco.")

st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

# 2. BUSCANDO A LISTA DE NOMES DO BANCO DE DADOS
# Essa função vai no Supabase e traz todos os nomes cadastrados
def buscar_nomes():
    try:
        resposta = supabase.table("colaboradores").select("nome").execute()
        lista = [linha["nome"] for linha in resposta.data]
        return sorted(lista) # Coloca em ordem alfabética
    except:
        return []

lista_banco = buscar_nomes()
# Adicionamos a opção de "Novo Cadastro" no topo da lista
opcoes_dropdown = ["➕ NOVO CADASTRO..."] + lista_banco

nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", opcoes_dropdown, index=None, placeholder="Clique para buscar seu nome...")

# ==========================================
# FLUXO A: TELA DE NOVO CADASTRO
# ==========================================
if nome_selecionado == "➕ NOVO CADASTRO...":
    st.info("📝 **Primeiro Acesso:** Preencha seus dados para ser incluído no sistema.")
    novo_nome = st.text_input("Digite seu Nome Completo:").strip().upper()
    
    if st.button("💾 SALVAR MEU CADASTRO", use_container_width=True):
        if novo_nome == "":
            st.error("Por favor, digite um nome válido.")
        elif novo_nome in lista_banco:
            st.warning("Este nome já consta no sistema! Selecione-o na lista acima.")
        else:
            try:
                # Salva o novo nome na tabela "colaboradores"
                supabase.table("colaboradores").insert({"nome": novo_nome}).execute()
                st.success("✅ Cadastro realizado! Atualize a página (F5) para registrar sua refeição.")
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao cadastrar: {e}")

# ==========================================
# FLUXO B: RETIRADA DE REFEIÇÃO (Para quem já tem nome na lista)
# ==========================================
elif nome_selecionado:
    
    # Etapa 1: Escolher o Item
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

    # Etapa 2: Confirmação e Assinatura
    else:
        item = st.session_state.item_selecionado
        
        st.warning("⚠️ **VERIFIQUE SEU PEDIDO ANTES DE CONFIRMAR**")
        st.write(f"**Colaborador:** {nome_selecionado}")
        st.write(f"**Item selecionado:** {item}")
        
        volume = "N/A"
        if item in ["CAFÉ", "CHÁ"]:
            volume = st.radio("Selecione os litros:", ["0.5 L", "1.0 L", "1.5 L", "2.0 L"], horizontal=True)

        st.markdown("---")
        
        assinatura = st.checkbox("Declaro que estou retirando este item (Assinatura Eletrônica)")
        
        c_confirma, c_cancela = st.columns(2)
        
        with c_cancela:
            if st.button("❌ CANCELAR", use_container_width=True):
                del st.session_state.item_selecionado
                st.rerun()

        with c_confirma:
            if st.button("✅ CONFIRMAR E REGISTRAR", use_container_width=True, disabled=not assinatura):
                try:
                    codigo_auditoria = str(uuid.uuid4())[:8].upper()
                    
                    novo_registro = {
                        "data": datetime.now().strftime("%d/%m/%Y"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "colaborador": nome_selecionado,
                        "tipo": item,
                        "litros": volume,
                        "codigo_auditoria": codigo_auditoria
                    }
                    
                    # Salva o consumo na tabela "registros"
                    supabase.table("registros").insert(novo_registro).execute()
                    
                    st.success(f"Registrado com sucesso! Cód. Auditoria: {codigo_auditoria}")
                    del st.session_state.item_selecionado
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Erro técnico ao salvar: {e}")
