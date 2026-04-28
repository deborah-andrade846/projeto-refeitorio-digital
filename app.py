import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import uuid
import io
import hashlib
import time
try:
    import pytz
    _TZ_CUIABA = pytz.timezone("America/Cuiaba")
    _USE_PYTZ = True
except ImportError:
    _USE_PYTZ = False

# ==========================================
# 1. CONFIGURAÇÃO DA PÁGINA
# ==========================================
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

# --- Ocultar sidebar e rodapé do Streamlit por padrão ---
# O portal admin é acessado via parâmetro ?admin=1 na URL
st.markdown("""
    <style>
    /* Oculta sidebar no modo totem */
    [data-testid="stSidebar"] { display: none !important; }
    /* Oculta footer do Streamlit */
    footer { visibility: hidden; }
    /* Botões de ação maiores para toque em tablet */
    div[data-testid="stButton"] > button {
        min-height: 3.5rem;
        font-size: 1.05rem;
        font-weight: 600;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. MODO ADMIN — via parâmetro de URL (?admin=1)
# ==========================================
params = st.query_params
MODO_ADMIN_URL = params.get("admin", "0") == "1"

# Se for modo admin, reexibir sidebar
if MODO_ADMIN_URL:
    st.markdown("""
        <style>
        [data-testid="stSidebar"] { display: block !important; }
        </style>
    """, unsafe_allow_html=True)

# ==========================================
# 3. CONEXÃO COM O BANCO DE DADOS
# ==========================================
@st.cache_resource
def init_connection():
    try:
        url = st.secrets["SUPABASE_URL"]
        key = st.secrets["SUPABASE_KEY"]
        return create_client(url, key)
    except Exception as e:
        st.error("Erro nos Secrets do Streamlit. Verifique a configuração.")
        return None

supabase = init_connection()

# ==========================================
# 4. CONSTANTES
# ==========================================
TIMEOUT_MINUTOS = 2          # Sessão expira após 2 min de inatividade
AVISO_TIMEOUT_SEG = 30       # Aviso visual nos últimos 30 segundos
MAX_TENTATIVAS_SENHA = 5     # Bloqueia após 5 erros de senha
DATA_CORTE_FALLBACK = datetime(2025, 12, 31)  # Fallback texto puro encerra nesta data

# ==========================================
# 5. FUNÇÕES DE SEGURANÇA
# ==========================================

def hash_senha(senha: str) -> str:
    """Gera hash SHA-256 da senha."""
    return hashlib.sha256(senha.strip().encode()).hexdigest()

def verificar_senha(senha_digitada: str, senha_db: str) -> bool:
    """
    Verifica senha com suporte a migração:
    - Aceita senhas já em hash (novos cadastros)
    - Aceita senhas em texto puro apenas até DATA_CORTE_FALLBACK
    """
    if not senha_db:
        return False
    if senha_db == hash_senha(senha_digitada):
        return True
    # Fallback: suporte a senhas antigas (texto puro) — expira em DATA_CORTE_FALLBACK
    if datetime.now() <= DATA_CORTE_FALLBACK:
        if senha_db == senha_digitada.strip():
            return True
    return False

# ==========================================
# 6. FUNÇÕES DE SESSÃO / TIMEOUT
# ==========================================

def segundos_restantes() -> float:
    """Retorna segundos restantes antes do timeout. Negativo = expirou."""
    if "ultimo_ativo" not in st.session_state:
        return TIMEOUT_MINUTOS * 60
    decorrido = time.time() - st.session_state.ultimo_ativo
    return (TIMEOUT_MINUTOS * 60) - decorrido

def verificar_timeout() -> bool:
    """Retorna True se a sessão expirou por inatividade."""
    return segundos_restantes() <= 0

def atualizar_atividade():
    """Atualiza o timestamp de última atividade."""
    st.session_state.ultimo_ativo = time.time()

def resetar_sessao():
    """Reseta todos os estados de sessão do colaborador."""
    st.session_state.usuario_autenticado = False
    st.session_state.item_selecionado = None
    st.session_state.ultimo_nome = None
    st.session_state.chave_identificacao = str(uuid.uuid4())
    st.session_state.tentativas_senha = 0
    st.session_state.pop("ultimo_ativo", None)

# ==========================================
# 7. FUNÇÕES DE DADOS
# ==========================================

@st.cache_data(ttl=60)
def buscar_dados_colaboradores():
    """Busca colaboradores com cache de 60 segundos."""
    try:
        res = supabase.table("colaboradores").select("nome, senha, ativo").execute()
        # Exibe apenas colaboradores ativos (campo 'ativo' = True ou ausente)
        return [u for u in res.data if u.get("ativo", True) is not False]
    except:
        return []

@st.cache_data(ttl=60)
def buscar_todos_colaboradores():
    """Busca todos os colaboradores (incluindo inativos) para o admin."""
    try:
        res = supabase.table("colaboradores").select("*").execute()
        return res.data
    except:
        return []

def hora_local() -> datetime:
    """Retorna hora atual no fuso de Mato Grosso (America/Cuiaba)."""
    if _USE_PYTZ:
        return datetime.now(_TZ_CUIABA).replace(tzinfo=None)
    # Fallback sem pytz (UTC-4 fixo)
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
# 8. INICIALIZAÇÃO DO ESTADO
# ==========================================
defaults = {
    "item_selecionado": None,
    "usuario_autenticado": False,
    "chave_identificacao": str(uuid.uuid4()),
    "mostrar_sucesso": False,
    "ultimo_nome": None,
    "tentativas_senha": 0,
}
for key, val in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = val

# ==========================================
# 9. TIMEOUT AUTOMÁTICO
# ==========================================
if st.session_state.usuario_autenticado and verificar_timeout():
    resetar_sessao()
    st.warning("⏱️ Sessão encerrada por inatividade. Identifique-se novamente.")

if st.session_state.usuario_autenticado:
    atualizar_atividade()

# ==========================================
# 10. BARRA LATERAL — ACESSO ADMIN (apenas via ?admin=1)
# ==========================================
senha_admin_ok = False

if MODO_ADMIN_URL:
    st.sidebar.image("https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Aura_Minerals_logo.svg/320px-Aura_Minerals_logo.svg.png", use_container_width=True)
    st.sidebar.markdown("---")
    pw_admin = st.sidebar.text_input("🔑 Senha Admin:", type="password")
    senha_admin_correta = st.secrets.get("ADMIN_PASSWORD", "")

    if not senha_admin_correta:
        st.sidebar.error("⚠️ ADMIN_PASSWORD não configurado nos secrets.")
    elif pw_admin == senha_admin_correta:
        senha_admin_ok = True
    elif pw_admin:
        st.sidebar.error("❌ Senha incorreta!")

# ==========================================
# TELA 1: PORTAL ADMINISTRATIVO
# ==========================================
if senha_admin_ok:
    st.title("📊 Portal Administrativo — Medição")
    st.markdown("---")

    aba_dados, aba_colaboradores = st.tabs(["📈 Registros e Relatórios", "👥 Gestão de Colaboradores"])

    # --- ABA 1: REGISTROS ---
    with aba_dados:
        col_i, col_f = st.columns(2)
        with col_i:
            d_inicio = st.date_input("Data Início:", hora_local() - timedelta(days=30), format="DD/MM/YYYY")
        with col_f:
            d_fim = st.date_input("Data Fim:", hora_local(), format="DD/MM/YYYY")

        if st.button("🔍 CARREGAR DADOS DO PERÍODO", use_container_width=True):
            try:
                # ✅ Filtro feito no Supabase — não carrega tabela inteira
                d_i_str = d_inicio.strftime("%d/%m/%Y")
                d_f_str = d_fim.strftime("%d/%m/%Y")

                # Gera lista de datas do período para filtrar (formato dd/mm/yyyy)
                delta = (d_fim - d_inicio).days
                datas_periodo = [
                    (d_inicio + timedelta(days=i)).strftime("%d/%m/%Y")
                    for i in range(delta + 1)
                ]

                res_adm = (
                    supabase.table("registros")
                    .select("*")
                    .in_("data", datas_periodo)
                    .execute()
                )
                df = pd.DataFrame(res_adm.data)

                if not df.empty:
                    df_exibir = df[["data", "hora", "colaborador", "tipo", "litros", "codigo_auditoria"]]

                    # --- CARDS DE RESUMO ---
                    st.subheader("📈 Resumo do Período")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total de Registros", len(df_exibir))
                    m2.metric("Colaboradores Ativos", df_exibir["colaborador"].nunique())
                    m3.metric("Tipos Distintos", df_exibir["tipo"].nunique())

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

                    # --- EXPORTAÇÃO ---
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
            except Exception as e:
                st.error(f"Erro ao gerar relatório: {e}")

    # --- ABA 2: GESTÃO DE COLABORADORES ---
    with aba_colaboradores:
        st.subheader("👥 Colaboradores Cadastrados")

        todos_colab = buscar_todos_colaboradores()

        if not todos_colab:
            st.info("Nenhum colaborador cadastrado.")
        else:
            df_colab = pd.DataFrame(todos_colab)
            colunas_exibir = [c for c in ["nome", "empresa", "ativo"] if c in df_colab.columns]
            st.dataframe(df_colab[colunas_exibir], use_container_width=True, hide_index=True)

        st.markdown("---")

        # Resetar senha
        st.write("**🔑 Resetar Senha de Colaborador**")
        nomes_admin = [u["nome"] for u in todos_colab] if todos_colab else []
        col_r1, col_r2 = st.columns(2)
        with col_r1:
            colab_reset = st.selectbox("Colaborador:", [""] + nomes_admin, key="sel_reset")
        with col_r2:
            nova_senha = st.text_input("Nova Senha:", type="password", key="inp_nova_senha")

        if st.button("🔄 RESETAR SENHA", use_container_width=True):
            if not colab_reset or not nova_senha:
                st.error("Selecione o colaborador e digite a nova senha.")
            else:
                try:
                    supabase.table("colaboradores").update(
                        {"senha": hash_senha(nova_senha)}
                    ).eq("nome", colab_reset).execute()
                    buscar_dados_colaboradores.clear()
                    buscar_todos_colaboradores.clear()
                    st.success(f"✅ Senha de **{colab_reset}** resetada com sucesso.")
                except Exception as e:
                    st.error(f"Erro: {e}")

        st.markdown("---")

        # Ativar / Desativar colaborador
        st.write("**🚫 Ativar / Desativar Colaborador**")
        col_a1, col_a2 = st.columns(2)
        with col_a1:
            colab_ativar = st.selectbox("Colaborador:", [""] + nomes_admin, key="sel_ativar")
        with col_a2:
            acao_ativo = st.radio("Ação:", ["Ativar", "Desativar"], horizontal=True)

        if st.button("✅ APLICAR ALTERAÇÃO", use_container_width=True):
            if not colab_ativar:
                st.error("Selecione um colaborador.")
            else:
                try:
                    novo_status = acao_ativo == "Ativar"
                    supabase.table("colaboradores").update(
                        {"ativo": novo_status}
                    ).eq("nome", colab_ativar).execute()
                    buscar_dados_colaboradores.clear()
                    buscar_todos_colaboradores.clear()
                    st.success(f"✅ Colaborador **{colab_ativar}** {'ativado' if novo_status else 'desativado'}.")
                except Exception as e:
                    st.error(f"Erro: {e}")

# ==========================================
# TELA 2: TOTEM DIGITAL (COLABORADORES)
# ==========================================
elif not MODO_ADMIN_URL:
    st.title("🚀 Registro Digital — Refeitório")
    st.markdown("---")

    # --- AVISO DE TIMEOUT IMINENTE ---
    if st.session_state.usuario_autenticado:
        seg_rest = segundos_restantes()
        if 0 < seg_rest <= AVISO_TIMEOUT_SEG:
            st.warning(f"⚠️ Sessão encerrará em **{int(seg_rest)} segundos** por inatividade.")

    # --- FEEDBACK PÓS-REGISTRO ---
    if st.session_state.mostrar_sucesso:
        st.success("✅ Registro concluído com sucesso! O Totem está pronto para o próximo colaborador.")
        st.balloons()
        st.session_state.mostrar_sucesso = False
        time.sleep(3)
        st.rerun()

    dados_usuarios = buscar_dados_colaboradores()
    nomes_lista = sorted([u["nome"] for u in dados_usuarios])
    nome_selecionado = st.selectbox(
        "IDENTIFIQUE-SE:",
        ["➕ NOVO CADASTRO..."] + nomes_lista,
        index=None,
        placeholder="Toque aqui e selecione seu nome...",
        key=st.session_state.chave_identificacao,
    )

    if st.session_state.ultimo_nome != nome_selecionado:
        st.session_state.usuario_autenticado = False
        st.session_state.tentativas_senha = 0
        st.session_state.ultimo_nome = nome_selecionado

    # --- FLUXO 1: NOVO CADASTRO ---
    if nome_selecionado == "➕ NOVO CADASTRO...":
        st.info("📝 Preencha os dados abaixo e crie sua senha de acesso.")

        with st.form("form_cadastro"):
            n_nome = st.text_input("Nome Completo (Nome e Sobrenome):").strip().upper()
            n_empresa = st.text_input("Empresa:").strip().upper()
            n_senha = st.text_input(
                "Crie uma Senha de Acesso (Ex: 1234):",
                type="password",
                help="Dica: use apenas números para facilitar a digitação no tablet."
            ).strip()
            btn_salvar = st.form_submit_button("💾 SALVAR CADASTRO", type="primary", use_container_width=True)

        if btn_salvar:
            if len(n_nome.split()) < 2:
                st.error("⚠️ Digite o nome completo (nome e sobrenome).")
            elif not n_empresa or not n_senha:
                st.error("⚠️ Todos os campos são obrigatórios.")
            elif n_nome in nomes_lista:
                st.warning("⚠️ Este nome já está cadastrado.")
            else:
                try:
                    supabase.table("colaboradores").insert({
                        "nome": n_nome,
                        "empresa": n_empresa,
                        "senha": hash_senha(n_senha),
                        "ativo": True,
                    }).execute()
                    buscar_dados_colaboradores.clear()
                    st.session_state.mostrar_sucesso = True
                    st.session_state.chave_identificacao = str(uuid.uuid4())
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")

    # --- FLUXO 2: AUTENTICAÇÃO E REGISTRO ---
    elif nome_selecionado:
        colab_info = next((u for u in dados_usuarios if u["nome"] == nome_selecionado), None)
        senha_db = str(colab_info["senha"]).strip() if colab_info and colab_info.get("senha") else None

        # --- Bloqueio por tentativas ---
        tentativas = st.session_state.get("tentativas_senha", 0)
        if tentativas >= MAX_TENTATIVAS_SENHA:
            st.error(f"🔒 Acesso bloqueado após {MAX_TENTATIVAS_SENHA} tentativas incorretas. Procure o responsável.")
        elif not st.session_state.usuario_autenticado:
            with st.form("form_login"):
                st.warning(f"Olá, **{nome_selecionado}**! Digite sua senha para liberar o totem.")
                if tentativas > 0:
                    st.caption(f"⚠️ {tentativas}/{MAX_TENTATIVAS_SENHA} tentativas usadas.")
                senha_digitada = st.text_input(
                    "Digite sua Senha:",
                    type="password",
                    placeholder="Somente números (ex: 1234)",
                )
                btn_login = st.form_submit_button("CONFIRMAR IDENTIDADE", type="primary", use_container_width=True)

            if btn_login:
                if verificar_senha(senha_digitada, senha_db):
                    st.session_state.usuario_autenticado = True
                    st.session_state.tentativas_senha = 0
                    atualizar_atividade()
                    st.rerun()
                else:
                    st.session_state.tentativas_senha += 1
                    restam = MAX_TENTATIVAS_SENHA - st.session_state.tentativas_senha
                    if restam > 0:
                        st.error(f"❌ Senha incorreta! Restam {restam} tentativa(s).")
                    else:
                        st.error("🔒 Acesso bloqueado. Procure o responsável.")
                    st.rerun()

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

                st.caption(
                    f"⏰ Horário (MT): **{hora_local().strftime('%H:%M')}** "
                    f"| 🍽️ Almoço: 10h–14h | 🌙 Jantar: 20h–00h"
                    f" | ⏱️ Sessão expira em {int(max(segundos_restantes(), 0) // 60)}min"
                )
                st.markdown("---")
                st.write("**O que deseja registrar?**")

                # ✅ Layout 3+2 para botões maiores e mais fáceis de tocar
                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("☕\nCAFÉ", use_container_width=True):
                        st.session_state.item_selecionado = "CAFÉ"
                        atualizar_atividade()
                        st.rerun()
                with c2:
                    if st.button("🍵\nCHÁ", use_container_width=True):
                        st.session_state.item_selecionado = "CHÁ"
                        atualizar_atividade()
                        st.rerun()
                with c3:
                    if st.button("🍱\nMARMITA", use_container_width=True):
                        st.session_state.item_selecionado = "MARMITA"
                        atualizar_atividade()
                        st.rerun()

                c4, c5 = st.columns(2)
                with c4:
                    p_a, m_a = verificar_regras_refeicao(nome_selecionado, "ALMOÇO")
                    if st.button("🍽️\nALMOÇO", disabled=not p_a, use_container_width=True):
                        st.session_state.item_selecionado = "ALMOÇO"
                        atualizar_atividade()
                        st.rerun()
                    if not p_a:
                        st.caption(m_a)
                with c5:
                    p_j, m_j = verificar_regras_refeicao(nome_selecionado, "JANTAR")
                    if st.button("🌙\nJANTAR", disabled=not p_j, use_container_width=True):
                        st.session_state.item_selecionado = "JANTAR"
                        atualizar_atividade()
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
                    assinatura = st.checkbox("✍️ Declaro e confirmo a retirada dos itens preenchidos acima.")

                    c_can, c_con = st.columns(2)
                    with c_can:
                        btn_cancelar = st.form_submit_button("❌ CANCELAR E VOLTAR", use_container_width=True)
                    with c_con:
                        btn_confirmar = st.form_submit_button("✅ CONFIRMAR REGISTRO", type="primary", use_container_width=True)

                if btn_cancelar:
                    st.session_state.item_selecionado = None
                    atualizar_atividade()
                    st.rerun()

                if btn_confirmar:
                    atualizar_atividade()
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
                        st.error("⚠️ Marque a caixinha de declaração antes de confirmar.")
                    else:
                        try:
                            inserir_registros(nome_selecionado, item, lista_final)
                            st.session_state.mostrar_sucesso = True
                            resetar_sessao()
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erro: {e}")

elif MODO_ADMIN_URL and not senha_admin_ok:
    st.title("🔐 Portal Administrativo")
    st.info("Digite a senha na barra lateral para acessar.")
