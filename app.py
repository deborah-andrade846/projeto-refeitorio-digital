import streamlit as st
from supabase import create_client, Client
from datetime import datetime, timedelta
import pandas as pd
import uuid
import io

# 1. CONFIGURAÇÃO DA PÁGINA
st.set_page_config(page_title="Totem Aura Apoena", layout="centered")

# --- OCULTAR MENU E RODAPÉ DO STREAMLIT ---
esconder_menu = """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    </style>
    """
st.markdown(esconder_menu, unsafe_allow_html=True)

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

def hora_local():
    # Fuso de MT (UTC-4)
    return datetime.utcnow() - timedelta(hours=4)

def buscar_dados_colaboradores():
    try:
        res = supabase.table("colaboradores").select("nome, senha").execute()
        return res.data
    except:
        return []

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
        res = supabase.table("registros").select("id").eq("colaborador", nome).eq("data", data_hoje).eq("tipo", tipo_refeicao).limit(1).execute()
        if res.data:
            return False, f"Bloqueado: {tipo_refeicao} já consumido hoje."
    except:
        pass
    return True, ""

# --- ESTADO DO SISTEMA ---
if 'item_selecionado' not in st.session_state:
    st.session_state.item_selecionado = None

if 'usuario_autenticado' not in st.session_state:
    st.session_state.usuario_autenticado = False

if 'chave_identificacao' not in st.session_state:
    st.session_state.chave_identificacao = str(uuid.uuid4())

if 'mostrar_sucesso' not in st.session_state:
    st.session_state.mostrar_sucesso = False


# ==========================================
# CONTROLE DE NAVEGAÇÃO (BARRA LATERAL)
# ==========================================
st.sidebar.markdown("---")
modo_admin = st.sidebar.checkbox("Acessar Portal de Medição")
senha_admin_ok = False

if modo_admin:
    pw_admin = st.sidebar.text_input("Senha Admin:", type="password")
    if pw_admin == "Aura@2026":
        senha_admin_ok = True
    elif pw_admin != "":
        st.sidebar.error("Senha incorreta!")


# ==========================================
# TELA 1: PORTAL DE MEDIÇÃO (ADMINISTRAÇÃO)
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
                df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y').dt.date
                mask = (df['data_dt'] >= d_inicio) & (df['data_dt'] <= d_fim)
                df_filtrado = df.loc[mask].drop(columns=['data_dt'])
                
                if not df_filtrado.empty:
                    st.write(f"Encontrados: {len(df_filtrado)} registros neste período.")
                    df_exibir = df_filtrado[["data", "hora", "colaborador", "tipo", "litros", "codigo_auditoria"]]
                    st.dataframe(df_exibir, use_container_width=True)
                    
                    output = io.BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        df_exibir.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 BAIXAR EXCEL DO PERÍODO", 
                        data=output.getvalue(), 
                        file_name=f"Medicao_{d_inicio.strftime('%d_%m_%Y')}_a_{d_fim.strftime('%d_%m_%Y')}.xlsx", 
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", 
                        use_container_width=True
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

    # Verifica se o status de sucesso do registro anterior foi ativado
    if st.session_state.mostrar_sucesso:
        st.success("✅ Registro concluído com sucesso! O Totem está pronto para o próximo colaborador.")
        st.balloons()
        # Limpa o status para não repetir a animação se a pessoa clicar em outra coisa
        st.session_state.mostrar_sucesso = False

    dados_usuarios = buscar_dados_colaboradores()
    nomes_lista = sorted([u["nome"] for u in dados_usuarios])
    nome_selecionado = st.selectbox("IDENTIFIQUE-SE:", ["➕ NOVO CADASTRO..."] + nomes_lista, index=None, key=st.session_state.chave_identificacao)

    if 'ultimo_nome' not in st.session_state or st.session_state.ultimo_nome != nome_selecionado:
        st.session_state.usuario_autenticado = False
        st.session_state.ultimo_nome = nome_selecionado

    # --- FLUXO 1: NOVO CADASTRO ---
    if nome_selecionado == "➕ NOVO CADASTRO...":
        st.info("📝 Preencha os dados abaixo e crie sua senha de acesso.")
        
        n_nome = st.text_input("Nome Completo (Nome e Sobrenome):").strip().upper()
        n_empresa = st.text_input("Empresa:").strip().upper()
        n_senha = st.text_input("Crie uma Senha de Acesso (Ex: 1234):", type="password").strip()
        
        if st.button("💾 SALVAR CADASTRO", type="primary", use_container_width=True):
            if len(n_nome.split()) < 2:
                st.error("⚠️ Digite o nome completo.")
            elif n_empresa == "" or n_senha == "":
                st.error("⚠️ Todos os campos, incluindo a Senha, são obrigatórios.")
            elif n_nome in nomes_lista:
                st.warning("⚠️ Este nome já está cadastrado.")
            else:
                try:
                    supabase.table("colaboradores").insert({
                        "nome": n_nome, 
                        "empresa": n_empresa, 
                        "senha": n_senha
                    }).execute()
                    
                    st.session_state.mostrar_sucesso = True
                    st.session_state.chave_identificacao = str(uuid.uuid4())
                    st.rerun()
                    
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}. Verifique a coluna 'senha' no Supabase.")

    # --- FLUXO 2: VALIDAÇÃO POR SENHA E REGISTRO ---
    elif nome_selecionado:
        colab_info = next((u for u in dados_usuarios if u["nome"] == nome_selecionado), None)
        senha_db = str(colab_info["senha"]).strip() if colab_info and colab_info.get("senha") else None

        if not st.session_state.usuario_autenticado:
            st.warning(f"Olá {nome_selecionado}, digite sua senha para liberar o totem.")
            senha_digitada = st.text_input("Digite sua Senha:", type="password")
            
            if st.button("CONFIRMAR IDENTIDADE"):
                if senha_digitada.strip() == senha_db:
                    st.session_state.usuario_autenticado = True
                    st.rerun()
                else:
                    st.error("❌ Senha incorreta! Tente novamente.")

        if st.session_state.usuario_autenticado:
            # TELA A: ESCOLHA DO ITEM
            if not st.session_state.item_selecionado:
                st.write(f"### Bem-vindo(a), **{nome_selecionado}**!")
                c1, c2, c3, c4, c5 = st.columns(5)
                
                with c1: 
                    if st.button("☕\nCAFÉ"): 
                        st.session_state.item_selecionado = "CAFÉ"
                        st.rerun()
                with c2: 
                    if st.button("🍵\nCHÁ"): 
                        st.session_state.item_selecionado = "CHÁ"
                        st.rerun()
                with c3: 
                    if st.button("🍱\nMARMITA"): 
                        st.session_state.item_selecionado = "MARMITA"
                        st.rerun()
                with c4:
                    p_a, m_a = verificar_regras_refeicao(nome_selecionado, "ALMOÇO")
                    if st.button("🍽️\nALMOÇO", disabled=not p_a): 
                        st.session_state.item_selecionado = "ALMOÇO"
                        st.rerun()
                    if not p_a: st.caption(m_a)
                with c5:
                    p_j, m_j = verificar_regras_refeicao(nome_selecionado, "JANTAR")
                    if st.button("🌙\nJANTAR", disabled=not p_j): 
                        st.session_state.item_selecionado = "JANTAR"
                        st.rerun()
                    if not p_j: st.caption(m_j)
                    
            # TELA B: QUANTIDADES E CONFIRMAÇÃO
            else:
                item = st.session_state.item_selecionado
                st.warning(f"**Registrando: {item}**")
                lista_final = []
                
                if item in ["CAFÉ", "CHÁ"]:
                    st.write("**Quantas garrafas de cada tamanho você está levando?**")
                    l1, l2, l3, l4 = st.columns(4)
                    with l1: 
                        q05 = st.number_input("Garrafa 0.5 L", 0, 10, 0)
                        for _ in range(q05): lista_final.append("0.5 L")
                    with l2: 
                        q10 = st.number_input("Garrafa 1.0 L", 0, 10, 0)
                        for _ in range(q10): lista_final.append("1.0 L")
                    with l3: 
                        q15 = st.number_input("Garrafa 1.5 L", 0, 10, 0)
                        for _ in range(q15): lista_final.append("1.5 L")
                    with l4: 
                        q18 = st.number_input("Garrafa 1.8 L", 0, 10, 0)
                        for _ in range(q18): lista_final.append("1.8 L")
                    
                    l5, l6, l7 = st.columns(3)
                    with l5: 
                        q20 = st.number_input("Garrafa 2.0 L", 0, 10, 0)
                        for _ in range(q20): lista_final.append("2.0 L")
                    with l6: 
                        q25 = st.number_input("Garrafa 2.5 L", 0, 10, 0)
                        for _ in range(q25): lista_final.append("2.5 L")
                    with l7: 
                        q35 = st.number_input("Garrafa 3.5 L", 0, 10, 0)
                        for _ in range(q35): lista_final.append("3.5 L")
                        
                    st.write("**Outro tamanho de garrafa?**")
                    c_out1, c_out2 = st.columns(2)
                    with c_out1: litro_outro = st.number_input("Tamanho (Litros):", 0.0, 10.0, 0.0, step=0.1)
                    with c_out2: 
                        qtd_outro = st.number_input("Quantidade dessa garrafa:", 0, 10, 0)
                        for _ in range(qtd_outro):
                            if litro_outro > 0: lista_final.append(f"{litro_outro} L")

                elif item == "MARMITA":
                    qm = st.number_input("Quantidade de Marmitas:", 1, 10, 1)
                    for _ in range(qm): lista_final.append("1 UN")
                else:
                    st.info("Regra Corporativa: Limite de 1 unidade por pessoa/turno.")
                    lista_final.append("1 UN")

                st.markdown("---")
                total_itens = len(lista_final)
                if total_itens == 0:
                    st.error("⚠️ Adicione a quantidade antes de confirmar.")
                    
                assinatura = st.checkbox(f"Confirmo a retirada de {total_itens} item(ns)", disabled=(total_itens==0))
                
                c_can, c_con = st.columns(2)
                with c_can:
                    if st.button("❌ CANCELAR E VOLTAR", use_container_width=True): 
                        st.session_state.item_selecionado = None
                        st.rerun()
                with c_con:
                    if st.button("✅ CONFIRMAR REGISTRO", type="primary", use_container_width=True, disabled=not assinatura):
                        try:
                            cod = str(uuid.uuid4())[:8].upper()
                            agora_mt = hora_local()
                            dt = agora_mt.strftime("%d/%m/%Y")
                            hr = agora_mt.strftime("%H:%M:%S")
                            
                            for lit in lista_final:
                                supabase.table("registros").insert({
                                    "data": dt, 
                                    "hora": hr, 
                                    "colaborador": nome_selecionado, 
                                    "tipo": item, 
                                    "litros": lit, 
                                    "codigo_auditoria": cod
                                }).execute()
                                
                            # O SEGREDO DO "CLIQUE ÚNICO" ESTÁ AQUI:
                            # 1. Ativa a mensagem de sucesso
                            st.session_state.mostrar_sucesso = True
                            
                            # 2. Desloga o usuário e esvazia o carrinho
                            st.session_state.item_selecionado = None
                            st.session_state.usuario_autenticado = False 
                            st.session_state.ultimo_nome = None
                            
                            # 3. Muda a 'chave' do selectbox para forçá-lo a zerar e exibir "IDENTIFIQUE-SE"
                            st.session_state.chave_identificacao = str(uuid.uuid4())
                            
                            # 4. Recarrega a tela instantaneamente (agora ela vai abrir limpa e soltar os balões!)
                            st.rerun()
                            
                        except Exception as e: 
                            st.error(f"Erro: {e}")
