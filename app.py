import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import uuid
import io

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

# 2. CONEXÃO COM O BANCO DE DADOS
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Erro nos Secrets do Streamlit.")
        return None

supabase = init_connection()

# --- FUNÇÕES DE APOIO ---

def buscar_dados_colaboradores():
    try:
        # Buscamos agora o nome e a senha criada
        res = supabase.table("colaboradores").select("nome, senha").execute()
        return res.data
    except:
        return []

def verificar_trava_tempo(nome, tipo_refeicao):
    if tipo_refeicao not in ["ALMOÇO", "JANTAR"]:
        return True, ""
    agora = datetime.now()
    data_hoje = agora.strftime("%d/%m/%Y")
    try:
        res = supabase.table("registros").select("hora").eq("colaborador", nome).eq("data", data_hoje).eq("tipo", tipo_refeicao).order("hora", desc=True).limit(1).execute()
        if res.data:
            ultima_h = datetime.strptime(res.data[0]['hora'], "%H:%M:%S")
            diff = agora - datetime.combine(agora.date(), ultima_h.time())
            if diff.total_seconds() < 14400: # 4 horas
                return False, f"Bloqueado: Registro recente de {tipo_refeicao} (< 4h)."
    except:
        pass
    return True, ""

# --- ESTADO DO SISTEMA ---
if 'item_selecionado' not in st.session_state:
    st.session_state.item_selecionado = None
if 'usuario_autenticado' not in st.session_state:
    st.session_state.usuario_autenticado = False

# --- INTERFACE PRINCIPAL ---
st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

dados_usuarios = buscar_dados_colaboradores()
nomes_lista = sorted([u["nome"] for u in dados_usuarios])
nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", ["➕ NOVO CADASTRO..."] + nomes_lista, index=None)

# Reset de autenticação se mudar o nome selecionado
if 'ultimo_nome' not in st.session_state or st.session_state.ultimo_nome != nome_selecionado:
    st.session_state.usuario_autenticado = False
    st.session_state.ultimo_nome = nome_selecionado

# ==========================================
# FLUXO 1: NOVO CADASTRO COM CRIAÇÃO DE SENHA
# ==========================================
if nome_selecionado == "➕ NOVO CADASTRO...":
    st.info("📝 Preencha os dados abaixo e crie sua senha de acesso.")
    n_nome = st.text_input("Nome Completo:").strip().upper()
    n_empresa = st.text_input("Empresa:").strip().upper()
    n_senha = st.text_input("Crie uma Senha Numérica (Ex: 1234):", type="password").strip()
    
    if st.button("💾 SALVAR CADASTRO", type="primary", use_container_width=True):
        if len(n_nome.split()) < 2:
            st.error("⚠️ Digite o nome completo (Nome e Sobrenome).")
        elif n_empresa == "" or n_senha == "":
            st.error("⚠️ Empresa e Senha são obrigatórios.")
        else:
            try:
                supabase.table("colaboradores").insert({
                    "nome": n_nome, "empresa": n_empresa, "senha": n_senha
                }).execute()
                st.success("✅ Cadastro realizado! Selecione seu nome para entrar.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# ==========================================
# FLUXO 2: VALIDAÇÃO POR SENHA E REGISTRO
# ==========================================
elif nome_selecionado:
    # Busca a senha correta do usuário selecionado
    colab_info = next((u for u in dados_usuarios if u["nome"] == nome_selecionado), None)
    senha_correta = str(colab_info["senha"]).strip() if colab_info else None

    if not st.session_state.usuario_autenticado:
        st.warning(f"Olá {nome_selecionado}, digite sua senha para continuar.")
        senha_digitada = st.text_input("Sua Senha:", type="password")
        if st.button("ENTRAR"):
            if senha_digitada.strip() == senha_correta:
                st.session_state.usuario_autenticado = True
                st.rerun()
            else:
                st.error("❌ Senha incorreta!")

    if st.session_state.usuario_autenticado:
        if not st.session_state.item_selecionado:
            st.write(f"### Bem-vindo(a), **{nome_selecionado}**!")
            c1, c2, c3, c4, c5 = st.columns(5)
            with c1: 
                if st.button("☕\nCAFÉ"): st.session_state.item_selecionado = "CAFÉ"; st.rerun()
            with c2: 
                if st.button("🍵\nCHÁ"): st.session_state.item_selecionado = "CHÁ"; st.rerun()
            with c3: 
                if st.button("🍱\nMARMITA"): st.session_state.item_selecionado = "MARMITA"; st.rerun()
            with c4:
                p_a, m_a = verificar_trava_tempo(nome_selecionado, "ALMOÇO")
                if st.button("🍽️\nALMOÇO", disabled=not p_a): st.session_state.item_selecionado = "ALMOÇO"; st.rerun()
                if not p_a: st.caption(m_a)
            with c5:
                p_j, m_j = verificar_trava_tempo(nome_selecionado, "JANTAR")
                if st.button("🌙\nJANTAR", disabled=not p_j): st.session_state.item_selecionado = "JANTAR"; st.rerun()
                if not p_j: st.caption(m_j)
        else:
            item = st.session_state.item_selecionado
            st.warning(f"**Registrando: {item}**")
            lista_final = []
            
            if item in ["CAFÉ", "CHÁ"]:
                l1, l2, l3, l4 = st.columns(4)
                with l1: q05 = st.number_input("0.5 L", 0, 10, 0); [lista_final.append("0.5 L") for _ in range(q05)]
                with l2: q10 = st.number_input("1.0 L", 0, 10, 0); [lista_final.append("1.0 L") for _ in range(q10)]
                with l3: q15 = st.number_input("1.5 L", 0, 10, 0); [lista_final.append("1.5 L") for _ in range(q15)]
                with l4: q18 = st.number_input("1.8 L", 0, 10, 0); [lista_final.append("1.8 L") for _ in range(q18)]
                l5, l6, l7 = st.columns(3)
                with l5: q20 = st.number_input("2.0 L", 0, 10, 0); [lista_final.append("2.0 L") for _ in range(q20)]
                with l6: q25 = st.number_input("2.5 L", 0, 10, 0); [lista_final.append("2.5 L") for _ in range(q25)]
                with l7: q35 = st.number_input("3.5 L", 0, 10, 0); [lista_final.append("3.5 L") for _ in range(q35)]
            elif item == "MARMITA":
                qm = st.number_input("Quantidade:", 1, 10, 1); [lista_final.append("1 UN") for _ in range(qm)]
            else:
                lista_final.append("1 UN")

            st.markdown("---")
            total_ret = len(lista_final)
            assinatura = st.checkbox(f"Assino a retirada", disabled=(total_ret==0))
            
            c_can, c_con = st.columns(2)
            with c_can:
                if st.button("❌ CANCELAR"): st.session_state.item_selecionado = None; st.rerun()
            with c_con:
                if st.button("✅ CONFIRMAR", type="primary", disabled=not assinatura):
                    try:
                        cod = str(uuid.uuid4())[:8].upper()
                        dt, hr = datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M:%S")
                        for lit in lista_final:
                            supabase.table("registros").insert({
                                "data": dt, "hora": hr, "colaborador": nome_selecionado, 
                                "tipo": item, "litros": lit, "codigo_auditoria": cod
                            }).execute()
                        st.success(f"✅ Registrado!")
                        st.session_state.item_selecionado = None
                        st.session_state.usuario_autenticado = False
                        st.balloons()
                    except Exception as e: st.error(f"Erro: {e}")

# --- PORTAL DE MEDIÇÃO COM FILTRO POR PERÍODO ---
st.sidebar.markdown("---")
if st.sidebar.checkbox("Portal de Medição"):
    pw = st.sidebar.text_input("Senha Admin:", type="password")
    if pw == "Aura@2026":
        st.header("📊 Filtro de Medição")
        
        # Seletores de Data
        col_i, col_f = st.columns(2)
        with col_i:
            d_inicio = st.date_input("De:", datetime.now() - timedelta(days=7))
        with col_f:
            d_fim = st.date_input("Até:", datetime.now())

        if st.button("🔍 CARREGAR PERÍODO", use_container_width=True):
            try:
                res_adm = supabase.table("registros").select("*").execute()
                df = pd.DataFrame(res_adm.data)
                
                if not df.empty:
                    # Filtramos pela coluna 'data' convertendo para o formato de data real
                    df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y').dt.date
                    mask = (df['data_dt'] >= d_inicio) & (df['data_dt'] <= d_fim)
                    df_filtrado = df.loc[mask].drop(columns=['data_dt'])

                    if not df_filtrado.empty:
                        st.write(f"Registros encontrados: {len(df_filtrado)}")
                        st.dataframe(df_filtrado[["data", "hora", "colaborador", "tipo", "litros", "codigo_auditoria"]], use_container_width=True)
                        
                        output = io.BytesIO()
                        with pd.ExcelWriter(output, engine='openpyxl') as writer:
                            df_filtrado.to_excel(writer, index=False, sheet_name='Medicao')
                        
                        st.download_button(
                            label="📥 BAIXAR EXCEL DO PERÍODO",
                            data=output.getvalue(),
                            file_name=f"Medicao_{d_inicio}_a_{d_fim}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            use_container_width=True
                        )
                    else:
                        st.warning("Nenhum registro encontrado neste período.")
            except Exception as e: st.error(f"Erro ao filtrar: {e}")
    elif pw != "": st.sidebar.error("Senha incorreta")
