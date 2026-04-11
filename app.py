import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
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

# --- INICIALIZAÇÃO DE ESTADO ---
if 'item_selecionado' not in st.session_state:
    st.session_state.item_selecionado = None

# --- INTERFACE PRINCIPAL ---
st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

nomes_cadastrados = buscar_nomes()
nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", ["➕ NOVO CADASTRO..."] + nomes_cadastrados, index=None)

# ==========================================
# FLUXO 1: NOVO CADASTRO
# ==========================================
if nome_selecionado == "➕ NOVO CADASTRO...":
    st.info("📝 Preencha os dados para inclusão no sistema.")
    
    novo_nome = st.text_input("Nome Completo (Obrigatório):").strip().upper()
    nova_empresa = st.text_input("Empresa (Obrigatório):").strip().upper()
    nova_matricula = st.text_input("Matrícula (Opcional):").strip().upper()
    
    if st.button("💾 SALVAR CADASTRO", type="primary", use_container_width=True):
        if len(novo_nome.split()) < 2:
            st.error("⚠️ Digite seu Nome e Sobrenome.")
        elif nova_empresa == "":
            st.error("⚠️ O campo Empresa é obrigatório.")
        elif novo_nome in nomes_cadastrados:
            st.warning("⚠️ Este nome já existe na lista.")
        else:
            try:
                mat_final = nova_matricula if nova_matricula != "" else "N/A"
                supabase.table("colaboradores").insert({
                    "nome": novo_nome, "empresa": nova_empresa, "matricula": mat_final
                }).execute()
                st.success("✅ Cadastro realizado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# ==========================================
# FLUXO 2: SELEÇÃO E REGISTRO
# ==========================================
elif nome_selecionado:
    
    if not st.session_state.item_selecionado:
        st.write(f"### Olá, **{nome_selecionado}**!")
        st.write("**O que você vai retirar agora?**")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            if st.button("☕\nCAFÉ"): st.session_state.item_selecionado = "CAFÉ"; st.rerun()
        with col2:
            if st.button("🍵\nCHÁ"): st.session_state.item_selecionado = "CHÁ"; st.rerun()
        with col3:
            if st.button("🍱\nMARMITA"): st.session_state.item_selecionado = "MARMITA"; st.rerun()
        with col4:
            pode_almoco, msg_a = verificar_trava_tempo(nome_selecionado, "ALMOÇO")
            if st.button("🍽️\nALMOÇO", disabled=not pode_almoco): st.session_state.item_selecionado = "ALMOÇO"; st.rerun()
            if not pode_almoco: st.caption(msg_a)
        with col5:
            pode_jantar, msg_j = verificar_trava_tempo(nome_selecionado, "JANTAR")
            if st.button("🌙\nJANTAR", disabled=not pode_jantar): st.session_state.item_selecionado = "JANTAR"; st.rerun()
            if not pode_jantar: st.caption(msg_j)

    else:
        item = st.session_state.item_selecionado
        st.warning(f"⚠️ **Confirmando Registro: {item}**")
        
        lista_para_salvar = []
        
        if item in ["CAFÉ", "CHÁ"]:
            st.write("Selecione a quantidade de garrafas:")
            l1, l2, l3, l4 = st.columns(4)
            with l1: q05 = st.number_input("0.5 L", 0, 10, 0); [lista_para_salvar.append("0.5 L") for _ in range(q05)]
            with l2: q10 = st.number_input("1.0 L", 0, 10, 0); [lista_para_salvar.append("1.0 L") for _ in range(q10)]
            with l3: q15 = st.number_input("1.5 L", 0, 10, 0); [lista_para_salvar.append("1.5 L") for _ in range(q15)]
            with l4: q18 = st.number_input("1.8 L", 0, 10, 0); [lista_para_salvar.append("1.8 L") for _ in range(q18)]
            
            l5, l6, l7 = st.columns(3)
            with l5: q20 = st.number_input("2.0 L", 0, 10, 0); [lista_para_salvar.append("2.0 L") for _ in range(q20)]
            with l6: q25 = st.number_input("2.5 L", 0, 10, 0); [lista_para_salvar.append("2.5 L") for _ in range(q25)]
            with l7: q35 = st.number_input("3.5 L", 0, 10, 0); [lista_para_salvar.append("3.5 L") for _ in range(q35)]
            
            st.write("Outro tamanho?")
            co1, co2 = st.columns(2)
            with co1: l_out = st.number_input("Litragem:", 0.0, 10.0, 0.0, step=0.1)
            with co2: q_out = st.number_input("Qtd:", 0, 10, 0); [lista_para_salvar.append(f"{l_out} L") for _ in range(q_out) if l_out > 0]

        elif item == "MARMITA":
            qtd_m = st.number_input("Quantidade:", 1, 10, 1)
            [lista_para_salvar.append("1 UN") for _ in range(qtd_m)]
        else:
            st.info("Limite de 1 unidade por turno.")
            lista_para_salvar.append("1 UN")

        st.markdown("---")
        total = len(lista_para_salvar)
        assinatura = st.checkbox(f"Assino a retirada de {total} item(ns)", disabled=(total == 0))
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("❌ CANCELAR", use_container_width=True):
                st.session_state.item_selecionado = None; st.rerun()
        with c2:
            if st.button("✅ CONFIRMAR", use_container_width=True, disabled=not assinatura, type="primary"):
                try:
                    cod = str(uuid.uuid4())[:8].upper()
                    dt, hr = datetime.now().strftime("%d/%m/%Y"), datetime.now().strftime("%H:%M:%S")
                    for lit in lista_para_salvar:
                        supabase.table("registros").insert({
                            "data": dt, "hora": hr, "colaborador": nome_selecionado,
                            "tipo": item, "litros": lit, "codigo_auditoria": cod
                        }).execute()
                    st.success(f"✅ Registrado! Cód: {cod}")
                    st.session_state.item_selecionado = None; st.balloons()
                except Exception as e: st.error(f"Erro: {e}")

# ==========================================
# PORTAL DE MEDIÇÃO (BARRA LATERAL)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("🔒 Administração")
if st.sidebar.checkbox("Portal de Medição"):
    senha = st.sidebar.text_input("Senha:", type="password")
    if senha == "Aura@2026": # Escolha sua senha
        st.markdown("---")
        st.header("📊 Dados de Medição")
        try:
            adm_res = supabase.table("registros").select("*").execute()
            df = pd.DataFrame(adm_res.data)
            if not df.empty:
                df = df[["data", "hora", "colaborador", "tipo", "litros", "codigo_auditoria"]]
                st.dataframe(df, use_container_width=True)
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button("📥 BAIXAR CSV", csv, "medicao.csv", "text/csv", use_container_width=True)
        except Exception as e: st.error(f"Erro: {e}")
    elif senha != "": st.sidebar.error("Incorreta")
    
    elif senha != "":
        st.sidebar.error("Senha incorreta!")                    
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
