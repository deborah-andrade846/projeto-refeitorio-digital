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
# FLUXO 1: NOVO CADASTRO (Aprimorado)
# ==========================================
if nome_selecionado == "➕ NOVO CADASTRO...":
    st.info("📝 Preencha seus dados para inclusão no sistema.")
    
    # Novos campos de entrada
    novo_nome = st.text_input("Nome Completo (Obrigatório):").strip().upper()
    nova_empresa = st.text_input("Empresa (Obrigatório - Ex: AURA, SERT, G3):").strip().upper()
    nova_matricula = st.text_input("Matrícula:").strip().upper()
    
    if st.button("💾 SALVAR CADASTRO", type="primary", use_container_width=True):
        
        # VALIDAÇÃO 1: Exige pelo menos duas palavras no nome (Nome + Sobrenome)
        if len(novo_nome.split()) < 2:
            st.error("⚠️ Por favor, digite seu Nome e Sobrenome.")
            
        # VALIDAÇÃO 2: Empresa não pode ficar em branco
        elif nova_empresa == "":
            st.error("⚠️ O campo Empresa é obrigatório.")
            
        # VALIDAÇÃO 3: Evita duplicidade de nomes
        elif novo_nome in nomes:
            st.warning("⚠️ Este nome já existe na lista. Por favor, retorne e selecione-o.")
            
        # Se passar em todas as validações, salva no banco!
        else:
            try:
                # Se a matrícula estiver vazia, salvamos como "N/A" (Não se Aplica)
                matricula_final = nova_matricula if nova_matricula != "" else "N/A"
                
                dados_colaborador = {
                    "nome": novo_nome,
                    "empresa": nova_empresa,
                    "matricula": matricula_final
                }
                
                supabase.table("colaboradores").insert(dados_colaborador).execute()
                st.success("✅ Cadastro realizado com sucesso!")
                st.rerun() # Recarrega a tela para atualizar a lista
                
            except Exception as e:
                st.error(f"Erro ao salvar no banco de dados: {e}")
# ==========================================
# FLUXO 2: SELEÇÃO E CONFIRMAÇÃO (Totem Simplificado)
# ==========================================
elif nome_selecionado:
    
    # TELA A: MENU PRINCIPAL
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

    # TELA B: DETALHES E CONFIRMAÇÃO (Com Múltiplas Quantidades)
    else:
        item = st.session_state.item_selecionado
        
        st.warning("⚠️ **Confirme as quantidades do seu registro:**")
        st.write(f"**Colaborador:** {nome_selecionado}")
        st.write(f"**Item selecionado:** {item}")
        
        # Essa lista vai guardar as "linhas" que vão para o banco de dados
        lista_para_salvar = [] 
        
        # --- LÓGICA DE BEBIDAS (Múltiplas garrafas e tamanhos) ---
        if item in ["CAFÉ", "CHÁ"]:
            st.write("**Quantas garrafas de cada tamanho você está levando?**")
            
            # Contadores lado a lado
            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            with c1: qtd_05 = st.number_input("Garrafa 0.5 L", 0, 10, 0)
            with c2: qtd_10 = st.number_input("Garrafa 1.0 L", 0, 10, 0)
            with c3: qtd_15 = st.number_input("Garrafa 1.5 L", 0, 10, 0)
            with c3: qtd_15 = st.number_input("Garrafa 1.8 L", 0, 10, 0)    
            with c4: qtd_20 = st.number_input("Garrafa 2.0 L", 0, 10, 0)
            with c4: qtd_20 = st.number_input("Garrafa 2.5 L", 0, 10, 0)
            with c4: qtd_20 = st.number_input("Garrafa 3.5 L", 0, 10, 0)
            
            st.write("**Outro tamanho de garrafa?**")
            c_out1, c_out2 = st.columns(2)
            with c_out1: litro_outro = st.number_input("Tamanho (Litros):", 0.0, 10.0, 0.0, step=0.1)
            with c_out2: qtd_outro = st.number_input("Quantidade dessa garrafa:", 0, 10, 0)

            # O sistema gera uma linha no banco para CADA garrafa selecionada
            for _ in range(qtd_05): lista_para_salvar.append("0.5 L")
            for _ in range(qtd_10): lista_para_salvar.append("1.0 L")
            for _ in range(qtd_15): lista_para_salvar.append("1.5 L")
            for _ in range(qtd_20): lista_para_salvar.append("2.0 L")
            for _ in range(qtd_outro): 
                if litro_outro > 0: lista_para_salvar.append(f"{litro_outro} L")
                
        # --- LÓGICA DE MARMITA (Múltiplas quantidades) ---
        elif item == "MARMITA":
            qtd_marmitas = st.number_input("Quantidade de Marmitas:", min_value=1, max_value=10, step=1)
            for _ in range(qtd_marmitas):
                lista_para_salvar.append("1 UN") # Gera várias linhas de 1 UN
            
        # --- LÓGICA DE ALMOÇO / JANTAR (Travado em 1 unidade) ---
        else: 
            st.info("Regra Corporativa: Limite de 1 unidade por pessoa/turno.")
            lista_para_salvar.append("1 UN")

        st.markdown("---")
        
        # VALIDAÇÃO: Impede envio de carrinho vazio (ex: pessoa marcou 0 garrafas)
        total_itens = len(lista_para_salvar)
        if total_itens == 0:
            st.error("⚠️ Adicione a quantidade de garrafas antes de confirmar.")
            
        assinatura = st.checkbox(f"Declaro que estou retirando {total_itens} item(ns).", disabled=(total_itens == 0))
        
        # Botões de Ação
        c_cancela, c_confirma = st.columns(2)
        
        with c_cancela:
            if st.button("❌ CANCELAR E VOLTAR", use_container_width=True):
                st.session_state.item_selecionado = None 
                st.rerun()

        with c_confirma:
            # O botão verde só liga se a pessoa tiver escolhido algo > 0 e assinado
            if st.button("✅ CONFIRMAR REGISTRO", use_container_width=True, disabled=not assinatura, type="primary"):
                try:
                    cod_auditoria = str(uuid.uuid4())[:8].upper()
                    data_hoje = datetime.now().strftime("%d/%m/%Y")
                    hora_agora = datetime.now().strftime("%H:%M:%S")
                    
                    # Salva CADA item da lista como uma linha independente no Supabase
                    for litragem in lista_para_salvar:
                        dados_bd = {
                            "data": data_hoje,
                            "hora": hora_agora,
                            "colaborador": nome_selecionado,
                            "tipo": item,
                            "litros": litragem,
                            "codigo_auditoria": cod_auditoria
                        }
                        supabase.table("registros").insert(dados_bd).execute()
                    
                    st.success(f"✅ Registrado com sucesso! Cód: {cod_auditoria}")
                    st.session_state.item_selecionado = None
                    st.balloons()
                    
                except Exception as e:
                    st.error(f"Erro ao salvar: {e}")
