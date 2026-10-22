import streamlit as st
import pandas as pd
from datetime import datetime, date
import smartsheet
import calendar

st.set_page_config(
    page_title="Reserva de Veículos",
    page_icon="🚗",
    layout="wide"
)

SMARTSHEET_TOKEN = "2g2PXCKnWbqmN8SHjbxA6MlxsmokO1spK6Oek"
SHEET_ID = 2989343672061828

SHEET_VEICULOS_ID = 8521380734652292
SHEET_CONDUTORES_ID = 639574043742084

ss_client = smartsheet.Smartsheet(SMARTSHEET_TOKEN)
ss_client.errors_as_exceptions(True)

def carregar_cadastro(sheet_id):
    sheet = ss_client.Sheets.get_sheet(sheet_id)
    nomes_colunas = {col.id: col.title for col in sheet.columns}
    dados = []

    for row in sheet.rows:
        registro = {}
        for cell in row.cells:
            registro[nomes_colunas.get(cell.column_id, "")] = cell.value
        dados.append(registro)

    return pd.DataFrame(dados)


def esta_ativo(valor):
    return str(valor).strip().casefold() in {"sim", "s", "yes", "true", "1"}


def carregar_veiculos_ativos():
    df = carregar_cadastro(SHEET_VEICULOS_ID)
    obrigatorias = {"Placa", "Modelo", "Cor", "Ativo"}

    if not obrigatorias.issubset(df.columns):
        faltantes = ", ".join(sorted(obrigatorias - set(df.columns)))
        raise ValueError(
            f"Cadastro de Veículos: coluna(s) ausente(s): {faltantes}."
        )

    df = df[df["Ativo"].apply(esta_ativo)].copy()
    df = df.dropna(subset=["Placa", "Modelo"])

    return {
        str(row["Placa"]).strip(): {
            "modelo": str(row["Modelo"]).strip(),
            "cor": str(row["Cor"]).strip() if pd.notna(row["Cor"]) else ""
        }
        for _, row in df.iterrows()
    }


def carregar_condutores_ativos():
    df = carregar_cadastro(SHEET_CONDUTORES_ID)
    obrigatorias = {"Nome", "Ativo"}

    if not obrigatorias.issubset(df.columns):
        faltantes = ", ".join(sorted(obrigatorias - set(df.columns)))
        raise ValueError(
            f"Cadastro de Condutores: coluna(s) ausente(s): {faltantes}."
        )

    df = df[df["Ativo"].apply(esta_ativo)].copy()
    condutores = df["Nome"].dropna().astype(str).str.strip()
    return sorted([nome for nome in condutores.unique() if nome])


def obter_colunas():
    sheet = ss_client.Sheets.get_sheet(SHEET_ID)
    return {col.title: col.id for col in sheet.columns}


def carregar_reservas():
    sheet = ss_client.Sheets.get_sheet(SHEET_ID)
    nomes_colunas = {col.id: col.title for col in sheet.columns}
    dados = []

    for row in sheet.rows:
        registro = {"row_id": row.id}
        for cell in row.cells:
            registro[nomes_colunas.get(cell.column_id, "")] = cell.value
        dados.append(registro)

    df = pd.DataFrame(dados)

    if df.empty:
        return pd.DataFrame(columns=[
            "placa", "modelo", "condutor", "destino", "centro_custo",
            "data_inicio", "data_fim", "hora_saida", "hora_retorno",
            "status", "data_registro", "row_id"
        ])

    # Compatibilidade com reservas antigas que usam apenas Data Reserva.
    if "Data Inicio" not in df.columns and "Data Reserva" in df.columns:
        df["Data Inicio"] = df["Data Reserva"]
    if "Data Fim" not in df.columns:
        df["Data Fim"] = df.get("Data Inicio")
    if "Centro de Custo" not in df.columns:
        df["Centro de Custo"] = ""

    for coluna in ["Data Inicio", "Data Fim"]:
        df[coluna] = pd.to_datetime(df[coluna], errors="coerce").dt.date

    return df.rename(columns={
        "Placa": "placa",
        "Veiculo": "modelo",
        "Condutor": "condutor",
        "Destino": "destino",
        "Centro de Custo": "centro_custo",
        "Data Inicio": "data_inicio",
        "Data Fim": "data_fim",
        "Hora Saida": "hora_saida",
        "Hora Retorno": "hora_retorno",
        "Status": "status",
        "Data Registro": "data_registro"
    })


def salvar_reserva(placa, modelo, condutor, destino, centro_custo, data_inicio, data_fim, hora_saida, hora_retorno):
    colunas = obter_colunas()
    nova_linha = smartsheet.models.Row()
    nova_linha.to_top = True

    nova_linha.cells.append({"column_id": colunas["Placa"], "value": placa})
    nova_linha.cells.append({"column_id": colunas["Veiculo"], "value": modelo})
    nova_linha.cells.append({"column_id": colunas["Condutor"], "value": condutor})
    nova_linha.cells.append({"column_id": colunas["Destino"], "value": destino})
    nova_linha.cells.append({"column_id": colunas["Centro de Custo"], "value": centro_custo})
    nova_linha.cells.append({"column_id": colunas["Data Inicio"], "value": data_inicio.isoformat()})
    nova_linha.cells.append({"column_id": colunas["Data Fim"], "value": data_fim.isoformat()})
    nova_linha.cells.append({"column_id": colunas["Hora Saida"], "value": hora_saida})
    nova_linha.cells.append({"column_id": colunas["Hora Retorno"], "value": hora_retorno})
    nova_linha.cells.append({"column_id": colunas["Status"], "value": "Ativa"})
    nova_linha.cells.append({
        "column_id": colunas["Data Registro"],
        "value": datetime.now().strftime("%Y-%m-%d %H:%M")
    })

    ss_client.Sheets.add_rows(SHEET_ID, [nova_linha])


def cancelar_reserva(row_id):
    colunas = obter_colunas()
    linha = smartsheet.models.Row()
    linha.id = int(row_id)
    linha.cells.append({"column_id": colunas["Status"], "value": "Cancelada"})
    ss_client.Sheets.update_rows(SHEET_ID, [linha])


def verificar_disponibilidade(df, placa, data_inicio, data_fim):
    if df.empty:
        return True, None

    conflito = df[
        (df["placa"] == placa) &
        (df["status"] == "Ativa") &
        (df["data_inicio"] <= data_fim) &
        (df["data_fim"] >= data_inicio)
    ]

    return (False, conflito.iloc[0]) if not conflito.empty else (True, None)


def contar_disponibilidades(df):
    if df.empty:
        return len(VEICULOS)

    reservados = df[
        (df["status"] == "Ativa") &
        (df["data_inicio"] <= date.today()) &
        (df["data_fim"] >= date.today())
    ]["placa"].unique()

    ativos_reservados = [placa for placa in reservados if placa in VEICULOS]
    return max(0, len(VEICULOS) - len(ativos_reservados))


def contar_reservas_ativas(df):
    if df.empty:
        return 0
    return len(df[(df["status"] == "Ativa") & (df["data_fim"] >= date.today())])


def contar_condutores_ativos(df):
    if df.empty:
        return 0
    ativos = df[(df["status"] == "Ativa") & (df["data_fim"] >= date.today())]
    return ativos["condutor"].nunique() if not ativos.empty else 0


try:
    VEICULOS = carregar_veiculos_ativos()
    CONDUTORES = carregar_condutores_ativos()
    df_reservas = carregar_reservas()

    if not VEICULOS:
        st.error("Não há veículos ativos no Cadastro de Veículos.")
        st.stop()

    if not CONDUTORES:
        st.error("Não há condutores ativos no Cadastro de Condutores.")
        st.stop()

except Exception as e:
    st.error(f"Erro ao carregar os cadastros ou as reservas na Smartsheet: {e}")
    st.info("Confira os IDs e as colunas: Placa, Modelo, Cor, Ativo; Nome, Ativo.")
    st.stop()

st.markdown("""
<style>
.card {padding:20px; border-radius:12px; text-align:center; color:white; margin-bottom:10px;}
.card-azul {background:linear-gradient(135deg,#667eea,#764ba2);}
.card-verde {background:linear-gradient(135deg,#11998e,#38ef7d);}
.card-laranja {background:linear-gradient(135deg,#f093fb,#f5576c);}
.card-cinza {background:linear-gradient(135deg,#4b6cb7,#182848);}
.card h2 {margin:0; font-size:2.5em;}
.card p {margin:5px 0 0; font-size:1.1em; opacity:.9;}
</style>
""", unsafe_allow_html=True)

try:
    st.sidebar.image("logo.png", use_container_width=True)
except Exception:
    st.sidebar.caption("Logo não encontrada.")

st.sidebar.title("Reserva de Veículos")
st.sidebar.markdown("---")
st.sidebar.markdown("**Quem está usando:**")
usuario_atual = st.sidebar.selectbox(
    "Usuário", CONDUTORES, label_visibility="collapsed"
)
st.sidebar.markdown("---")

PAGINAS = [
    "Home", "Nova Reserva", "Reservas Ativas", "Cancelar Reserva",
    "Histórico", "Calendário"
]
pagina_link = st.query_params.get("pagina", "Home")
if pagina_link not in PAGINAS:
    pagina_link = "Home"

pagina = st.sidebar.radio("Navegação", PAGINAS, index=PAGINAS.index(pagina_link))
st.sidebar.markdown("---")
st.sidebar.caption("Syngenta - Parent Seeds Operations")

if pagina == "Home":
    st.title("Frota")
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(f'<div class="card card-azul"><h2>{len(VEICULOS)}</h2><p>Veículos</p></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="card card-verde"><h2>{contar_disponibilidades(df_reservas)}</h2><p>Disponíveis</p></div>', unsafe_allow_html=True)
    with col3:
        st.markdown(f'<div class="card card-laranja"><h2>{contar_reservas_ativas(df_reservas)}</h2><p>Reservas ativas</p></div>', unsafe_allow_html=True)
    with col4:
        st.markdown(f'<div class="card card-cinza"><h2>{contar_condutores_ativos(df_reservas)}</h2><p>Condutores</p></div>', unsafe_allow_html=True)

    st.markdown("---")
    st.subheader("Próximas Reservas")
    df_proximas = df_reservas[
        (df_reservas["status"] == "Ativa") &
        (df_reservas["data_fim"] >= date.today())
    ].sort_values("data_inicio").head(10)

    if df_proximas.empty:
        st.info("Nenhuma reserva ativa no momento.")
    else:
        exibir = df_proximas[[
            "placa", "modelo", "condutor", "destino", "data_inicio",
            "data_fim", "hora_saida", "hora_retorno"
        ]].copy()
        exibir.columns = [
            "Placa", "Modelo", "Condutor", "Destino", "Data de Início",
            "Data de Fim", "Saída", "Retorno"
        ]
        exibir["Data de Início"] = pd.to_datetime(exibir["Data de Início"]).dt.strftime("%d/%m/%Y")
        exibir["Data de Fim"] = pd.to_datetime(exibir["Data de Fim"]).dt.strftime("%d/%m/%Y")
        st.dataframe(exibir, use_container_width=True, hide_index=True)

elif pagina == "Nova Reserva":
    st.title("Nova Reserva")
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        opcoes = [f"{placa} - {info['modelo']} ({info['cor']})" for placa, info in VEICULOS.items()]
        veiculo_selecionado = st.selectbox("Selecione o Veículo", opcoes)
        placa_selecionada = veiculo_selecionado.split(" - ")[0]
        modelo_selecionado = VEICULOS[placa_selecionada]["modelo"]
        condutor = st.selectbox("Nome do Condutor", CONDUTORES, index=CONDUTORES.index(usuario_atual))
        destino = st.text_input("Destino", placeholder="Ex.: Matão, Ribeirão Preto")
        centro_custo = st.text_input("Centro de Custo", placeholder="Ex.: 1234-5678")

    with col2:
        data_inicio = st.date_input("Data de Início", min_value=date.today(), value=date.today())
        data_fim = st.date_input("Data de Fim", min_value=data_inicio, value=data_inicio)
        st.caption(f"Período: {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}")
        h1, h2 = st.columns(2)
        with h1:
            hora_saida = st.time_input("Hora de Saída", value=None)
        with h2:
            hora_retorno = st.time_input("Hora de Retorno", value=None)

    disponivel, conflito = verificar_disponibilidade(df_reservas, placa_selecionada, data_inicio, data_fim)
    if disponivel:
        st.success(f"DISPONÍVEL — Veículo {placa_selecionada} está disponível de {data_inicio.strftime('%d/%m/%Y')} até {data_fim.strftime('%d/%m/%Y')}.")
    else:
        st.error(f"INDISPONÍVEL — Veículo já reservado por {conflito['condutor']} no período de {conflito['data_inicio'].strftime('%d/%m/%Y')} até {conflito['data_fim'].strftime('%d/%m/%Y')}.")

    habilitado = bool(disponivel and destino.strip() and centro_custo.strip() and hora_saida is not None and hora_retorno is not None)
    if st.button("Confirmar Reserva", type="primary", use_container_width=True, disabled=not habilitado):
        try:
            salvar_reserva(
                placa_selecionada, modelo_selecionado, condutor, destino.strip(),
                centro_custo.strip(), data_inicio, data_fim,
                hora_saida.strftime("%H:%M"), hora_retorno.strftime("%H:%M")
            )
            st.success("Reserva confirmada e salva na Smartsheet.")
            st.rerun()
        except Exception as e:
            st.error(f"Erro ao salvar na Smartsheet: {e}")

elif pagina == "Reservas Ativas":
    st.title("Reservas Ativas")
    st.markdown("---")
    df_ativas = df_reservas[
        (df_reservas["status"] == "Ativa") &
        (df_reservas["data_fim"] >= date.today())
    ].sort_values("data_inicio")

    if df_ativas.empty:
        st.info("Nenhuma reserva ativa no momento.")
    else:
        filtro_data, filtro_placa = st.columns(2)
        with filtro_data:
            data_filtro = st.date_input("Filtrar por data:", value=None)
        with filtro_placa:
            placa_filtro = st.selectbox("Filtrar por veículo:", ["Todas"] + list(df_ativas["placa"].unique()))

        if data_filtro:
            df_ativas = df_ativas[
                (df_ativas["data_inicio"] <= data_filtro) &
                (df_ativas["data_fim"] >= data_filtro)
            ]
        if placa_filtro != "Todas":
            df_ativas = df_ativas[df_ativas["placa"] == placa_filtro]

        if df_ativas.empty:
            st.warning("Nenhuma reserva encontrada com esses filtros.")
        else:
            exibir = df_ativas[[
                "placa", "modelo", "condutor", "destino", "data_inicio",
                "data_fim", "hora_saida", "hora_retorno"
            ]].copy()
            exibir.columns = [
                "Placa", "Modelo", "Condutor", "Destino", "Data de Início",
                "Data de Fim", "Saída", "Retorno"
            ]
            exibir["Data de Início"] = pd.to_datetime(exibir["Data de Início"]).dt.strftime("%d/%m/%Y")
            exibir["Data de Fim"] = pd.to_datetime(exibir["Data de Fim"]).dt.strftime("%d/%m/%Y")
            st.dataframe(exibir, use_container_width=True, hide_index=True)

elif pagina == "Cancelar Reserva":
    st.title("Cancelar Reserva")
    st.markdown("---")

    df_minhas = df_reservas[
        (df_reservas["status"] == "Ativa") &
        (df_reservas["data_fim"] >= date.today()) &
        (df_reservas["condutor"].astype(str).str.strip().str.casefold() == usuario_atual.strip().casefold())
    ].sort_values("data_inicio")

    if df_minhas.empty:
        st.info(f"Não há reservas ativas para cancelamento em nome de {usuario_atual}.")
    else:
        opcoes = [
            f"{r['placa']} | {r['destino']} | {r['data_inicio'].strftime('%d/%m/%Y')}"
            for _, r in df_minhas.iterrows()
        ]
        selecionada = st.selectbox("Selecione a sua reserva para cancelar:", opcoes)
        reserva = df_minhas.iloc[opcoes.index(selecionada)]
        st.markdown(
            f"**Veículo:** {reserva['placa']} - {reserva['modelo']} | "
            f"**Condutor:** {reserva['condutor']} | "
            f"**Destino:** {reserva['destino']} | "
            f"**Centro de Custo:** {reserva.get('centro_custo', '')} | "
            f"**Período:** {reserva['data_inicio'].strftime('%d/%m/%Y')} até {reserva['data_fim'].strftime('%d/%m/%Y')} | "
            f"**Horário:** {reserva['hora_saida']} às {reserva['hora_retorno']}"
        )
        if st.button("Cancelar minha reserva", type="secondary"):
            try:
                cancelar_reserva(reserva["row_id"])
                st.success("Sua reserva foi cancelada com sucesso.")
                st.rerun()
            except Exception as e:
                st.error(f"Erro ao cancelar: {e}")

elif pagina == "Histórico":
    st.title("Histórico de Reservas")
    st.markdown("---")

    if df_reservas.empty:
        st.info("Nenhuma reserva registrada.")
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            status = st.selectbox("Status:", ["Todas", "Ativa", "Cancelada"])
        with c2:
            busca = st.text_input("Buscar por condutor:")
        with c3:
            placa = st.selectbox("Veículo:", ["Todos"] + list(df_reservas["placa"].dropna().unique()))

        hist = df_reservas.copy()
        if status != "Todas":
            hist = hist[hist["status"] == status]
        if busca:
            hist = hist[hist["condutor"].astype(str).str.contains(busca, case=False, na=False)]
        if placa != "Todos":
            hist = hist[hist["placa"] == placa]

        if hist.empty:
            st.warning("Nenhuma reserva encontrada com esses filtros.")
        else:
            exibir = hist[[
                "placa", "modelo", "condutor", "destino", "centro_custo",
                "data_inicio", "data_fim", "hora_saida", "hora_retorno", "status"
            ]].copy()
            exibir.columns = [
                "Placa", "Modelo", "Condutor", "Destino", "Centro de Custo",
                "Data de Início", "Data de Fim", "Saída", "Retorno", "Status"
            ]
            exibir["Data de Início"] = pd.to_datetime(exibir["Data de Início"]).dt.strftime("%d/%m/%Y")
            exibir["Data de Fim"] = pd.to_datetime(exibir["Data de Fim"]).dt.strftime("%d/%m/%Y")
            st.dataframe(exibir, use_container_width=True, hide_index=True)
            st.metric("Total de registros", len(hist))

elif pagina == "Calendário":
    st.title("Calendário de Reservas")
    st.markdown("---")

    if df_reservas.empty:
        st.info("Nenhuma reserva registrada.")
    else:
        df_cal = df_reservas.copy()
        df_cal["data_inicio"] = pd.to_datetime(df_cal["data_inicio"], errors="coerce")
        df_cal["data_fim"] = pd.to_datetime(df_cal["data_fim"], errors="coerce")
        df_cal = df_cal.dropna(subset=["data_inicio", "data_fim"])

        if df_cal.empty:
            st.warning("Não foi possível identificar as datas das reservas.")
        else:
            meses = [
                "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"
            ]
            anos = sorted(set(
                df_cal["data_inicio"].dt.year.tolist() +
                df_cal["data_fim"].dt.year.tolist() +
                [date.today().year]
            ))

            c1, c2, c3 = st.columns(3)
            with c1:
                mes = st.selectbox(
                    "Mês:", list(range(1, 13)), index=date.today().month - 1,
                    format_func=lambda n: meses[n - 1]
                )
            with c2:
                ano = st.selectbox("Ano:", anos, index=anos.index(date.today().year))
            with c3:
                placa = st.selectbox(
                    "Veículo:",
                    ["Todos"] + sorted(df_cal["placa"].dropna().astype(str).unique().tolist())
                )

            primeiro_dia = pd.Timestamp(date(ano, mes, 1))
            ultimo_dia = primeiro_dia + pd.offsets.MonthEnd(1)
            reservas = df_cal[
                (df_cal["data_inicio"] <= ultimo_dia) &
                (df_cal["data_fim"] >= primeiro_dia)
            ].copy()

            if placa != "Todos":
                reservas = reservas[reservas["placa"] == placa]

            cores = {
                "SHI-6J15": "#5B7F12",
                "SHI-6J17": "#A92D76",
                "UAE-7E13": "#2878B5",
                "UVH-2D53": "#D97A18"
            }

            st.markdown("""
            <style>
            .legenda {display:flex; gap:10px; flex-wrap:wrap; margin:20px 0;}
            .tag {color:#fff; padding:5px 10px; border-radius:5px; font-size:13px;}
            .cal {display:grid; grid-template-columns:repeat(7, minmax(0, 1fr)); width:100%; overflow:hidden; border-top:1px solid #ddd; border-left:1px solid #ddd;}
            .cab {background:#f4f5f6; text-align:center; font-weight:bold; padding:8px 4px; font-size:13px; border-right:1px solid #ddd; border-bottom:1px solid #ddd;}
            .dia {min-height:110px; min-width:0; padding:5px; border-right:1px solid #ddd; border-bottom:1px solid #ddd;}
            .hoje {background:#eaf7ee;}
            .num {font-weight:bold; margin-bottom:5px;}
            .evento {display:block; width:100%; box-sizing:border-box; color:#fff; padding:3px 5px; border-radius:4px; margin:2px 0; font-size:10px; line-height:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;}
            </style>
            """, unsafe_allow_html=True)

            legenda = '<div class="legenda">' + ''.join(
                f'<span class="tag" style="background:{cor}">{placa} - Fiat Toro</span>'
                for placa, cor in cores.items()
            ) + '</div>'
            st.markdown(legenda, unsafe_allow_html=True)

            html = '<div class="cal">' + ''.join(
                f'<div class="cab">{dia}</div>'
                for dia in ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
            )

            for semana in calendar.monthcalendar(ano, mes):
                for dia in semana:
                    if not dia:
                        html += '<div class="dia"></div>'
                        continue

                    data_dia = pd.Timestamp(date(ano, mes, dia))
                    itens = reservas[
                        (reservas["data_inicio"] <= data_dia) &
                        (reservas["data_fim"] >= data_dia)
                    ]
                    classe = " hoje" if data_dia.date() == date.today() else ""
                    eventos = ""

                    for _, reserva in itens.iterrows():
                        placa_reserva = str(reserva["placa"])
                        cor = cores.get(placa_reserva, "#6C757D")
                        condutor_reserva = str(reserva["condutor"])
                        titulo = (
                            f"{placa_reserva} | {condutor_reserva} | "
                            f"CC: {reserva.get('centro_custo', '')}"
                        )
                        texto = f"{placa_reserva} - {condutor_reserva}"
                        eventos += (
                            f'<div class="evento" style="background:{cor}" '
                            f'title="{titulo}">{texto}</div>'
                        )

                    html += (
                        f'<div class="dia{classe}"><div class="num">{dia}</div>'
                        f'{eventos}</div>'
                    )

            html += '</div>'
            st.markdown(html, unsafe_allow_html=True)
            st.metric("Total de reservas no período", len(reservas))
