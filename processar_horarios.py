import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from IPython.display import HTML # Você ainda pode precisar disso se testar em um notebook

# --- DEFINIÇÕES GLOBAIS ---
dias_da_semana = {'2': 'segunda-feira', '3': 'terça-feira', '4': 'quarta-feira', '5': 'quinta-feira', '6': 'sexta-feira'}
horarios_turno = {
    '1': ['08:00-08:50', '08:50-09:40', '10:00-10:50', '10:50-11:40', '11:40-12:30'],
    '2': ['13:30-14:20', '14:20-15:10', '15:10-16:00', '16:00-16:50', '17:10-18:00', '18:00-18:50'],
    '3': ['19:00-19:50', '19:50-20:40', '20:40-21:30', '21:30-22:20', '22:20-23:10']
}
creds_file = 'gcreds.json' # O GitHub Action vai criar este arquivo 

# --- FUNÇÕES DE PROCESSAMENTO ---

def buscar_dados_planilha():
    """Autentica e busca os dados da planilha do Google Sheets."""
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive"
    ]
    try:
        creds = Credentials.from_service_account_file(creds_file, scopes=scopes)
        client = gspread.authorize(creds)
        google_sheet = client.open("planilha-2025-2-real")
        aba = google_sheet.worksheet("Planilha1")
        dados = aba.get_all_records()
        return pd.DataFrame(dados)
    
    except gspread.exceptions.SpreadsheetNotFound:
        print("ERRO: Planilha não encontrada. Verifique o nome da planilha no Google Sheets.")
        raise
    except gspread.exceptions.WorksheetNotFound:
        print("ERRO: Aba da planilha não encontrada. Verifique o nome da aba (ex: 'Planilha1').")
        raise
    except Exception as e:
        print(f"Ocorreu um erro ao acessar o Google Sheets: {e}")
        raise

def gerar_tabela_html(tabela_horarios, titulo):
    """Gera o HTML de uma tabela de horário."""
    html = f'<h3 style=\"text-align: center; font-size: 1.5em; font-weight: bold;\">{titulo}</h3>'
    html += '<table border=\"1\" cellpadding=\"5\" cellspacing=\"0\" style=\"border-collapse: collapse; text-align: center; width: 100%;\">'
    html += '<thead><tr><th>Horário</th><th>Segunda-feira</th><th>Terça-feira</th><th>Quarta-feira</th><th>Quinta-feira</th><th>Sexta-feira</th></tr></thead><tbody>'
    
    for index, row in tabela_horarios.iterrows():
        if row['horário'] == '---':
            html += '<tr><td colspan=\"6\" style=\"background-color: #e0e0e0; font-weight: bold;\">Intervalo entre Turnos</td></tr>'
        else:
            html += '<tr>' + ''.join(f'<td>{item}</td>' for item in row) + '</tr>'
    
    html += '</tbody></table>'
    return html

def gerar_html_tabela_horarios(df, titulo):
    """Gera o HTML de UMA tabela específica (ex: 2º semestre)"""
    horarios = pd.DataFrame(df, columns=['horário', 'dia', 'disciplina'])
    tabela_pivot = horarios.pivot_table(index='horário', columns='dia', values='disciplina', aggfunc=lambda x: '<br>'.join(x)).fillna('')

    for dia in dias_da_semana.values():
        if dia not in tabela_pivot.columns:
            tabela_pivot[dia] = ''
    tabela_pivot = tabela_pivot[['segunda-feira', 'terça-feira', 'quarta-feira', 'quinta-feira', 'sexta-feira']]

    turnos_usados = set()
    for linha in df:
        if linha[0] in horarios_turno['1']: turnos_usados.add('1')
        elif linha[0] in horarios_turno['2']: turnos_usados.add('2')
        elif linha[0] in horarios_turno['3']: turnos_usados.add('3')

    horarios_completos = []
    for i, turno in enumerate(sorted(turnos_usados)):
        horarios_completos.extend(horarios_turno[turno])
        if i < len(turnos_usados) - 1:
            horarios_completos.append('---')
    
    tabela_final = pd.DataFrame({'horário': horarios_completos})
    tabela_final = pd.merge(tabela_final, tabela_pivot, on='horário', how='left').fillna('')

    # A MUDANÇA PRINCIPAL ESTÁ AQUI:
    return gerar_tabela_html(tabela_final, titulo)
    # Antes era: display(HTML(gerar_tabela_html(tabela_final, titulo)))


def gerar_html_todas_tabelas():
    """Função principal que busca dados e gera o HTML de TODAS as tabelas."""
    
    planilha = buscar_dados_planilha()
    
    # Dicionários para guardar os dados
    semestres_pares = {}
    reofertas = []
    optativas = []

    # Processamento das linhas da planilha
    for _, row in planilha.iterrows():
        semestre = row['semestre']
        if pd.isna(semestre):
            continue
        
        try:
            semestre = int(semestre)
        except ValueError:
            continue

        codigo = row.get('codigo', '')
        nome = row.get('disciplina', '')
        turma = row.get('turma', '')
        prof = row.get('professor', '')

        horarios_disciplina = []
        for i in range(1, 7):
            horario_col = f'horario {i}'
            sala_col = f'sala {i}'
            horario_val = row.get(horario_col)

            if pd.notna(horario_val) and str(horario_val).strip() != '':
                try:
                    cod_horario = str(int(horario_val))
                except ValueError:
                    continue

                dia = dias_da_semana.get(cod_horario[0], '')
                turno = cod_horario[1]
                aula_idx = int(cod_horario[2]) - 1
                
                if turno in horarios_turno and 0 <= aula_idx < len(horarios_turno[turno]):
                    hora = horarios_turno[turno][aula_idx]
                else:
                    continue

                sala = row.get(sala_col, '')
                if pd.isna(sala) or str(sala).strip().lower() == 'nan' or str(sala).strip() == '':
                    sala = 'sala indefinida'
                else:
                    sala = f'sala {sala}'

                texto = f'{codigo} - {nome} {turma} (Prof. {prof} - {sala})'
                horarios_disciplina.append([hora, dia, texto])

        if not horarios_disciplina:
            continue

        if semestre % 2 == 0 and semestre < 10:
            if semestre not in semestres_pares:
                semestres_pares[semestre] = []
            semestres_pares[semestre].extend(horarios_disciplina)
        elif semestre % 2 == 1 and semestre < 10:
            reofertas.extend(horarios_disciplina)
        elif semestre == 88:
            optativas.extend(horarios_disciplina)

    # Geração das strings HTML
    html_final_como_string = ""
    
    for semestre, lista in sorted(semestres_pares.items()):
        html_final_como_string += gerar_html_tabela_horarios(lista, f'{semestre}º semestre')
        html_final_como_string += "\n<br>\n" # Adiciona um espaço

    if reofertas:
        html_final_como_string += gerar_html_tabela_horarios(reofertas, 'Reofertas')
        html_final_como_string += "\n<br>\n"

    if optativas:
        html_final_como_string += gerar_html_tabela_horarios(optativas, 'Optativas')

    return html_final_como_string
