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
except:
    st.error("Erro de conexão.")

# --- FUNÇÕES DE APOIO ---

def buscar_nomes():
    res = supabase.table("colaboradores").select("nome").execute()
    return sorted([linha["nome"] for linha in res.data])

def verificar_trava_tempo(nome, tipo_refeicao):
    """Verifica se houve Almoço/Jantar nas últimas 4 horas"""
    if tipo_refeicao not in ["ALMOÇO", "JANTAR"]:
        return True, "" # Café e Marmita não têm trava de tempo
    
    agora = datetime.now()
    quatro_horas_atras = (agora - timedelta(hours=4)).strftime("%H:%M:%S")
    data_hoje = agora.strftime("%d/%m/%Y")
    
    # Busca o último registro desse tipo hoje para esse colaborador
    res = supabase.table("registros")\
        .select("hora")\
        .eq("colaborador", nome)\
        .eq("data", data_hoje)\
        .eq("tipo", tipo_refeicao)\
        .order("hora", desc=True)\
        .limit(1)\
        .execute()
    
    if res.data:
        ultima_hora = datetime.strptime(res.data[0]['hora'], "%H:%M:%S")
        diferenca = agora - datetime.combine(agora.date(), ultima_hora.time())
        
        if diferenca.total_seconds() < 14400: # 14400 segundos = 4 horas
            return False, f"Bloqueado: Você já registrou {tipo_refeicao} há menos de 4h."
            
    return True, ""

# --- INTERFACE ---

st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

nomes = buscar_nomes()
nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", ["➕ NOVO CADASTRO..."] + nomes, index=None)

if 'cesta' not in st.session_state:
    st.session_state.cesta = []

if nome_selecionado == "➕ NOVO CADASTRO...":
    # (Mantenha seu código de cadastro aqui...)
    pass

# ==========================================
# FLUXO DE REGISTRO (Corrigido com Memória de Estado)
# ==========================================
elif nome_selecionado:
    st.write(f"### Olá, **{nome_selecionado}**!")
    
    # Cria a memória para saber qual botão foi clicado
    if 'menu_ativo' not in st.session_state:
        st.session_state.menu_ativo = None

    # 1. SELEÇÃO DE ITENS
    st.write("**O que você está levando?**")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        if st.button("☕\nCAFÉ"): st.session_state.menu_ativo = "CAFÉ"
    with col2:
        if st.button("🍵\nCHÁ"): st.session_state.menu_ativo = "CHÁ"
    with col3:
        if st.button("🍱\nMARMITA"): st.session_state.menu_ativo = "MARMITA"
    with col4:
        pode_almoco, msg_almoco = verificar_trava_tempo(nome_selecionado, "ALMOÇO")
        if st.button("🍽️\nALMOÇO", disabled=not pode_almoco): st.session_state.menu_ativo = "ALMOÇO"
        if not pode_almoco: st.caption(msg_almoco)
    with col5:
        pode_jantar, msg_jantar = verificar_trava_tempo(nome_selecionado, "JANTAR")
        if st.button("🌙\nJANTAR", disabled=not pode_jantar): st.session_state.menu_ativo = "JANTAR"
        if not pode_jantar: st.caption(msg_jantar)

    # 2. DETALHAMENTO DO ITEM (Só aparece se algo estiver na memória)
    if st.session_state.menu_ativo:
        item = st.session_state.menu_ativo
        st.markdown(f"#### Detalhando: {item}")
        detalhe = "1 UN" # Padrão
        
        if item in ["CAFÉ", "CHÁ"]:
            opcao = st.radio("Litragem:", ["0.5 L", "1.0 L", "1.5 L", "2.0 L", "Outro"], horizontal=True)
            if opcao == "Outro":
                detalhe = f"{st.number_input('Litros:', 0.1, 10.0, 1.0)} L"
            else:
                detalhe = opcao
        
        elif item == "MARMITA":
            qtd = st.number_input("Quantidade de Marmitas:", 1, 5, 1)
            detalhe = f"{qtd} UN"
        
        else: # Almoço ou Jantar
            st.info("Regra: Limite de 1 refeição por pessoa.")
            detalhe = "1 UN"

        # O botão que salva na lista
        if st.button(f"➕ CONFIRMAR {item} NA LISTA", type="secondary"):
            st.session_state.cesta.append({"tipo": item, "detalhe": detalhe})
            st.session_state.menu_ativo = None # Limpa a memória para fechar esse menu
            st.rerun() # Pisca a tela para atualizar na hora!

    # 3. FINALIZAÇÃO (A Cesta e o Botão Final)
    if len(st.session_state.cesta) > 0:
        st.write("---")
        st.write("### 🛒 Sua Lista de Retirada")
        
        # Mostra tudo que está no carrinho
        for i, r in enumerate(st.session_state.cesta):
            st.write(f"**{i+1}.** {r['tipo']} ({r['detalhe']})")
        
        if st.button("🗑️ Limpar Lista"):
            st.session_state.cesta = []
            st.rerun()

        st.markdown("---")
        assinatura = st.checkbox("Confirmo a retirada dos itens acima (Assinatura Eletrônica)")
        
        # O botão de enviar para o banco de dados
        if st.button("🚀 FINALIZAR REGISTRO NO SISTEMA", disabled=not assinatura, type="primary"):
            try:
                cod = str(uuid.uuid4())[:8].upper()
                dt, hr = datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M:%S")
                
                for item_cesta in st.session_state.cesta:
                    supabase.table("registros").insert({
                        "data": dt, "hora": hr, "colaborador": nome_selecionado,
                        "tipo": item_cesta['tipo'], "litros": item_cesta['detalhe'], "codigo_auditoria": cod
                    }).execute()
                
                st.success(f"✅ Tudo registrado! Cód. Auditoria: {cod}")
                st.session_state.cesta = [] # Esvazia a cesta depois de salvar
                st.balloons()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")
