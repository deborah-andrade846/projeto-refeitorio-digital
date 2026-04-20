import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import uuid
import io
import hashlib
import time

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

# ==========================================
# 2. CONEXÃO COM O BANCO DE DADOS
# ==========================================
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

# ==========================================
# 3. CONSTANTES
# ==========================================
TIMEOUT_MINUTOS = 5  # Sessão expira após 5 min de inatividade

# ==========================================
# 4. FUNÇÕES DE SEGURANÇA
# ==========================================

def hash_senha(senha: str) -> str:
    """Gera hash SHA-256 da senha."""
    return hashlib.sha256(senha.strip().encode()).hexdigest()

def verificar_senha(senha_digitada: str, senha_db: str) -> bool:
    """
    Verifica senha com suporte a migração:
    - Aceita senhas já em hash (novos cadastros)
    - Aceita senhas em texto puro (cadastros antigos, para compatibilidade)
    """
    if not senha_db:
        return False
    if senha_db == hash_senha(senha_digitada):
        return True
    # Fallback: suporte a senhas antigas (texto puro) durante período de migração
    if senha_db == senha_digitada.strip():
        return True
    return False

# ==========================================
# 5. FUNÇÕES DE SESSÃO / TIMEOUT
# ==========================================

def verificar_timeout() -> bool:
    """Retorna True se a sessão expirou por inatividade."""
    if "ultimo_ativo" not in st.session_state:
        return False
    return (time.time() - st.session_state.ultimo_ativo) > (TIMEOUT_MINUTOS * 60)

def atualizar_atividade():
    """Atualiza o timestamp de última atividade."""
    st.session_state.ultimo_ativo = time.time()

def resetar_sessao():
    """Reseta todos os estados de sessão do colaborador."""
    st.session_state.usuario_autenticado = False
    st.session_state.item_selecionado = None
    st.session_state.ultimo_nome = None
    st.session_state.chave_identificacao = str(uuid.uuid4())
    st.session_state.pop("ultimo_ativo", None)

# ==========================================
# 6. FUNÇÕES DE DADOS
# ==========================================

@st.cache_data(ttl=60)
def buscar_dados_colaboradores():
    """Busca colaboradores com cache de 60 segundos."""
    try:
        res = supabase.table("colaboradores").select("nome, senha").execute()
        return res.data
    except:
        return []

def hora_local():
    """Retorna hora atual no fuso de Mato Grosso (UTC-4)."""
    return datetime.utcnow() - timedelta(hours=4)

def verificar_regras_refeicao(nome, tipo_refeicao):
    if tipo_refeicao not in ["ALMOÇO", "JANTAR"]:
        return True, ""

    agora = hora_local()
    hora_atual = agora.hour
    data_hoje = agora.strftime("%d/%m/%Y")

    if tipo_refeicao == "ALMOÇO":
        if not (10 <= hora_atual < 14):
            return False, "Fora do horário (10h às 14h)"
    elif tipo_refeicao == "JANTAR":
        if hora_atual < 20:
            return False, "Fora do horário (20h às 00h)"

    try:
        res = (
            supabase.table("registros")
            .select("id")
            .eq("colaborador", nome)
            .eq("data", data_hoje)
            .eq("tipo", tipo_refeicao)
            .limit(1)
            .execute()
        )
        if res.data:
            return False, f"Bloqueado: {tipo_refeicao} já consumido hoje."
    except:
        pass
    return True, ""

def inserir_registros(nome, item, lista_final):
    """Insere registros no Supabase e retorna o código de auditoria."""
    cod = str(uuid.uuid4())[:8].upper()
    agora_mt = hora_local()
    dt = agora_mt.strftime("%d/%m/%Y")
    hr = agora_mt.strftime("%H:%M:%S")

    for lit in lista_final:
        supabase.table("registros").insert({
            "data": dt,
            "hora": hr,
            "colaborador": nome,
            "tipo": item,
            "litros": lit,
            "codigo_auditoria": cod,
        }).execute()
    return cod

def gerar_excel(df_exibir, d_inicio, d_fim):
    """Gera Excel com aba de resumo e aba de detalhes."""
    resumo_tipo = df_exibir.groupby("tipo").size().reset_index(name="Quantidade")
    resumo_colab = (
        df_exibir.groupby("colaborador").size()
        .reset_index(name="Quantidade")
        .sort_values("Quantidade", ascending=False)
    )

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        resumo_tipo.to_excel(writer, sheet_name="Resumo por Tipo", index=False)
        resumo_colab.to_excel(writer, sheet_name="Resumo por Colaborador", index=False)
        df_exibir.to_excel(writer, sheet_name="Detalhes", index=False)

    return output.getvalue()

# ==========================================
# 7. INICIALIZAÇÃO DO ESTADO
# ==========================================
defaults = {
    "item_selecionado": None,
    "usuario_autenticado": False,
    "chave_identificacao": str(uuid.uuid4()),
    "mostrar_sucesso": False,
    "ultimo_nome": None,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================
# 8. TIMEOUT AUTOMÁTICO
# ==========================================
if st.session_state.usuario_autenticado and verificar_timeout():
    resetar_sessao()
    st.warning("⏱️ Sessão encerrada por inatividade. Identifique-se novamente.")

if st.session_state.usuario_autenticado:
    atualizar_atividade()

# ==========================================
# 9. BARRA LATERAL — ACESSO ADMIN
# ==========================================
st.sidebar.markdown("---")
modo_admin = st.sidebar.checkbox("Acessar Portal de Medição")
senha_admin_ok = False

if modo_admin:
    pw_admin = st.sidebar.text_input("Senha Admin:", type="password")
    # Senha vinda dos secrets; fallback local apenas para desenvolvimento
    senha_admin_correta = st.secrets.get("ADMIN_PASSWORD", "Aura@2026")
    if pw_admin == senha_admin_correta:
        senha_admin_ok = True
    elif pw_admin != "":
        st.sidebar.error("Senha incorreta!")

# ==========================================
# TELA 1: PORTAL ADMINISTRATIVO
# ==========================================
if senha_admin_ok:
    st.title("📊 Portal Administrativo - Medição")
    st.markdown("---")

    col_i, col_f = st.columns(2)
    with col_i:
        d_inicio = st.date_input("Data Início:", hora_local() - timedelta(days=30), format="DD/MM/YYYY")
    with col_f:
        d_fim = st.date_input("Data Fim:", hora_local(), format="DD/MM/YYYY")

    if st.button("🔍 CARREGAR DADOS DO PERÍODO", use_container_width=True):
        try:
            res_adm = supabase.table("registros").select("*").execute()
            df = pd.DataFrame(res_adm.data)

            if not df.empty:
                df["data_dt"] = pd.to_datetime(df["data"], format="%d/%m/%Y").dt.date
                mask = (df["data_dt"] >= d_inicio) & (df["data_dt"] <= d_fim)
                df_filtrado = df.loc[mask].drop(columns=["data_dt"])

                if not df_filtrado.empty:
                    df_exibir = df_filtrado[["data", "hora", "colaborador", "tipo", "litros", "codigo_auditoria"]]

                    # --- CARDS DE RESUMO ---
                    st.subheader("📈 Resumo do Período")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total de Registros", len(df_exibir))
                    m2.metric("Colaboradores Ativos", df_exibir["colaborador"].nunique())
                    m3.metric("Tipos Distintos", df_exibir["tipo"].nunique())

                    # Tabela de consumo por tipo
                    resumo_tipo = df_exibir.groupby("tipo").size().reset_index(name="Quantidade")
                    st.write("**Consumo por Tipo:**")
                    st.dataframe(resumo_tipo, use_container_width=True, hide_index=True)

                    # --- GRÁFICOS ---
                    st.subheader("📊 Gráficos")
                    gc1, gc2 = st.columns(2)
                    with gc1:
                        st.write("**Registros por Tipo**")
                        st.bar_chart(df_exibir["tipo"].value_counts())
                    with gc2:
                        st.write("**Top 10 Colaboradores**")
                        st.bar_chart(df_exibir["colaborador"].value_counts().head(10))

                    # --- FILTROS DETALHADOS ---
                    st.subheader("🔎 Filtrar Detalhes")
                    fc1, fc2 = st.columns(2)
                    with fc1:
                        filtro_tipo = st.multiselect(
                            "Filtrar por Tipo:",
                            options=sorted(df_exibir["tipo"].unique()),
                            default=sorted(df_exibir["tipo"].unique()),
                        )
                    with fc2:
                        filtro_colab = st.multiselect(
                            "Filtrar por Colaborador:",
                            options=sorted(df_exibir["colaborador"].unique()),
                            default=sorted(df_exibir["colaborador"].unique()),
                        )

                    df_final = df_exibir[
                        df_exibir["tipo"].isin(filtro_tipo)
                        & df_exibir["colaborador"].isin(filtro_colab)
                    ]
                    st.write(f"Exibindo **{len(df_final)}** de {len(df_exibir)} registros.")
                    st.dataframe(df_final, use_container_width=True, hide_index=True)

                    # --- EXPORTAÇÃO (3 abas no Excel) ---
                    excel_data = gerar_excel(df_exibir, d_inicio, d_fim)
                    st.download_button(
                        label="📥 BAIXAR EXCEL (Resumo + Detalhes)",
                        data=excel_data,
                        file_name=f"Medicao_{d_inicio.strftime('%d_%m_%Y')}_a_{d_fim.strftime('%d_%m_%Y')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )
                else:
                    st.warning("Nenhum registro encontrado para este período.")
            else:
                st.warning("O banco de dados de registros está vazio.")
        except Exception as e:
            st.error(f"Erro ao gerar relatório: {e}")

# ==========================================
# TELA 2: TOTEM DIGITAL (COLABORADORES)
# ==========================================
else:
    st.title("🚀 Registro Digital - Refeitório")
    st.markdown("---")

    if st.session_state.mostrar_sucesso:
        st.success("✅ Registro concluído com sucesso! O Totem está pronto para o próximo colaborador.")
        st.balloons()
        st.session_state.mostrar_sucesso = False

    dados_usuarios = buscar_dados_colaboradores()
    nomes_lista = sorted([u["nome"] for u in dados_usuarios])
    nome_selecionado = st.selectbox(
        "IDENTIFIQUE-SE:",
        ["➕ NOVO CADASTRO..."] + nomes_lista,
        index=None,
        key=st.session_state.chave_identificacao,
    )

    if st.session_state.ultimo_nome != nome_selecionado:
        st.session_state.usuario_autenticado = False
        st.session_state.ultimo_nome = nome_selecionado

    # --- FLUXO 1: NOVO CADASTRO ---
    if nome_selecionado == "➕ NOVO CADASTRO...":
        st.info("📝 Preencha os dados abaixo e crie sua senha de acesso.")

        with st.form("form_cadastro"):
            n_nome = st.text_input("Nome Completo (Nome e Sobrenome):").strip().upper()
            n_empresa = st.text_input("Empresa:").strip().upper()
            n_senha = st.text_input("Crie uma Senha de Acesso (Ex: 1234):", type="password").strip()
            btn_salvar = st.form_submit_button("💾 SALVAR CADASTRO", type="primary", use_container_width=True)

        if btn_salvar:
            if len(n_nome.split()) < 2:
                st.error("⚠️ Digite o nome completo.")
            elif not n_empresa or not n_senha:
                st.error("⚠️ Todos os campos, incluindo a Senha, são obrigatórios.")
            elif n_nome in nomes_lista:
                st.warning("⚠️ Este nome já está cadastrado.")
            else:
                try:
                    supabase.table("colaboradores").insert({
                        "nome": n_nome,
                        "empresa": n_empresa,
                        "senha": hash_senha(n_senha),  # ✅ Salva como hash
                    }).execute()
                    buscar_dados_colaboradores.clear()  # Invalida cache após novo cadastro
                    st.session_state.mostrar_sucesso = True
                    st.session_state.chave_identificacao = str(uuid.uuid4())
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    # --- FLUXO 2: AUTENTICAÇÃO E REGISTRO ---
    elif nome_selecionado:
        colab_info = next((u for u in dados_usuarios if u["nome"] == nome_selecionado), None)
        senha_db = str(colab_info["senha"]).strip() if colab_info and colab_info.get("senha") else None

        if not st.session_state.usuario_autenticado:
            with st.form("form_login"):
                st.warning(f"Olá, **{nome_selecionado}**! Digite sua senha para liberar o totem.")
                senha_digitada = st.text_input("Digite sua Senha:", type="password")
                btn_login = st.form_submit_button("CONFIRMAR IDENTIDADE", type="primary")

            if btn_login:
                if verificar_senha(senha_digitada, senha_db):
                    st.session_state.usuario_autenticado = True
                    atualizar_atividade()
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta! Tente novamente.")

        if st.session_state.usuario_autenticado:

            # TELA A: ESCOLHA DO ITEM
            if not st.session_state.item_selecionado:
                c_bv, c_sair = st.columns([4, 1])
                with c_bv:
                    st.write(f"### Bem-vindo(a), **{nome_selecionado}**!")
                with c_sair:
                    if st.button("🚪 Sair", use_container_width=True, help="Encerrar sessão"):
                        resetar_sessao()
                        st.rerun()

                # Info de horários visível antes da escolha
                st.caption(
                    f"⏰ Horário atual (MT): **{hora_local().strftime('%H:%M')}** "
                    "| 🍽️ Almoço: 10h–14h | 🌙 Jantar: 20h–00h"
                )
                st.markdown("---")

                c1, c2, c3, c4, c5 = st.columns(5)
                with c1:
                    if st.button("☕\nCAFÉ", use_container_width=True):
                        st.session_state.item_selecionado = "CAFÉ"
                        st.rerun()
                with c2:
                    if st.button("🍵\nCHÁ", use_container_width=True):
                        st.session_state.item_selecionado = "CHÁ"
                        st.rerun()
                with c3:
                    if st.button("🍱\nMARMITA", use_container_width=True):
                        st.session_state.item_selecionado = "MARMITA"
                        st.rerun()
                with c4:
                    p_a, m_a = verificar_regras_refeicao(nome_selecionado, "ALMOÇO")
                    if st.button("🍽️\nALMOÇO", disabled=not p_a, use_container_width=True):
                        st.session_state.item_selecionado = "ALMOÇO"
                        st.rerun()
                    if not p_a:
                        st.caption(m_a)
                with c5:
                    p_j, m_j = verificar_regras_refeicao(nome_selecionado, "JANTAR")
                    if st.button("🌙\nJANTAR", disabled=not p_j, use_container_width=True):
                        st.session_state.item_selecionado = "JANTAR"
                        st.rerun()
                    if not p_j:
                        st.caption(m_j)

            # TELA B: QUANTIDADES E CONFIRMAÇÃO
            else:
                item = st.session_state.item_selecionado
                st.warning(f"**Registrando: {item}**")

                with st.form("form_registro", clear_on_submit=False):
                    if item in ["CAFÉ", "CHÁ"]:
                        st.write("**Quantas garrafas de cada tamanho você está levando?**")
                        l1, l2, l3, l4 = st.columns(4)
                        with l1: q05 = st.number_input("Garrafa 0.5 L", 0, 10, 0)
                        with l2: q10 = st.number_input("Garrafa 1.0 L", 0, 10, 0)
                        with l3: q15 = st.number_input("Garrafa 1.5 L", 0, 10, 0)
                        with l4: q18 = st.number_input("Garrafa 1.8 L", 0, 10, 0)

                        l5, l6, l7 = st.columns(3)
                        with l5: q20 = st.number_input("Garrafa 2.0 L", 0, 10, 0)
                        with l6: q25 = st.number_input("Garrafa 2.5 L", 0, 10, 0)
                        with l7: q35 = st.number_input("Garrafa 3.5 L", 0, 10, 0)

                        st.write("**Outro tamanho de garrafa?**")
                        c_out1, c_out2 = st.columns(2)
                        with c_out1: litro_outro = st.number_input("Tamanho (Litros):", 0.0, 10.0, 0.0, step=0.1)
                        with c_out2: qtd_outro = st.number_input("Quantidade dessa garrafa:", 0, 10, 0)

                    elif item == "MARMITA":
                        qm = st.number_input("Quantidade de Marmitas:", 1, 10, 1)
                    else:
                        st.info("Regra Corporativa: Limite de 1 unidade por pessoa/turno.")

                    st.markdown("---")
                    assinatura = st.checkbox("Declaro e confirmo a retirada dos itens preenchidos acima.")

                    c_can, c_con = st.columns(2)
                    with c_can:
                        btn_cancelar = st.form_submit_button("❌ CANCELAR E VOLTAR", use_container_width=True)
                    with c_con:
                        btn_confirmar = st.form_submit_button("✅ CONFIRMAR REGISTRO", type="primary", use_container_width=True)

                if btn_cancelar:
                    st.session_state.item_selecionado = None
                    st.rerun()

                if btn_confirmar:
                    lista_final = []
                    if item in ["CAFÉ", "CHÁ"]:
                        for _ in range(q05): lista_final.append("0.5 L")
                        for _ in range(q10): lista_final.append("1.0 L")
                        for _ in range(q15): lista_final.append("1.5 L")
                        for _ in range(q18): lista_final.append("1.8 L")
                        for _ in range(q20): lista_final.append("2.0 L")
                        for _ in range(q25): lista_final.append("2.5 L")
                        for _ in range(q35): lista_final.append("3.5 L")
                        for _ in range(qtd_outro):
                            if litro_outro > 0:
                                lista_final.append(f"{litro_outro} L")
                    elif item == "MARMITA":
                        for _ in range(qm): lista_final.append("1 UN")
                    else:
                        lista_final.append("1 UN")

                    if len(lista_final) == 0:
                        st.error("⚠️ Adicione a quantidade antes de confirmar.")
                    elif not assinatura:
                        st.error("⚠️ Você precisa marcar a caixinha declarando a retirada antes de confirmar.")
                    else:
                        try:
                            inserir_registros(nome_selecionado, item, lista_final)
                            st.session_state.mostrar_sucesso = True
                            resetar_sessao()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")
