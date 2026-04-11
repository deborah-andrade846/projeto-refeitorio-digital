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

# --- INTERFACE PRINCIPAL ---
st.title("🚀 Registro Digital - Refeitório")
st.markdown("---")

nomes_cadastrados = buscar_nomes()
nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", ["➕ NOVO CADASTRO..."] + nomes_cadastrados, index=None)

# --- FLUXO 1: NOVO CADASTRO ---
if nome_selecionado == "➕ NOVO CADASTRO...":
    st.info("📝 Preencha os dados abaixo:")
    n_nome = st.text_input("Nome Completo (Mínimo 2 nomes):").strip().upper()
    n_empresa = st.text_input("Empresa:").strip().upper()
    n_mat = st.text_input("Matrícula (Opcional):").strip().upper()
    
    if st.button("💾 SALVAR CADASTRO", type="primary", use_container_width=True):
        if len(n_nome.split()) < 2:
            st.error("⚠️ Digite o nome completo (Nome e Sobrenome).")
        elif n_empresa == "":
            st.error("⚠️ Informe a empresa.")
        else:
            try:
                supabase.table("colaboradores").insert({
                    "nome": n_nome, "empresa": n_empresa, "matricula": n_mat if n_mat else "N/A"
                }).execute()
                st.success("✅ Cadastro realizado!")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao salvar: {e}")

# --- FLUXO 2: REGISTRO DE CONSUMO ---
elif nome_selecionado:
    if not st.session_state.item_selecionado:
        st.write(f"### Olá, **{nome_selecionado}**!")
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1: 
            if st.button("☕\nCAFÉ"): st.session_state.item_selecionado = "CAFÉ"; st.rerun()
        with c2: 
            if st.button("🍵\nCHÁ"): st.session_state.item_selecionado = "CHÁ"; st.rerun()
        with c3: 
            if st.button("🍱\nMARMITA"): st.session_state.item_selecionado = "MARMITA"; st.rerun()
        with col4:
            pode_a, msg_a = verificar_trava_tempo(nome_selecionado, "ALMOÇO")
            if st.button("🍽️\nALMOÇO", disabled=not pode_a): st.session_state.item_selecionado = "ALMOÇO"; st.rerun()
            if not pode_a: st.caption(msg_a)
        with col5:
            pode_j, msg_j = verificar_trava_tempo(nome_selecionado, "JANTAR")
            if st.button("🌙\nJANTAR", disabled=not pode_j): st.session_state.item_selecionado = "JANTAR"; st.rerun()
            if not pode_j: st.caption(msg_j)

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
        total_retirado = len(lista_final)
        assinatura = st.checkbox(f"Assino a retirada de {total_retirado} item(ns)", disabled=(total_retirado==0))
        
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
                    st.success(f"✅ Registrado! Cód: {cod}")
                    st.session_state.item_selecionado = None
                    st.balloons()
                except Exception as e: st.error(f"Erro: {e}")

# --- PORTAL DE MEDIÇÃO (ADMIN) ---
st.sidebar.markdown("---")
if st.sidebar.checkbox("Portal de Medição"):
    pw = st.sidebar.text_input("Senha:", type="password")
    if pw == "Aura@2026":
        st.header("📊 Portal de Medição")
        try:
            res_adm = supabase.table("registros").select("*").execute()
            df = pd.DataFrame(res_adm.data)
            if not df.empty:
                df = df[["data", "hora", "colaborador", "tipo", "litros", "codigo_auditoria"]]
                st.dataframe(df, use_container_width=True)
                
                # Gerando Excel na memória
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False)
                
                st.download_button(
                    label="📥 BAIXAR PLANILHA (EXCEL)",
                    data=output.getvalue(),
                    file_name=f"Medicao_{datetime.now().strftime('%d_%m_%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        except Exception as e: st.error(f"Erro: {e}")
    elif pw != "": st.sidebar.error("Senha incorreta")
