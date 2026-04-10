import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import uuid

# 1. CONFIGURAÇÃO E CONEXÃO
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

@st.cache_resource
def init_connection():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

try:
    supabase: Client = init_connection()
except Exception as e:
    st.error("Erro de conexão com o banco de dados.")

# --- FUNÇÕES DE APOIO ---
def buscar_nomes():
    try:
        res = supabase.table("colaboradores").select("nome").execute()
        return sorted([linha["nome"] for linha in res.data])
    except:
        return []

def verificar_trava_tempo(nome, tipo_refeicao):
    """Verifica se o colaborador já pegou esta refeição nas últimas 4h"""
    if tipo_refeicao not in ["ALMOÇO", "JANTAR"]:
        return True, ""
    
    agora = datetime.now()
    data_hoje = agora.strftime("%d/%m/%Y")
    
    try:
        res = supabase.table("registros")\
            .select("hora")\
            .eq("colaborador", nome)\
            .eq("data", data_hoje)\
            .eq("tipo", tipo_refeicao)\
            .order("hora", desc=True)\
            .limit(1).execute()
        
        if res.data:
            ultima_hora = datetime.strptime(res.data[0]['hora'], "%H:%M:%S")
            diferenca = agora - datetime.combine(agora.date(), ultima_hora.time())
            if diferenca.total_seconds() < 14400: # 4 horas
                return False, f"Bloqueado: Registro recente de {tipo_refeicao} (< 4h)."
    except:
        pass
    return True, ""

# --- INICIALIZAÇÃO DA MEMÓRIA ---
# 'item_selecionado' guarda o que a pessoa clicou para focar a tela
if 'item_selecionado' not in st.session_state:
    st.session_state.item_selecionado = None

# --- INTERFACE PRINCIPAL ---
st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

nomes = buscar_nomes()
nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", ["➕ NOVO CADASTRO..."] + nomes, index=None)

# ==========================================
# FLUXO 1: NOVO CADASTRO (Corrigido)
# ==========================================
if nome_selecionado == "➕ NOVO CADASTRO...":
    st.info("📝 Preencha seus dados para inclusão no sistema.")
    novo_nome = st.text_input("Nome Completo:").strip().upper()
    
    if st.button("💾 SALVAR CADASTRO", type="primary", use_container_width=True):
        if novo_nome == "":
            st.error("Digite um nome válido.")
        elif novo_nome in nomes:
            st.warning("Este nome já existe na lista.")
        else:
            try:
                supabase.table("colaboradores").insert({"nome": novo_nome}).execute()
                st.success("✅ Cadastro realizado com sucesso!")
                # O comando abaixo FORÇA a tela a recarregar para mostrar o nome novo na lista
                st.rerun() 
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# ==========================================
# FLUXO 2: SELEÇÃO E CONFIRMAÇÃO
# ==========================================
elif nome_selecionado:
    
    # TELA A: MENU PRINCIPAL (Só aparece se nada foi selecionado ainda)
    if not st.session_state.item_selecionado:
        st.write(f"### Olá, **{nome_selecionado}**!")
        st.write("**O que você vai retirar agora?**")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("☕\nCAFÉ"): 
                st.session_state.item_selecionado = "CAFÉ"
                st.rerun()
        with col2:
            if st.button("🍵\nCHÁ"): 
                st.session_state.item_selecionado = "CHÁ"
                st.rerun()
        with col3:
            if st.button("🍱\nMARMITA"): 
                st.session_state.item_selecionado = "MARMITA"
                st.rerun()
        with col4:
            pode_almoco, msg_almoco = verificar_trava_tempo(nome_selecionado, "ALMOÇO")
            if st.button("🍽️\nALMOÇO", disabled=not pode_almoco): 
                st.session_state.item_selecionado = "ALMOÇO"
                st.rerun()
            if not pode_almoco: st.caption(msg_almoco)
        with col5:
            pode_jantar, msg_jantar = verificar_trava_tempo(nome_selecionado, "JANTAR")
            if st.button("🌙\nJANTAR", disabled=not pode_jantar): 
                st.session_state.item_selecionado = "JANTAR"
                st.rerun()
            if not pode_jantar: st.caption(msg_jantar)

    # TELA B: DETALHES E CONFIRMAÇÃO (Foco total no item escolhido)
    else:
        item = st.session_state.item_selecionado
        
        st.warning("⚠️ **Confirme os dados do seu registro:**")
        st.write(f"**Colaborador:** {nome_selecionado}")
        st.write(f"**Item selecionado:** {item}")
        
        detalhe_final = "1 UN" # Valor padrão
        
        # Opções específicas dependendo do item
        if item in ["CAFÉ", "CHÁ"]:
            opcao = st.radio("Selecione o volume:", ["0.5 L", "1.0 L", "1.5 L", "2.0 L", "Outro..."], horizontal=True)
            if opcao == "Outro...":
                litros = st.number_input("Digite os litros:", min_value=0.1, max_value=10.0, step=0.1)
                detalhe_final = f"{litros} L"
            else:
                detalhe_final = opcao
                
        elif item == "MARMITA":
            qtd = st.number_input("Quantidade de Marmitas:", min_value=1, max_value=5, step=1)
            detalhe_final = f"{qtd} UN"
            
        else: # Almoço / Jantar (Travado em 1 unidade)
            st.info("Regra Corporativa: Limite de 1 unidade por registro.")
            detalhe_final = "1 UN"

        st.markdown("---")
        assinatura = st.checkbox("Declaro que estou retirando este item (Assinatura Eletrônica)")
        
        # Botões de Ação
        c_cancela, c_confirma = st.columns(2)
        
        with c_cancela:
            if st.button("❌ CANCELAR E VOLTAR", use_container_width=True):
                st.session_state.item_selecionado = None # Limpa a memória e volta pro menu
                st.rerun()

        with c_confirma:
            if st.button("✅ CONFIRMAR REGISTRO", use_container_width=True, disabled=not assinatura, type="primary"):
                try:
                    cod_auditoria = str(uuid.uuid4())[:8].upper()
                    
                    dados_bd = {
                        "data": datetime.now().strftime("%d/%m/%Y"),
                        "hora": datetime.now().strftime("%H:%M:%S"),
                        "colaborador": nome_selecionado,
                        "tipo": item,
                        "litros": detalhe_final,
                        "codigo_auditoria": cod_auditoria
                    }
                    
                    supabase.table("registros").insert(dados_bd).execute()
                    
                    st.success(f"✅ Registrado com sucesso! Cód: {cod_auditoria}")
                    st.session_state.item_selecionado = None # Esvazia a tela para o próximo
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
