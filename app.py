import streamlit as st
import pandas as pd
from datetime import datetime, date, time
import smartsheet

st.set_page_config(page_title="Reserva de Veiculos", page_icon="car", layout="wide")

SMARTSHEET_TOKEN = "2g2PXCKnWbqmN8SHjbxA6MlxsmokO1spK6Oek"
SHEET_ID = 2989343672061828

ss_client = smartsheet.Smartsheet(SMARTSHEET_TOKEN)
ss_client.errors_as_exceptions(True)

VEICULOS = {
    "SHI-6J15": {"modelo": "Fiat Toro", "cor": "Prata"},
    "SHI-6J17": {"modelo": "Fiat Toro", "cor": "Prata"},
}

def obter_colunas():
    sheet = ss_client.Sheets.get_sheet(SHEET_ID)
    colunas = {}
    for col in sheet.columns:
        colunas[col.title] = col.id
    return colunas

def carregar_reservas():
    sheet = ss_client.Sheets.get_sheet(SHEET_ID)
    colunas = {col.id: col.title for col in sheet.columns}
    dados = []
    for row in sheet.rows:
        registro = {"row_id": row.id}
        for cell in row.cells:
            col_nome = colunas.get(cell.column_id, "")
            registro[col_nome] = cell.value
        dados.append(registro)
    df = pd.DataFrame(dados)
    if df.empty:
        return pd.DataFrame(columns=["placa", "modelo", "condutor", "destino", "data_reserva", "hora_saida", "hora_retorno", "status", "data_registro", "row_id"])
    if "Data Reserva" in df.columns:
        df["Data Reserva"] = pd.to_datetime(df["Data Reserva"], errors="coerce").dt.date
    df = df.rename(columns={
        "Placa": "placa",
        "Veiculo": "modelo",
        "Condutor": "condutor",
        "Destino": "destino",
        "Data Reserva": "data_reserva",
        "Hora Saida": "hora_saida",
        "Hora Retorno": "hora_retorno",
        "Status": "status",
        "Data Registro": "data_registro"
    })
    return df

def salvar_reserva(placa, modelo, condutor, destino, data_reserva, hora_saida, hora_retorno):
    colunas = obter_colunas()
    nova_linha = smartsheet.models.Row()
    nova_linha.to_top = True
    nova_linha.cells.append({"column_id": colunas["Placa"], "value": placa})
    nova_linha.cells.append({"column_id": colunas["Veiculo"], "value": modelo})
    nova_linha.cells.append({"column_id": colunas["Condutor"], "value": condutor})
    nova_linha.cells.append({"column_id": colunas["Destino"], "value": destino})
    nova_linha.cells.append({"column_id": colunas["Data Reserva"], "value": data_reserva.isoformat()})
    nova_linha.cells.append({"column_id": colunas["Hora Saida"], "value": hora_saida})
    nova_linha.cells.append({"column_id": colunas["Hora Retorno"], "value": hora_retorno})
    nova_linha.cells.append({"column_id": colunas["Status"], "value": "Ativa"})
    nova_linha.cells.append({"column_id": colunas["Data Registro"], "value": datetime.now().strftime("%Y-%m-%d %H:%M")})
    ss_client.Sheets.add_rows(SHEET_ID, [nova_linha])

def cancelar_reserva(row_id):
    colunas = obter_colunas()
    linha = smartsheet.models.Row()
    linha.id = int(row_id)
    linha.cells.append({"column_id": colunas["Status"], "value": "Cancelada"})
    ss_client.Sheets.update_rows(SHEET_ID, [linha])

def verificar_disponibilidade(df, placa, data_reserva):
    if df.empty:
        return True, None
    conflito = df[(df["placa"] == placa) & (df["data_reserva"] == data_reserva) & (df["status"] == "Ativa")]
    if len(conflito) > 0:
        return False, conflito.iloc[0]
    return True, None

def contar_disponibilidades(df_reservas):
    hoje = date.today()
    if df_reservas.empty:
        return len(VEICULOS)
    reservados_hoje = df_reservas[(df_reservas["data_reserva"] == hoje) & (df_reservas["status"] == "Ativa")]["placa"].unique()
    return max(0, len(VEICULOS) - len(reservados_hoje))

def contar_condutores_ativos(df_reservas):
    hoje = date.today()
    if df_reservas.empty:
        return 0
    ativos = df_reservas[(df_reservas["status"] == "Ativa") & (df_reservas["data_reserva"] >= hoje)]
    return ativos["condutor"].nunique() if not ativos.empty else 0

def contar_reservas_ativas(df_reservas):
    hoje = date.today()
    if df_reservas.empty:
        return 0
    ativas = df_reservas[(df_reservas["status"] == "Ativa") & (df_reservas["data_reserva"] >= hoje)]
    return len(ativas)

try:
    df_reservas = carregar_reservas()
except Exception as e:
    st.error(f"Erro ao conectar com Smartsheet: {e}")
    st.info("Verifique o token e o ID da planilha.")
    st.stop()

st.markdown("""
<style>
    .card {padding: 20px; border-radius: 12px; text-align: center; color: white; margin-bottom: 10px;}
    .card-azul {background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);}
    .card-verde {background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);}
    .card-laranja {background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);}
    .card-cinza {background: linear-gradient(135deg, #4b6cb7 0%, #182848 100%);}
    .card h2 {margin: 0; font-size: 2.5em;}
    .card p {margin: 5px 0 0 0; font-size: 1.1em; opacity: 0.9;}
</style>
""", unsafe_allow_html=True)

st.sidebar.title("Reserva de Veiculos")
st.sidebar.markdown("---")
pagina = st.sidebar.radio("Navegacao", ["Home", "Nova Reserva", "Reservas Ativas", "Cancelar Reserva", "Historico"])
st.sidebar.markdown("---")
st.sidebar.caption("Syngenta - Parent Seeds Operations")

if pagina == "Home":
    st.title("Frota")
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="card card-azul"><h2>{len(VEICULOS)}</h2><p>Veiculos</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card card-verde"><h2>{contar_disponibilidades(df_reservas)}</h2><p>Disponiveis</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card card-laranja"><h2>{contar_reservas_ativas(df_reservas)}</h2><p>Reservas ativas</p></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="card card-cinza"><h2>{contar_condutores_ativos(df_reservas)}</h2><p>Condutores</p></div>', unsafe_allow_html=True)
    st.markdown("---")
    st.subheader("Proximas Reservas")
    if df_reservas.empty:
        st.info("Nenhuma reserva ativa no momento.")
    else:
        df_proximas = df_reservas[(df_reservas["status"] == "Ativa") & (df_reservas["data_reserva"] >= date.today())].sort_values("data_reserva").head(10)
        if df_proximas.empty:
            st.info("Nenhuma reserva ativa no momento.")
        else:
            df_exibir = df_proximas[["placa", "modelo", "condutor", "destino", "data_reserva", "hora_saida", "hora_retorno"]].copy()
            df_exibir.columns = ["Placa", "Modelo", "Condutor", "Destino", "Data", "Saida", "Retorno"]
            df_exibir["Data"] = pd.to_datetime(df_exibir["Data"]).dt.strftime("%d/%m/%Y")
            st.dataframe(df_exibir, use_container_width=True, hide_index=True)

elif pagina == "Nova Reserva":
    st.title("Nova Reserva")
    st.markdown("---")
    col1, col2 = st.columns(2)
    with col1:
        opcoes_veiculos = [f"{placa} - {info['modelo']} ({info['cor']})" for placa, info in VEICULOS.items()]
        veiculo_selecionado = st.selectbox("Selecione o Veiculo", opcoes_veiculos)
        placa_selecionada = veiculo_selecionado.split(" - ")[0]
        modelo_selecionado = VEICULOS[placa_selecionada]["modelo"]
        condutor = st.text_input("Nome do Condutor", placeholder="Digite seu nome completo")
        destino = st.text_input("Destino", placeholder="Ex: Matao, Ribeirao Preto")
    with col2:
        data_reserva = st.date_input("Data da Reserva", min_value=date.today(), value=date.today())
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            hora_saida = st.time_input("Hora de Saida", value=None)
        with col_h2:
            hora_retorno = st.time_input("Hora de Retorno", value=None)
    st.markdown("---")
    disponivel, reserva_conflito = verificar_disponibilidade(df_reservas, placa_selecionada, data_reserva)
    if disponivel:
        st.success(f"DISPONIVEL - Veiculo {placa_selecionada} esta disponivel em {data_reserva.strftime('%d/%m/%Y')}")
    else:
        st.error(f"INDISPONIVEL - Veiculo {placa_selecionada} ja reservado em {data_reserva.strftime('%d/%m/%Y')} por: {reserva_conflito['condutor']} (Destino: {reserva_conflito['destino']})")
    botao_habilitado = disponivel and condutor.strip() != "" and destino.strip() != "" and hora_saida is not None and hora_retorno is not None
    if st.button("Confirmar Reserva", type="primary", use_container_width=True, disabled=not botao_habilitado):
        try:
            salvar_reserva(placa_selecionada, modelo_selecionado, condutor.strip(), destino.strip(), data_reserva, hora_saida.strftime("%H:%M"), hora_retorno.strftime("%H:%M"))
            st.success(f"Reserva confirmada e salva no Smartsheet! Veiculo: {placa_selecionada} - {modelo_selecionado} | Condutor: {condutor} | Destino: {destino} | Data: {data_reserva.strftime('%d/%m/%Y')} | Horario: {hora_saida.strftime('%H:%M')} as {hora_retorno.strftime('%H:%M')}")
            st.balloons()
        except Exception as e:
            st.error(f"Erro ao salvar no Smartsheet: {e}")

elif pagina == "Reservas Ativas":
    st.title("Reservas Ativas")
    st.markdown("---")
    if df_reservas.empty:
        st.info("Nenhuma reserva ativa no momento.")
    else:
        df_ativas = df_reservas[(df_reservas["status"] == "Ativa") & (df_reservas["data_reserva"] >= date.today())].sort_values("data_reserva")
        if df_ativas.empty:
            st.info("Nenhuma reserva ativa no momento.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_data = st.date_input("Filtrar por data:", value=None, key="filtro_data")
            with col_f2:
                placas_disponiveis = ["Todas"] + list(df_ativas["placa"].unique())
                filtro_placa = st.selectbox("Filtrar por veiculo:", placas_disponiveis)
            if filtro_data:
                df_ativas = df_ativas[df_ativas["data_reserva"] == filtro_data]
            if filtro_placa != "Todas":
                df_ativas = df_ativas[df_ativas["placa"] == filtro_placa]
            if df_ativas.empty:
                st.warning("Nenhuma reserva encontrada com esses filtros.")
            else:
                df_exibir = df_ativas[["placa", "modelo", "condutor", "destino", "data_reserva", "hora_saida", "hora_retorno"]].copy()
                df_exibir.columns = ["Placa", "Modelo", "Condutor", "Destino", "Data", "Saida", "Retorno"]
                df_exibir["Data"] = pd.to_datetime(df_exibir["Data"]).dt.strftime("%d/%m/%Y")
                st.dataframe(df_exibir, use_container_width=True, hide_index=True)
                st.metric("Total de reservas ativas", len(df_ativas))

elif pagina == "Cancelar Reserva":
    st.title("Cancelar Reserva")
    st.markdown("---")
    if df_reservas.empty:
        st.info("Nenhuma reserva para cancelar.")
    else:
        df_cancelaveis = df_reservas[(df_reservas["status"] == "Ativa") & (df_reservas["data_reserva"] >= date.today())].sort_values("data_reserva")
        if df_cancelaveis.empty:
            st.info("Nenhuma reserva ativa para cancelar.")
        else:
            opcoes = []
            for idx, row in df_cancelaveis.iterrows():
                data_fmt = row["data_reserva"].strftime("%d/%m/%Y") if hasattr(row["data_reserva"], "strftime") else row["data_reserva"]
                opcoes.append(f"{row['placa']} | {row['condutor']} | {row['destino']} | {data_fmt}")
            reserva_cancelar = st.selectbox("Selecione a reserva para cancelar:", opcoes)
            idx_sel = opcoes.index(reserva_cancelar)
            row_sel = df_cancelaveis.iloc[idx_sel]
            st.markdown(f"**Veiculo:** {row_sel['placa']} - {row_sel['modelo']} | **Condutor:** {row_sel['condutor']} | **Destino:** {row_sel['destino']} | **Horario:** {row_sel['hora_saida']} as {row_sel['hora_retorno']}")
            if st.button("Cancelar esta reserva", type="secondary"):
                try:
                    cancelar_reserva(row_sel["row_id"])
                    st.success("Reserva cancelada com sucesso no Smartsheet!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Erro ao cancelar: {e}")

elif pagina == "Historico":
    st.title("Historico de Reservas")
    st.markdown("---")
    if df_reservas.empty:
        st.info("Nenhuma reserva registrada.")
    else:
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            filtro_status = st.selectbox("Status:", ["Todas", "Ativa", "Cancelada"])
        with col_f2:
            filtro_condutor = st.text_input("Buscar por condutor:", "")
        with col_f3:
            filtro_placa_hist = st.selectbox("Veiculo:", ["Todos"] + list(df_reservas["placa"].unique()))
        df_hist = df_reservas.copy()
        if filtro_status != "Todas":
            df_hist = df_hist[df_hist["status"] == filtro_status]
        if filtro_condutor:
            df_hist = df_hist[df_hist["condutor"].str.contains(filtro_condutor, case=False, na=False)]
        if filtro_placa_hist != "Todos":
            df_hist = df_hist[df_hist["placa"] == filtro_placa_hist]
        if df_hist.empty:
            st.warning("Nenhuma reserva encontrada com esses filtros.")
        else:
            df_hist_exibir = df_hist[["placa", "modelo", "condutor", "destino", "data_reserva", "hora_saida", "hora_retorno", "status"]].copy()
            df_hist_exibir.columns = ["Placa", "Modelo", "Condutor", "Destino", "Data", "Saida", "Retorno", "Status"]
            df_hist_exibir["Data"] = pd.to_datetime(df_hist_exibir["Data"]).dt.strftime("%d/%m/%Y")
            st.dataframe(df_hist_exibir, use_container_width=True, hide_index=True)
            st.metric("Total de registros", len(df_hist))
