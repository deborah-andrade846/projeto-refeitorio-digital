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

elif nome_selecionado:
    st.write(f"### Olá, **{nome_selecionado}**!")
    
    # 1. SELEÇÃO DE ITENS
    st.write("**O que você está levando?**")
    col1, col2, col3, col4, col5 = st.columns(5)
    
    item_atual = None
    with col1:
        if st.button("☕\nCAFÉ"): item_atual = "CAFÉ"
    with col2:
        if st.button("🍵\nCHÁ"): item_atual = "CHÁ"
    with col3:
        if st.button("🍱\nMARMITA"): item_atual = "MARMITA"
    with col4:
        # Validação para Almoço
        pode_almoco, msg_almoco = verificar_trava_tempo(nome_selecionado, "ALMOÇO")
        if st.button("🍽️\nALMOÇO", disabled=not pode_almoco): item_atual = "ALMOÇO"
        if not pode_almoco: st.caption(msg_almoco)
    with col5:
        # Validação para Jantar
        pode_jantar, msg_jantar = verificar_trava_tempo(nome_selecionado, "JANTAR")
        if st.button("🌙\nJANTAR", disabled=not pode_jantar): item_atual = "JANTAR"
        if not pode_jantar: st.caption(msg_jantar)

    # 2. DETALHAMENTO DO ITEM SELECIONADO
    if item_atual:
        st.markdown(f"#### Detalhando: {item_atual}")
        detalhe = "1 UN" # Padrão
        
        if item_atual in ["CAFÉ", "CHÁ"]:
            detalhe = st.radio("Litragem:", ["0.5 L", "1.0 L", "1.5 L", "2.0 L", "Outro"], horizontal=True)
            if detalhe == "Outro":
                detalhe = f"{st.number_input('Litros:', 0.1, 10.0, 1.0)} L"
        
        elif item_atual == "MARMITA":
            qtd = st.number_input("Quantidade de Marmitas:", 1, 5, 1)
            detalhe = f"{qtd} UN"
        
        else: # Almoço ou Jantar
            st.info("Regra: Limite de 1 refeição por pessoa.")
            detalhe = "1 UN"

        if st.button(f"➕ ADICIONAR {item_atual} À LISTA"):
            st.session_state.cesta.append({"tipo": item_atual, "detalhe": detalhe})
            st.toast("Adicionado!")

    # 3. FINALIZAÇÃO (Cesta e Assinatura)
    if st.session_state.cesta:
        st.write("---")
        st.write("### 🛒 Resumo da Retirada")
        for i, r in enumerate(st.session_state.cesta):
            st.write(f"{i+1}. {r['tipo']} ({r['detalhe']})")
        
        if st.button("🗑️ Limpar"):
            st.session_state.cesta = []
            st.rerun()

        assinatura = st.checkbox("Confirmo a retirada dos itens acima")
        
        if st.button("🚀 FINALIZAR REGISTRO", disabled=not assinatura, type="primary"):
            try:
                cod = str(uuid.uuid4())[:8].upper()
                dt, hr = datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M:%S")
                
                for item in st.session_state.cesta:
                    supabase.table("registros").insert({
                        "data": dt, "hora": hr, "colaborador": nome_selecionado,
                        "tipo": item['tipo'], "litros": item['detalhe'], "codigo_auditoria": cod
                    }).execute()
                
                st.success(f"Registrado! Cód: {cod}")
                st.session_state.cesta = []
                st.balloons()
            except Exception as e:
                st.error(f"Erro: {e}")
