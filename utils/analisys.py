import pandas as pd
import re
from datetime import datetime


# Mostra todas as colunas
pd.set_option('display.max_columns', None)
# Aumenta a largura máxima da tela para não quebrar visualmente
pd.set_option('display.width', None)


def limpar_valor_monetario(valor):
    """
    Converte valores monetários do SIOR para float.

    Exemplos aceitos:
    - R$ 1.234,56
    - 1.234,56
    - 1234,56
    - 1234.56

    Valores inválidos, como 'Valor Original' ou 'Não informado',
    retornam 0.0 para não quebrar a varredura.
    """

    try:
        if pd.isna(valor):
            return 0.0

        valor = str(valor).strip()

        if not valor:
            return 0.0

        valores_invalidos = {
            "valor original",
            "não informado",
            "nao informado",
            "none",
            "nan",
            "-"
        }

        if valor.lower() in valores_invalidos:
            return 0.0

        valor = (
            valor
            .replace("R$", "")
            .replace("\xa0", "")
            .replace(" ", "")
            .strip()
        )

        # Remove qualquer caractere que não seja número, ponto, vírgula ou sinal.
        valor = re.sub(r"[^0-9,.-]", "", valor)

        if not valor:
            return 0.0

        # Padrão brasileiro: 1.234,56
        if "," in valor:
            valor = (
                valor
                .replace(".", "")
                .replace(",", ".")
            )

        return float(valor)

    except Exception:
        return 0.0


def etl_data(df_param, df_resultado2):
    inicio = datetime.now()
    # Lê o Excel principal
    #df = pd.read_excel(r'C:\Users\Daniel\Desktop\Projetos Dev\Varredura-SIOR-Cadastro-Divida\dados_finais.xlsx')
    df = df_resultado2
    colunas_desejadas = [
        'NUP Sapiens', 'Número do Auto - Auto de Infração', 'Devedor',
        'Data do Vencimento do Último Boleto - Análise e Conferência Sapiens',
        'Data de Início da Multa de Mora - Análise e Conferência Sapiens',
        'Data de Início da Taxa SELIC - Análise e Conferência Sapiens',
        'Valor Original - Financeiro',
        'Enquadramento - Auto de Infração',
        'Data da Infração - Auto de Infração',
        'Utilização de Publicação Editalícia? - Notificação de Autuação',
        'Data de Publicação no DOU - Notificação de Autuação [2]',
        'Data da Postagem - Notificação de Autuação [2]',
        'Data de Vencimento do Edital - Notificação de Autuação [2]',
        'Data de Vencimento - Notificação de Autuação [2]',
        'Data da Constituição Definitiva - Análise e Conferência Sapiens',
        'CodigoProcessoInfracao',
        'Data da Prescrição Executória - Análise e Conferência Sapiens',
        'Data de Cadastro no Sapiens Adm - Análise e Conferência Sapiens',
        'Data de Cadastro no Sapiens Dívida - Análise e Conferência Sapiens',
        'A notificação da autuação foi expedida no prazo de 30 (trinta) dias (Art. 281, parágrafo único, II, do CTB)? - Notificação de Autuação',
        'O andamento processual foi paralisado por mais de 3 (três) anos? - Análise e Conferência Sapiens',
        'O período que decorreu entre a constituição definitiva do crédito e a remessa dos autos a PFE/DNIT excede 5 anos? - Análise e Conferência Sapiens',
        'Data de Entrega do AR - Notificação de Autuação [2]',
        'Data de Vencimento Vigente - Notificação de Autuação',
        'Situação / Fase',
        'Recuperação de Crédito',
        'Inscrito em DAU',
        'Serviço de Expedição - Notificação de Autuação',
        'Serviço de Expedição - Notificação de Penalidade',
        'Situação do Débito - Financeiro',
        'Utilização de Publicação Editalícia? - Notificação de Autuação',
        'Utilização de Publicação Editalícia? - Notificação de Penalidade'
    ]

    if not all(col in df.columns for col in colunas_desejadas):
        raise ValueError("Uma ou mais colunas necessárias não foram encontradas no DataFrame.")

    df_extraido = df[['NUP Sapiens', 'Número do Auto - Auto de Infração', 'Devedor', 'CodigoProcessoInfracao']].copy()
    df_extraido.insert(1, 'Credor', 'DNIT')

    df_extraido['Devedor'] = df_extraido['Devedor'].apply(
        lambda x: re.search(r'\((.*?)\)', str(x)).group(1) if re.search(r'\((.*?)\)', str(x)) else x
    )

    df_extraido.insert(4, 'Data do Vencimento do Último Boleto - Análise e Conferência Sapiens',
                       df['Data do Vencimento do Último Boleto - Análise e Conferência Sapiens'])
    df_extraido.insert(5, 'Data de Início da Multa de Mora - Análise e Conferência Sapiens',
                       df['Data de Início da Multa de Mora - Análise e Conferência Sapiens'])
    df_extraido.insert(6, 'Data de Início da Taxa SELIC - Análise e Conferência Sapiens',
                       df['Data de Início da Taxa SELIC - Análise e Conferência Sapiens'])

    df_valor = df["Valor Original - Financeiro"].apply(
        limpar_valor_monetario
    )

    df_extraido.insert(
        7,
        "Valor Original - Financeiro",
        df_valor
    )

    df_extraido.insert(8, 'Modalidade', 'AUTO DE INFRAÇÃO')
    df_extraido.insert(9, 'Número do Auto2', df['Número do Auto - Auto de Infração'])
    df_extraido.insert(10, 'Data da Infração', df['Data da Infração - Auto de Infração'])

    df_extraido.insert(11, 'Data da Notificação Inicial', df.apply(
        lambda row: (
            row['Data de Publicação no DOU - Notificação de Autuação [2]']
            if str(row['Utilização de Publicação Editalícia? - Notificação de Autuação']).strip().lower() == 'sim'
            else row['Data da Postagem - Notificação de Autuação [2]']
        ),
        axis=1
    ))

    df_extraido.insert(12, 'Const. Def. Cred', df['Data da Constituição Definitiva - Análise e Conferência Sapiens'])

    df_merged = df_extraido.merge(
        df_param[['CodigoProcessoInfracao', 'EquipeSelecionada', 'TecnicoAnalise', 'DataAnalise',
                  'TecnicoConferencia', 'DataConferencia']],
        on='CodigoProcessoInfracao',
        how='left'
    )

    df_extraido['EquipeSelecionada'] = df_merged['EquipeSelecionada'].map({
        1: 'YAN GABRIEL TAVARES RODRIGUES',
        2: 'ARTHUR MOREIRA ALVES DE SOUZA',
        3: 'RAIANA TEIXEIRA DE SOUSA',
        4: 'SABRINA NERES CARVALHO',
        5: 'LUIZA ALVES DA CRUZ',
        9: 'DANIEL SANTOS DE ALMEIDA'
    })

    df_extraido['TecnicoAnalise'] = df_merged['TecnicoAnalise']
    df_extraido['DataAnalise'] = df_merged['DataAnalise']
    df_extraido['TecnicoConferencia'] = df_merged['TecnicoConferencia']
    df_extraido['DataConferencia'] = df_merged['DataConferencia']

    df_extraido['Decurso do prazo da defesa'] = df.apply(
        lambda row: (
            row['Data de Vencimento - Notificação de Autuação [2]']
            if str(row['Data de Vencimento do Edital - Notificação de Autuação [2]']).strip().lower() == 'não informado'
            else row['Data de Vencimento do Edital - Notificação de Autuação [2]']
        ),
        axis=1
    )

    df_extraido.insert(14, 'Regional', 'DNIT')
    df_extraido.insert(15, 'Unidade', 'INFRA')
    df_extraido.insert(16, 'Prescrição Executória',
                       df['Data da Prescrição Executória - Análise e Conferência Sapiens'])
    df_extraido.insert(17, 'Data Cadastro ADM',
                       df['Data de Cadastro no Sapiens Adm - Análise e Conferência Sapiens'])
    df_extraido.insert(18, 'Data Cadastro Dívida',
                       df['Data de Cadastro no Sapiens Dívida - Análise e Conferência Sapiens'])
    df_extraido.insert(19, '30 Dias - Decadencial',
                       df['A notificação da autuação foi expedida no prazo de 30 (trinta) dias (Art. 281, parágrafo único, II, do CTB)? - Notificação de Autuação'])
    df_extraido.insert(20, '3 anos - Intercorrente',
                       df['O andamento processual foi paralisado por mais de 3 (três) anos? - Análise e Conferência Sapiens'])
    df_extraido.insert(21, '5 anos - Executória',
                       df['O período que decorreu entre a constituição definitiva do crédito e a remessa dos autos a PFE/DNIT excede 5 anos? - Análise e Conferência Sapiens'])
    df_extraido.insert(22, 'Encaminhamento CCOBE *(Modificada)', df['Situação / Fase'])
    df_extraido.insert(23, 'Recuperação de Crédito *(Modificada)', df['Recuperação de Crédito'])
    df_extraido.insert(24, 'Inscrito em DAU', df['Inscrito em DAU'])
    df_extraido.insert(25, 'Data Inscrito *(Modificada)', 'Sem data')
    df_extraido.insert(26, 'Concat Devedor', df['Devedor'])
    df_extraido.insert(27, 'Postagem NA Analise', df['Data da Postagem - Notificação de Autuação [2]'])
    df_extraido.insert(28, 'Postagem NP Analise', df['Data da Postagem - Notificação de Penalidade [2]'])
    df_extraido.insert(29, 'Veiculo', 'Sem utilização')
    df_extraido.insert(30, 'Data Vencimento NA - Multa', df['Data de Vencimento Vigente - Notificação de Autuação'])
    df_extraido.insert(31, 'Data Vencimento NP - Multa', df['Data de Vencimento Vigente - Notificação de Penalidade'])
    df_extraido.insert(32, 'Expedição NA', df['Serviço de Expedição - Notificação de Autuação'])
    df_extraido.insert(33, 'Expedição NP', df['Serviço de Expedição - Notificação de Penalidade'])
    df_extraido.insert(34, 'Postagem NA Analise *(Duplicada)', df['Data da Postagem - Notificação de Autuação [2]'])
    df_extraido = inserir_colunas_defesa_condicional(df, df_extraido)
    df_extraido.insert(35, 'Situacao Débito', df['Situação do Débito - Financeiro'])
    df_extraido.insert(36, 'Publicação Editalícia NA', df['Utilização de Publicação Editalícia? - Notificação de Autuação'])
    df_extraido.insert(37, 'Publicação Editalícia NP', df['Utilização de Publicação Editalícia? - Notificação de Penalidade'])
    df_extraido.insert(38, 'Data analise Vencimento NA 1',
                       df['Data de Vencimento - Notificação de Autuação [2]'])
    df_extraido.insert(39, 'Data analise Vencimento NA 2 (Edital)',
                       df['Data de Vencimento do Edital - Notificação de Autuação [2]'])
    df_extraido.insert(40, 'Data analise Vencimento NP 1',
                       df['Data de Vencimento - Notificação de Penalidade [2]'])
    df_extraido.insert(41, 'Data analise Vencimento NP 2 (Edital)',
                       df['Data de Vencimento do Edital - Notificação de Penalidade [2]'])


    # ---------------------------------------------------
    # Funções de analise
    df_extraido['Validação Data Infração vs Notificação'] = df.apply(validar_data_infracao_vs_notificacao, axis=1)
    df_extraido['Validação Data Infração vs Decurso Defesa'] = df.apply(validar_data_infracao_vs_decurso_defesa, axis=1)
    df_extraido['Validação Decurso Defesa vs Notificação Inicial'] = df.apply(
        validar_data_notificacao_inicial_vs_decurso_defesa, axis=1)
    # Funções de analise INTERCORRENTE
    df_extraido['Validação Postagem NA x Publicação NA DOU'] = df.apply(
        validar_prescricao_intercorrente_postagem_vs_publicacao, axis=1)
    df_extraido['Validação Vencimento NA x Postagem NP'] = df.apply(validar_vencimento_na_vs_postagem_np, axis=1)
    df_extraido['Validação Postagem NP x Publicação NP DOU'] = df.apply(validar_prescricao_postagem_np_vs_publicacao_np,
                                                                        axis=1)
    df_extraido['Validação Postagem NP x Publicação NP DOU * (Duplicada)'] = df.apply(
        validar_prescricao_postagem_np_vs_publicacao_np, axis=1)
    df_extraido['Validação Vencimento NP'] = df.apply(validar_vencimento_np, axis=1)
    df_extraido['Validação Data Atual x Prescrição Executória'] = df.apply(validar_prescricao_executoria_data_atual,
                                                                           axis=1)
    df_extraido['Validação Utilizou AR NA ou Edital NA'] = df.apply(validar_utilizou_ar_ou_edital_na, axis=1)
    df_extraido['Validação Utilizou AR NP ou Edital NP'] = df.apply(validar_utilizou_ar_ou_edital_np, axis=1)
    df_extraido['Verificação NUP SIOR vs Sapiens'] = df.apply(validar_nup_sior_vs_sapiens, axis=1)
    df_extraido['Validação Data Infração x Notificação Inicial'] = df.apply(
        validar_data_infracao_vs_data_notificacao_inicial, axis=1)
    df_extraido['Validação Vencimento x Início Mora'] = df.apply(validar_vencimento_vs_multa_mora, axis=1)
    df_extraido['Validação Vencimento x Início Selic'] = df.apply(validar_vencimento_vs_selic, axis=1)
    df_extraido['Validação Vencimento NA vs Edital'] = df.apply(validar_vencimento_na, axis=1)
    df_extraido['Validação Vencimento NP vs Edital'] = df.apply(validar_vencimento_np_nova, axis=1)
    df_extraido['Validação Postagem NA divergente'] = df.apply(validar_postagem_na_divergente, axis=1)
    df_extraido['Validação Postagem NP divergente'] = df.apply(validar_postagem_np_divergente, axis=1)
    df_extraido['Validação Prescrição vs Vencimento + 5 anos'] = df.apply(validar_prescricao_por_vencimento, axis=1)
    df_extraido['Validação Const. Def. divergente'] = df.apply(validar_const_def_divergente, axis=1)
    df_extraido['Validação Postagem NP e Cadin'] = df.apply(validar_cadin_divergente, axis=1)

    # ---------------------------------------------------
    df_extraido['Supervisor'] = df_merged['EquipeSelecionada'].map({
        1: 'YAN GABRIEL TAVARES RODRIGUES',
        2: 'ARTHUR MOREIRA ALVES DE SOUZA',
        3: 'RAIANA TEIXEIRA DE SOUSA',
        4: 'SABRINA NERES CARVALHO',
        5: 'LUIZA ALVES DA CRUZ',
        9: 'DANIEL SANTOS DE ALMEIDA'
    })
    df_extraido['Equipe Nome'] = df_merged['EquipeSelecionada'].map({
        1: 'EQUIPE COBRANÇA 2',
        2: 'EQUIPE COBRANÇA 1',
        3: 'EQUIPE COBRANÇA 3',
        4: 'EQUIPE COBRANÇA 4',
        5: 'EQUIPE COBRANÇA 5',
        9: 'EQUIPE COBRANÇA 7'
    })

    # Complementos
    def definir_complemento(enq):
        if enq == "745-5 / 0: Transitar em velocidade superior à máxima permitida em até 20%":
            return "VELOCIDADE"
        elif enq == "746-3 / 0: Transitar em velocidade superior à máxima permitida em mais de 20% até 50%":
            return "VELOCIDADE"
        elif enq == "747-1 / 0: Transitar em velocidade superior à máxima permitida em mais de 50%":
            return "VELOCIDADE"
        elif enq == ("605-0 / 3: Avançar o sinal vermelho do semáforo,"
                     " exc houver sinaliz perm livre conv à direita -fiscalização eletrônica"):
            return "AVANÇO"
        elif enq == "605-0 / 1: Avançar o sinal vermelho do semáforo":
            return "AVANÇO"
        elif enq in [
            "683-1 / 2: Transitar com o veículo com excesso de peso - Por Eixo",
            "683-1 / 3: Transitar com o veículo com excesso de peso - PBT/PBTC e Por Eixo",
            "683-1 / 1: Transitar com o veículo com excesso de peso PBT/PBTC",
            '690-4 / 0: Transitar com o veículo excedendo a CMT acima de 1.000 k'
        ]:
            return "PESO"
        elif enq in [
            "567-3 / 2: Parar sobre faixa de pedestres na mudança de sinal luminoso (fisc eletrônica)",
            "581-9 / 7: Transitar com o veículo em acostamentos",
            '606-8 / 2: Deixar de adentrar às áreas destinadas à pesagem de veículos',
            '583-5 / 0: Desobedecer às ordens emanadas da autorid compet de trânsito ou de seus agentes',
            '772-2 / 0: Quando o veículo estiver em movimento deixar de manter acesa a luz baixa de dia, '
            'em rodovias de pista simples situadas fora dos perímetros urbanos, no caso de veículos desprovidos'
            ' de luzes de rodagem diurna',
            '596-7 / 0: Ultrapassar pela contramão linha de divisão de fluxos opostos, contínua amarela',
            '581-9 / 4: Transitar com o veículo em canteiros centrais/divisores de pista de rolamento',
            '544-4 / 0: Estacionar nos acostamentos',
            '579-7 / 0: Forçar passagem entre veícs trans sent opostos na iminência realiz ultrapassagem',
            '545-2 / 5: Estacionar ao lado ou sobre canteiro central/divisores de pista de rolamento',
            '704-8 / 1: Conduzir motocicleta, motoneta e ciclomotor transportando Passageiro s/ capacete.',
            '581-9 / 6: Transitar com o veículo em marcas de canalização',
            '590-8 / 0: Ultrapassar pelo acostamento',
            '592-4 / 2: Ultrapassar pela contramão nos aclives ou declives, sem visibilidade suficiente',
            '724-2 / 2: Em movimento de dia, deixar de manter acesa luz baixa sob chuva, neblina ou cerração',
            '518-5 / 1: Deixar o condutor de usar o cinto segurança',
            '518-5 / 2: Deixar o passageiro de usar o cinto segurança',
            '731-5 / 0: Dirigir o veículo com o braço do lado de fora',
            '676-9 / 0: Conduzir veíc c/ defeito no sist de iluminação, sinaliz ou lâmpadas queimadas',
            '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança',
            '584-3 / 3: Deixar de indicar c/ antec, med gesto de braço/luz indicadora, mudança direção',
            '501-0 / 0: Dirigir veículo sem possuir CNH/PPD/ACC',
            '506-1 / 0: Entregar veículo a pessoa sem CNH ou Permissão para Dirigir',
            '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança',
            '658-0 / 0: Conduzir o veículo sem qualquer uma das placas de identificação',
            '768-4 / 1: Conduzir motoc/ moton/ ciclom c/ utilização de capacete de segurança'
            ' s/ viseira/óculos de proteção',
            '734-0 / 0: Dirigir o veíc usando calçado que ñ se firme nos pés/comprometa utiliz pedais',
            '684-0 / 2: Transitar com autorização vencida, expedida p/ veículo c/ dimensões excedentes',
            '736-6 / 2: Dirigir veículo utilizando-se de telefone celular',
            '763-3 / 1: Dirigir veículo segurando telefone celular',
            '627-0 / 0: Deixar de reduzir a veloc onde o trânsito esteja sendo controlado pelo agente',
            '682-3 / 1: Transitar c/ veíc e/ou carga c/ dimensões superiores limite legal s/ autorização',
            '659-9 / 2: Conduzir o veículo registrado que não esteja devidamente licenciado',
            '703-0 / 1: Conduzir motocicleta, motoneta ou ciclomotor sem capacete de segurança',
            '500-2 / 0: Multa, por não identificação do condutor infrator, imposta à pessoa jurídica',
            '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança',
            '592-4 / 1: Ultrapassar pela contramão nas curvas sem visibilidade suficiente',
            '541-0 / 0: Estacionar em desacordo com as posições estabelecidas no CTB',
            '601-7 / 4: Executar operação de retorno passando por cima de canteiro de divisor de pista',
            '599-1 / 0: Executar operação de retorno em locais proibidos pela sinalização',
            '545-2 / 7: Estacionar ao lado ou sobre gramado ou jardim público'
        ]:
            return "DEMAIS MULTAS"
        else:
            return "NÃO MAPEADO"

    def definir_complemento2(enq):
        if enq == "745-5 / 0: Transitar em velocidade superior à máxima permitida em até 20%":
            return "INCISO I"
        elif enq == "746-3 / 0: Transitar em velocidade superior à máxima permitida em mais de 20% até 50%":
            return "INCISO II"
        elif enq == "747-1 / 0: Transitar em velocidade superior à máxima permitida em mais de 50%":
            return "INCISO III"
        elif enq == ("605-0 / 3: Avançar o sinal vermelho do semáforo, exc houver sinaliz perm livre conv"
                     " à direita -fiscalização eletrônica"):
            return "-"
        elif enq == "605-0 / 1: Avançar o sinal vermelho do semáforo":
            return "-"
        elif enq in [
            "683-1 / 2: Transitar com o veículo com excesso de peso - Por Eixo",
            "683-1 / 3: Transitar com o veículo com excesso de peso - PBT/PBTC e Por Eixo",
            "683-1 / 1: Transitar com o veículo com excesso de peso PBT/PBTC",
        ]:
            return "INCISO V"
        elif enq == "567-3 / 2: Parar sobre faixa de pedestres na mudança de sinal luminoso (fisc eletrônica)":
            return "PARAR SOBRE A FAIXA"
        elif enq == "581-9 / 7: Transitar com o veículo em acostamentos":
            return "TRANSITAR COM O VEÍCULO EM ACOSTAMENTOS"
        elif enq == "606-8 / 2: Deixar de adentrar às áreas destinadas à pesagem de veículos":
            return "DEIXAR DE ADENTRAR ÀS ÁREAS DESTINADAS À PESAGEM DE VEÍCULOS"
        elif enq == "583-5 / 0: Desobedecer às ordens emanadas da autorid compet de trânsito ou de seus agentes":
            return "Desobedecer às ordens emanadas da autorid compet de trânsito ou de seus agentes"
        elif enq == ('772-2 / 0: Quando o veículo estiver em movimento deixar de manter acesa a luz baixa de dia,'
                     ' em rodovias de pista simples situadas fora dos perímetros urbanos, no caso de veículos'
                     ' desprovidos de luzes de rodagem diurna'):
            return "Quando o veículo estiver em movimento deixar de manter acesa a luz baixa de dia"
        elif enq == '596-7 / 0: Ultrapassar pela contramão linha de divisão de fluxos opostos, contínua amarela':
            return 'Ultrapassar pela contramão linha de divisão de fluxos opostos, contínua amarela'
        elif enq == '581-9 / 4: Transitar com o veículo em canteiros centrais/divisores de pista de rolamento':
            return 'Transitar com o veículo em canteiros centrais/divisores de pista de rolamento'
        elif enq == '544-4 / 0: Estacionar nos acostamentos':
            return 'Art. 181, VII - 544-4 / 0: Estacionar nos acostamentos'
        elif enq == '579-7 / 0: Forçar passagem entre veícs trans sent opostos na iminência realiz ultrapassagem':
            return 'Art. 191, 579-7 / 0: Forçar passagem entre veícs trans sent opostos na iminência realiz ultrapass'
        elif enq == '545-2 / 5: Estacionar ao lado ou sobre canteiro central/divisores de pista de rolamento':
            return 'Art. 181/VIII, 545-2 / 5: Est. ao lado ou sobre canteiro central/divisores de pista de rolamento'
        elif enq == '704-8 / 1: Conduzir motocicleta, motoneta e ciclomotor transportando Passageiro s/ capacete.':
            return 'Art. 244, II - 704-8 / 1: Cond. moto, motoneta e ciclomotor transportando Passag. s/ capacete.'
        elif enq == '581-9 / 6: Transitar com o veículo em marcas de canalização':
            return 'Art. 193, 581-9 / 6: Transitar com o veículo em marcas de canalização'
        elif enq == '590-8 / 0: Ultrapassar pelo acostamento':
            return 'Art. 202, I, 590-8 / 0: Ultrapassar pelo acostamento'
        elif enq == '592-4 / 2: Ultrapassar pela contramão nos aclives ou declives, sem visibilidade suficiente':
            return 'Art. 203, I, 592-4 / 2: Ultrapassar pela contramão nos aclives ou declives, sem vis. suficiente'
        elif enq == '724-2 / 2: Em movimento de dia, deixar de manter acesa luz baixa sob chuva, neblina ou cerração':
            return 'Art. 250, I, b, Em mov. de dia, deixar de manter acesa luz baixa sob chuva, neblina ou cerração'
        elif enq == '518-5 / 1: Deixar o condutor de usar o cinto segurança':
            return 'Art. 167, 518-5 / 1: Deixar o condutor de usar o cinto segurança'
        elif enq == '518-5 / 2: Deixar o passageiro de usar o cinto segurança':
            return 'Art. 167, 518-5 / 2: Deixar o passageiro de usar o cinto segurança'
        elif enq == '731-5 / 0: Dirigir o veículo com o braço do lado de fora':
            return 'Art. 252, I, 731-5 / 0: Dirigir o veículo com o braço do lado de fora'
        elif enq == '676-9 / 0: Conduzir veíc c/ defeito no sist de iluminação, sinaliz ou lâmpadas queimadas':
            return '676-9 / 0: Conduzir veíc c/ defeito no sist de iluminação, sinaliz ou lâmpadas queimadas'
        elif enq == '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança':
            return '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança'
        elif enq == '584-3 / 3: Deixar de indicar c/ antec, med gesto de braço/luz indicadora, mudança direção':
            return '584-3 / 3: Deixar de indicar c/ antec, med gesto de braço/luz indicadora, mudança direção'
        elif enq == '501-0 / 0: Dirigir veículo sem possuir CNH/PPD/ACC':
            return '501-0 / 0: Dirigir veículo sem possuir CNH/PPD/ACC'
        elif enq == '506-1 / 0: Entregar veículo a pessoa sem CNH ou Permissão para Dirigir':
            return '506-1 / 0: Entregar veículo a pessoa sem CNH ou Permissão para Dirigir'
        elif enq == '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança':
            return '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança'
        elif enq == '658-0 / 0: Conduzir o veículo sem qualquer uma das placas de identificação':
            return '658-0 / 0: Conduzir o veículo sem qualquer uma das placas de identificação'
        elif enq == ('768-4 / 1: Conduzir motoc/ moton/ ciclom c/ utilização de capacete de segurança'
                     ' s/ viseira/óculos de proteção'):
            return '768-4 / 1: Conduzir motoc/ moton/ ciclom c/ ut. de capacete de seg. s/ viseira/óculos de prot.'
        elif enq == '734-0 / 0: Dirigir o veíc usando calçado que ñ se firme nos pés/comprometa utiliz pedais':
            return '734-0 / 0: Dirigir o veíc usando calçado que ñ se firme nos pés/comprometa utiliz pedais'
        elif enq == '684-0 / 2: Transitar com autorização vencida, expedida p/ veículo c/ dimensões excedentes':
            return 'Art. 231, VI, 684-0 / 2: Transitar com autorização vencida, expedida p/ veíc c/ dimensões exce.'
        elif enq == '736-6 / 2: Dirigir veículo utilizando-se de telefone celular':
            return 'Art. 252, VI- 736-6 / 2: Dirigir veículo utilizando-se de telefone celular'
        elif enq == '763-3 / 1: Dirigir veículo segurando telefone celular':
            return 'Art. 252, único, 763-3 / 1: Dirigir veículo segurando telefone celular'
        elif enq == '627-0 / 0: Deixar de reduzir a veloc onde o trânsito esteja sendo controlado pelo agente':
            return 'Art. 220, II - 627-0 / 0: Deixar de reduzir a veloc onde o trâns. esteja sendo controlado pelo agt.'
        elif enq == '682-3 / 1: Transitar c/ veíc e/ou carga c/ dimensões superiores limite legal s/ autorização':
            return 'Art. 231, IV, 682-3 / 1: Transi c/ veíc e/ou carga c/ dimensões sup. limite legal s/ autorização'
        elif enq == '659-9 / 2: Conduzir o veículo registrado que não esteja devidamente licenciado':
            return 'Art. 230, V, 659-9 / 2: Conduzir o veículo registrado que não esteja devidamente licenciado'
        elif enq == '703-0 / 1: Conduzir motocicleta, motoneta ou ciclomotor sem capacete de segurança':
            return 'Art. 244, I, 703-0 / 1: Conduzir motocicleta, motoneta ou ciclomotor sem capacete de segurança'
        elif enq == '500-2 / 0: Multa, por não identificação do condutor infrator, imposta à pessoa jurídica':
            return '257, § 8º, 500-2 / 0: Multa, por não identificação do condutor infrator, imposta à pessoa jurídica'
        elif enq == '672-6 / 1: Conduzir o veículo em mau estado de conservação, comprometendo a segurança':
            return 'Art.230, XVIII, 672-6 / 1: Conduzir o veíc em mau estado de conservação, comprometendo a segurança'
        elif enq == '592-4 / 1: Ultrapassar pela contramão nas curvas sem visibilidade suficiente':
            return 'Art. 203, I, 592-4 / 1: Ultrapassar pela contramão nas curvas sem visibilidade suficiente'
        elif enq == '541-0 / 0: Estacionar em desacordo com as posições estabelecidas no CTB':
            return 'Art. 181, IV, 541-0 / 0: Estacionar em desacordo com as posições estabelecidas no CTB'
        elif enq == '690-4 / 0: Transitar com o veículo excedendo a CMT acima de 1.000 kg':
            return 'Art. 231, X, 690-4 / 0: Transitar com o veículo excedendo a CMT acima de 1.000 k'
        elif enq == '601-7 / 4: Executar operação de retorno passando por cima de canteiro de divisor de pista':
            return 'Art. 206, II, 601-7 / 4: Exec op. de retorno passando por cima de canteiro de divisor de pista'
        elif enq == '599-1 / 0: Executar operação de retorno em locais proibidos pela sinalização':
            return 'Art. 206, I, 599-1 / 0: Executar operação de retorno em locais proibidos pela sinalização'
        elif enq == '545-2 / 7: Estacionar ao lado ou sobre gramado ou jardim público':
            return '545-2 / 7: Estacionar ao lado ou sobre gramado ou jardim público'
        else:
            return "NÃO MAPEADO"

    df_extraido.insert(1, 'Complemento1', df['Enquadramento - Auto de Infração'].apply(definir_complemento))
    df_extraido.insert(2, 'Complemento2', df['Enquadramento - Auto de Infração'].apply(definir_complemento2))
    df_extraido['Etiqueta'] = (
            df_extraido['EquipeSelecionada'].astype(str) + ' ' +
            df['Data da Prescrição Executória - Análise e Conferência Sapiens'].astype(str) + ' ' +
            df_extraido['Complemento1'].astype(str)
    )

    # Valor financeiro Atualizado
    # df_valor_atualizado = df['Valor Original - Financeiro'].astype(str).str.replace('R$', '', regex=False) \
    #     .str.replace('.', '', regex=False).str.replace(',', '.', regex=False).str.strip()
    # df_extraido.insert(7, 'Valor Original - Financeiro', df_valor_atualizado.astype(float))

    # Ordenação final
    ordem_colunas = [
        'NUP Sapiens',
        'Credor',
        'Complemento1',
        'Complemento2',
        'Número do Auto - Auto de Infração',
        'Devedor',
        'Data do Vencimento do Último Boleto - Análise e Conferência Sapiens',
        'Data de Início da Multa de Mora - Análise e Conferência Sapiens',
        'Data de Início da Taxa SELIC - Análise e Conferência Sapiens',
        'Valor Original - Financeiro',
        'Modalidade',
        'Número do Auto2',
        'Data da Infração',
        'Data da Notificação Inicial',
        'Const. Def. Cred',
        'Decurso do prazo da defesa',
        'Regional',
        'Unidade',
        'Etiqueta',
        'Prescrição Executória',
        'TecnicoAnalise',
        'DataAnalise',
        'TecnicoConferencia',
        'DataConferencia',
        'Data Cadastro ADM',
        'Data Cadastro Dívida',
        '30 Dias - Decadencial',
        '3 anos - Intercorrente',
        '5 anos - Executória',
        'Validação Data Infração vs Notificação',
        'Validação Data Infração vs Decurso Defesa',
        'Validação Decurso Defesa vs Notificação Inicial',
        'Validação Postagem NA x Publicação NA DOU',
        'Validação Vencimento NA x Postagem NP',
        'Validação Postagem NP x Publicação NP DOU',
        'Validação Postagem NP x Publicação NP DOU * (Duplicada)',
        'Validação Vencimento NP',
        'Validação Data Atual x Prescrição Executória',
        'Validação Utilizou AR NA ou Edital NA',
        'Validação Utilizou AR NP ou Edital NP',
        'Encaminhamento CCOBE *(Modificada)',
        'Recuperação de Crédito *(Modificada)',
        'Inscrito em DAU',
        'Data Inscrito *(Modificada)',
        'Supervisor',
        'Concat Devedor',
        'Equipe Nome',
        'Postagem NA Analise *(Duplicada)',
        'Defesa Data Protocolo',
        'Defesa Data Julgamento',
        'Data Ciência Decisão Defesa',
        'Postagem NA Analise',
        'Postagem NP Analise',
        'Veiculo',
        'Verificação NUP SIOR vs Sapiens',
        'Data Vencimento NA - Multa',
        'Data Vencimento NP - Multa',
        'Expedição NA',
        'Expedição NP',
        'Validação Data Infração x Notificação Inicial',
        'Validação Vencimento x Início Mora',
        'Validação Vencimento x Início Selic',
        'Validação Vencimento NA vs Edital',
        'Validação Vencimento NP vs Edital',
        'Validação Postagem NA divergente',
        'Validação Postagem NP divergente',
        'Situacao Débito',
        'Publicação Editalícia NA',
        'Publicação Editalícia NP',
        'Validação Prescrição vs Vencimento + 5 anos',
        'Validação Const. Def. divergente',
        'Validação Postagem NP e Cadin',
        'Data analise Vencimento NA 1',
        'Data analise Vencimento NA 2 (Edital)',
        'Data analise Vencimento NP 1',
        'Data analise Vencimento NP 2 (Edital)'
    ]

    # Garantir que as colunas de defesa existam no DataFrame, mesmo que não tenham sido extraídas
    colunas_defesa = [
        'Defesa Data Protocolo',
        'Defesa Data Julgamento',
        'Data Ciência Decisão Defesa'
    ]

    for col in colunas_defesa:
        if col not in df_extraido.columns:
            df_extraido[col] = None

    # Inserção dinâmica das colunas de defesa após 'Postagem NA Analise *(Duplicada)'
    posicao_referencia = ordem_colunas.index('Postagem NA Analise *(Duplicada)') + 1

    for idx, col in enumerate(colunas_defesa):
        if col not in ordem_colunas:
            ordem_colunas.insert(posicao_referencia + idx, col)

    df_extraido = df_extraido[ordem_colunas]
    fim = datetime.now()
    duracao = fim - inicio
    print(f"✅ Executado em {str(duracao).split('.')[0]}")
    return df_extraido


def validar_data_infracao_vs_notificacao(row):
    infracao = row['Data da Infração - Auto de Infração']
    dou = row['Data de Publicação no DOU - Notificação de Autuação [2]']
    entrega_ar = row['Data de Entrega do AR - Notificação de Autuação [2]']
    postagem = row['Data da Postagem - Notificação de Autuação [2]']

    # Verificação de "Não informado"
    dou_valido = dou != 'Não informado'
    entrega_ar_valido = entrega_ar != 'Não informado'
    postagem_valido = postagem != 'Não informado'

    # Conversão para datetime apenas se válido
    infracao_dt = pd.to_datetime(infracao, errors='coerce', dayfirst=True)
    dou_dt = pd.to_datetime(dou, errors='coerce', dayfirst=True) if dou_valido else pd.NaT
    entrega_ar_dt = pd.to_datetime(entrega_ar, errors='coerce', dayfirst=True) if entrega_ar_valido else pd.NaT
    postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True) if postagem_valido else pd.NaT

    # Lógica CASE adaptada
    if dou_valido:
        notificacao = dou_dt
    elif not dou_valido and not entrega_ar_valido:
        notificacao = postagem_dt
    else:
        notificacao = entrega_ar_dt

    if pd.isna(infracao_dt) or pd.isna(notificacao):
        return 'Data inválida ou ausente'

    if infracao_dt > notificacao:
        return 'Erro entre a data da infração para a data da notificação inicial'
    elif infracao_dt == notificacao:
        return 'Erro entre a data da infração é igual a data da notificação inicial'
    elif infracao_dt < notificacao:
        return 'Ok'
    else:
        return 'Indeterminado'


def validar_data_infracao_vs_decurso_defesa(row):
    infracao = row['Data da Infração - Auto de Infração']
    venc_edital = row['Data de Vencimento do Edital - Notificação de Autuação [2]']
    venc_comum = row['Data de Vencimento - Notificação de Autuação [2]']

    # Verificação de "Não informado"
    edital_valido = venc_edital != 'Não informado'
    comum_valido = venc_comum != 'Não informado'

    # Conversão para datetime se válido
    infracao_dt = pd.to_datetime(infracao, errors='coerce', dayfirst=True)
    edital_dt = pd.to_datetime(venc_edital, errors='coerce', dayfirst=True) if edital_valido else pd.NaT
    comum_dt = pd.to_datetime(venc_comum, errors='coerce', dayfirst=True) if comum_valido else pd.NaT

    # Lógica CASE equivalente
    if edital_valido:
        decurso_defesa = edital_dt
    else:
        decurso_defesa = comum_dt

    if pd.isna(infracao_dt) or pd.isna(decurso_defesa):
        return 'Data inválida ou ausente'

    if infracao_dt > decurso_defesa or infracao_dt == decurso_defesa:
        return 'Erro entre a data da infração para a data do decurso do prazo da defesa'
    elif infracao_dt < decurso_defesa:
        return 'Ok'
    else:
        return 'Indeterminado'


def validar_data_notificacao_inicial_vs_decurso_defesa(row):
    postagem = row['Data da Postagem - Notificação de Autuação [2]']
    venc_edital = row['Data de Vencimento do Edital - Notificação de Autuação [2]']
    venc_comum = row['Data de Vencimento - Notificação de Autuação [2]']

    # Verificação de "Não informado"
    edital_valido = venc_edital != 'Não informado'
    comum_valido = venc_comum != 'Não informado'
    postagem_valido = postagem != 'Não informado'

    # Conversão para datetime se válido
    postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True) if postagem_valido else pd.NaT
    edital_dt = pd.to_datetime(venc_edital, errors='coerce', dayfirst=True) if edital_valido else pd.NaT
    comum_dt = pd.to_datetime(venc_comum, errors='coerce', dayfirst=True) if comum_valido else pd.NaT

    # Lógica de escolha do vencimento
    if edital_valido:
        decurso_defesa = edital_dt
    else:
        decurso_defesa = comum_dt

    # Comparações
    if pd.isna(postagem_dt) or pd.isna(decurso_defesa):
        return 'Data inválida ou ausente'

    if postagem_dt > decurso_defesa:
        return 'Erro entre a data da infração para a data do decurso do prazo da defesa'
    elif postagem_dt == decurso_defesa:
        return 'Erro entre a dataN da infração para a data do decurso do prazo da defesa'
    elif postagem_dt < decurso_defesa:
        return 'Ok'
    else:
        return 'Indeterminado'


def validar_prescricao_intercorrente_postagem_vs_publicacao(row):
    postagem = row['Data da Postagem - Notificação de Autuação [2]']
    publicacao = row['Data de Publicação no DOU - Notificação de Autuação [2]']

    # Verificação "Não informado"
    publicacao_informado = publicacao != 'Não informado'
    postagem_informado = postagem != 'Não informado'

    # Se não houve publicação, retorna Ok
    if not publicacao_informado:
        return 'Ok'

    # Converte datas se informadas
    postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True) if postagem_informado else pd.NaT
    publicacao_dt = pd.to_datetime(publicacao, errors='coerce', dayfirst=True)

    if pd.isna(postagem_dt) or pd.isna(publicacao_dt):
        return 'Data inválida ou ausente'

    diff_dias = (publicacao_dt - postagem_dt).days

    if diff_dias >= 1096:
        return 'Prescrito Intercorrente NA para Publicação Ed. NA'
    elif diff_dias <= 1095:
        return 'Ok'
    else:
        return 'Indeterminado'


def validar_vencimento_na_vs_postagem_np(row):
    vencimento = row['Data de Vencimento do Edital - Notificação de Autuação [2]']
    postagem_np = row['Data da Postagem - Notificação de Penalidade [2]']

    # Verificações "Não informado"
    vencimento_valido = vencimento != 'Não informado'
    postagem_valido = postagem_np != 'Não informado'

    # Conversão para datetime se válido
    vencimento_dt = pd.to_datetime(vencimento, errors='coerce', dayfirst=True) if vencimento_valido else pd.NaT
    postagem_dt = pd.to_datetime(postagem_np, errors='coerce', dayfirst=True) if postagem_valido else pd.NaT

    if pd.isna(vencimento_dt) or pd.isna(postagem_dt):
        return 'Data não informada'

    diff_dias = (postagem_dt - vencimento_dt).days

    if diff_dias >= 1096:
        return 'Prescrito Intercorrente'
    elif diff_dias <= 1095:
        return 'Ok'
    else:
        return 'Indeterminado'


def validar_prescricao_postagem_np_vs_publicacao_np(row):
    postagem = row['Data da Postagem - Notificação de Penalidade [2]']
    publicacao = row['Data de Publicação no DOU - Notificação de Penalidade [2]']

    # Verificação de "Não informado"
    publicacao_informado = publicacao != 'Não informado'
    postagem_informado = postagem != 'Não informado'

    if not publicacao_informado:
        return 'Ok'

    # Conversão para datetime
    postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True) if postagem_informado else pd.NaT
    publicacao_dt = pd.to_datetime(publicacao, errors='coerce', dayfirst=True)

    if pd.isna(postagem_dt) or pd.isna(publicacao_dt):
        return 'Data inválida ou ausente'

    diff_dias = (publicacao_dt - postagem_dt).days

    if diff_dias >= 1096:
        return 'Prescrito Intercorrente NA para Publicação Ed. NP'
    elif diff_dias <= 1095:
        return 'Ok'
    else:
        return 'Indeterminado'


def validar_vencimento_np(row):
    vencimento = row['Data de Vencimento - Notificação de Penalidade [2]']

    if vencimento != 'Não informado':
        return 'Ok'
    else:
        return 'Data não informada'


def validar_prescricao_executoria_data_atual(row):
    prescricao = row['Data da Prescrição Executória - Análise e Conferência Sapiens']
    prescricao_valida = prescricao != 'Não informado'

    if not prescricao_valida:
        return 'Data não informada'

    prescricao_dt = pd.to_datetime(prescricao, errors='coerce', dayfirst=True)
    hoje = pd.Timestamp.today().normalize()

    if pd.isna(prescricao_dt):
        return 'Data inválida ou ausente'

    if hoje >= prescricao_dt:
        return 'Prescrito Executoriamente'
    else:
        return 'Ok'


def validar_utilizou_ar_ou_edital_na(row):
    publicacao_dou = row['Data de Publicação no DOU - Notificação de Autuação [2]']

    if publicacao_dou != 'Não informado':
        return 'Edital NA'
    else:
        return 'Ar_NA'


def validar_utilizou_ar_ou_edital_np(row):
    publicacao_dou = row['Data de Publicação no DOU - Notificação de Penalidade [2]']

    if publicacao_dou != 'Não informado':
        return 'Edital NP'
    else:
        return 'Ar_NP'


def validar_nup_sior_vs_sapiens(row):
    nup_sior = row['NUP Sapiens']
    nup_sapiens = row['NUP DNIT - Auto de Infração']

    if nup_sior == nup_sapiens:
        return 'Ok'
    else:
        return 'NUP SIOR é diferente do NUP Sapiens'


def validar_data_infracao_vs_data_notificacao_inicial(row):
    infracao = row['Data da Infração - Auto de Infração']
    dou = row['Data de Publicação no DOU - Notificação de Autuação [2]']
    entrega_ar = row['Data de Entrega do AR - Notificação de Autuação [2]']
    postagem = row['Data da Postagem - Notificação de Autuação [2]']

    # Verificação "Não informado"
    dou_informado = dou != 'Não informado'
    entrega_ar_informado = entrega_ar != 'Não informado'
    postagem_informado = postagem != 'Não informado'

    infracao_dt = pd.to_datetime(infracao, errors='coerce', dayfirst=True)
    dou_dt = pd.to_datetime(dou, errors='coerce', dayfirst=True) if dou_informado else pd.NaT
    entrega_dt = pd.to_datetime(entrega_ar, errors='coerce', dayfirst=True) if entrega_ar_informado else pd.NaT
    postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True) if postagem_informado else pd.NaT

    # Seleção da data de notificação
    if dou_informado:
        notificacao = dou_dt
    elif not dou_informado and not entrega_ar_informado:
        notificacao = postagem_dt
    else:
        notificacao = entrega_dt

    if pd.isna(infracao_dt) or pd.isna(notificacao):
        return 'Data inválida ou ausente'

    if infracao_dt > notificacao:
        return 'A Data da Infração é maior do que a Not. Inicial'
    else:
        return 'Ok'


def validar_vencimento_vs_multa_mora(row):
    vencimento = row['Data do Vencimento do Último Boleto - Análise e Conferência Sapiens']
    inicio_mora = row['Data de Início da Multa de Mora - Análise e Conferência Sapiens']

    vencimento_dt = pd.to_datetime(vencimento, errors='coerce', dayfirst=True)
    inicio_mora_dt = pd.to_datetime(inicio_mora, errors='coerce', dayfirst=True)

    if pd.isna(vencimento_dt) or pd.isna(inicio_mora_dt):
        return 'Data inválida ou ausente'

    if vencimento_dt > inicio_mora_dt:
        return 'A Data do Vencimento é maior do que a Inicio Mora'
    else:
        return 'Ok'


def validar_vencimento_vs_selic(row):
    vencimento = row['Data do Vencimento do Último Boleto - Análise e Conferência Sapiens']
    inicio_selic = row['Data de Início da Taxa SELIC - Análise e Conferência Sapiens']

    vencimento_dt = pd.to_datetime(vencimento, errors='coerce', dayfirst=True)
    selic_dt = pd.to_datetime(inicio_selic, errors='coerce', dayfirst=True)

    if pd.isna(vencimento_dt) or pd.isna(selic_dt):
        return 'Data inválida ou ausente'

    if selic_dt.day != 1:
        return 'A Data Selic não inicia com 01'
    elif vencimento_dt > selic_dt:
        return 'A Data do Vencimento é maior do que a Inicio Selic'
    else:
        return 'Ok'


def validar_vencimento_na(row):
    venc_na = row['Data de Vencimento - Notificação de Autuação [2]']
    venc_edital = row['Data de Vencimento do Edital - Notificação de Autuação [2]']

    # Ambos estão com 'Não informado'
    if venc_na == 'Não informado' and venc_edital == 'Não informado':
        return 'Data Vencimento Ausente'

    # Ambos estão preenchidos
    elif venc_na != 'Não informado' and venc_edital != 'Não informado':
        return 'Duplo preenchimento de Vencimento NA'

    # Apenas um preenchido (válido)
    else:
        return 'Ok'


def validar_vencimento_np_nova(row):
    venc_np = row['Data de Vencimento - Notificação de Penalidade [2]']
    venc_edital_np = row['Data de Vencimento do Edital - Notificação de Penalidade [2]']

    # Ambos estão com 'Não informado'
    if venc_np == 'Não informado' and venc_edital_np == 'Não informado':
        return 'Data Vencimento Ausente'

    # Ambos estão preenchidos
    elif venc_np != 'Não informado' and venc_edital_np != 'Não informado':
        return 'Duplo preenchimento de Vencimento NP'

    # Apenas um preenchido (válido)
    else:
        return 'Ok'


def validar_postagem_na_divergente(row):
    postagem_1 = row['Data da Postagem - Notificação de Autuação [2]']
    postagem_2 = row['Data da Postagem - Notificação de Autuação']

    if postagem_1 == postagem_2:
        return 'Ok'
    else:
        return 'Datas de Postagem NA divergente'


def validar_postagem_np_divergente(row):
    postagem_1 = row['Data da Postagem - Notificação de Penalidade [2]']
    postagem_2 = row['Data da Postagem - Notificação de Penalidade']

    if postagem_1 == postagem_2:
        return 'Ok'
    else:
        return 'Datas de Postagem NP divergente'


def validar_prescricao_por_vencimento(row):
    vencimento = row['Data do Vencimento do Último Boleto - Análise e Conferência Sapiens']
    prescricao = row['Data da Prescrição Executória - Análise e Conferência Sapiens']

    vencimento_dt = pd.to_datetime(vencimento, errors='coerce', dayfirst=True)
    prescricao_dt = pd.to_datetime(prescricao, errors='coerce', dayfirst=True)

    if pd.isna(vencimento_dt) or pd.isna(prescricao_dt):
        return 'Data inválida ou ausente'

    vencimento_mais_5 = vencimento_dt + pd.DateOffset(years=5)

    if vencimento_mais_5.date() == prescricao_dt.date():
        return 'Ok'
    else:
        return 'Data prescrição divergente'


def validar_const_def_divergente(row):
    data1 = row['Constituição Definitiva - Financeiro']
    data2 = row['Data da Constituição Definitiva - Análise e Conferência Sapiens']

    if data1 == data2:
        return 'Ok'
    else:
        return 'Datas de Constituição divergentes SIOR e Análise'


def validar_cadin_divergente(row):
    data1 = row['Data de Ciência CADIN - Análise e Conferência Sapiens']
    data2 = row['Data da Postagem - Notificação de Penalidade']

    if data1 == data2:
        return 'Ok'
    else:
        return 'Datas de Postagem NP SIOR e Cadin Divergentes'


def obter_data_ciencia_decisao_defesa(row):
    julgamento = row['Data do Julgamento - Defesa de Autuação [2]']
    postagem = row['Data da Postagem - Notificação de Penalidade [2]']

    if julgamento != 'Não informado':
        postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True)
        return postagem_dt.strftime('%d/%m/%Y') if not pd.isna(postagem_dt) else ''
    else:
        return ''


def inserir_colunas_defesa_condicional(df, df_extraido):
    # Define pares de coluna e nome desejado
    colunas_defesa = {
        'Data do Protocolo - Defesa de Autuação [2]': 'Defesa Data Protocolo',
        'Data do Julgamento - Defesa de Autuação [2]': 'Defesa Data Julgamento'
    }

    for col_original, col_nova in colunas_defesa.items():
        if col_original in df.columns:
            df_extraido[col_nova] = df[col_original]

    # Campo derivado de Data Ciência Decisão Defesa (condicional)
    if 'Data do Julgamento - Defesa de Autuação [2]' in df.columns and \
       'Data da Postagem - Notificação de Penalidade [2]' in df.columns:

        def obter_data_ciencia_decisao_defesa(row):
            julgamento = row['Data do Julgamento - Defesa de Autuação [2]']
            postagem = row['Data da Postagem - Notificação de Penalidade [2]']
            if julgamento != 'Não informado':
                postagem_dt = pd.to_datetime(postagem, errors='coerce', dayfirst=True)
                return postagem_dt.strftime('%d/%m/%Y') if not pd.isna(postagem_dt) else ''
            else:
                return ''

        df_extraido['Data Ciência Decisão Defesa'] = df.apply(obter_data_ciencia_decisao_defesa, axis=1)

    return df_extraido

