# Flet
# ⚖️ LexTrack - RPA para Consulta e Extração de Dados no SIOR e Sapiens

**LexTrack** é um Robô de Processamento Automatizado (RPA) que facilita a consulta e o download de informações diretamente dos sistemas **SIOR** e **Sapiens**, com foco em **Autos de Infração (AITs)** e **créditos da dívida ativa**. A interface gráfica é intuitiva e desenvolvida com a biblioteca **Flet**, permitindo uma experiência fluida, segura e eficiente.

---

## 🚀 Funcionalidades

- 🔍 Consulta de AITs com filtros e exportação para Excel
- 📥 Download automático de relatórios **Financeiro** e/ou **Resumido** em PDF
- 💰 Consulta de créditos no **Sapiens Dívida** por CPF ou CNPJ
- 🔐 Armazenamento seguro de credenciais em cache local
- 📄 Interface por abas, com logs detalhados e exportáveis

---

## ⚙️ Requisitos

- **Python 3.10 ou superior**
- **Google Chrome** instalado
- **ChromeDriver** compatível com sua versão do Chrome
- Sistema operacional **Windows 10+**
- Permissões de leitura/gravação na pasta `Downloads`

---

## 🛠️ Instalação

1. **Clone o repositório:**
   ```bash
   git clone https://github.com/seu-usuario/lextrack-rpa.git
   cd lextrack-rpa
   

2. **Crie e ative um ambiente virtual:**

   No Windows:
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```
   
3. **Instale as dependências:**
    ```bash
   pip install -r requirements.txt
    ```
   
4. **Gerar o executável**
    ```bash
    pyinstaller app.py --onefile --noconfirm --clean
   

## 🖼️ Interface da Aplicação

A aplicação está organizada em uma interface com quatro abas principais, oferecendo uma experiência simples e eficiente:

---

### 🔍 1. Consulta AIT (SIOR)

Permite consultar Autos de Infração (AITs) no sistema SIOR com filtros e exportação.

**Funcionalidades:**
- Inserção de até **2000 códigos AIT** simultaneamente
- Validação automática do formato dos códigos
- Filtros por **Número do Auto**, **Situação da Fase**, e **Situação do Débito**
- Paginação de resultados com exibição em tabela
- Exportação para arquivo `.xlsx`

---

### 📥 2. Download de Relatórios (SIOR)

Gera automaticamente relatórios em PDF para os autos informados, com download direto.

**Funcionalidades:**
- Opções para baixar **Relatório Financeiro** e/ou **Relatório Resumido**
- Login automatizado (ou manual, se necessário)
- Armazenamento automático em pasta `Downloads/Relatórios [data]`
- Log detalhado da operação
- Barra de progresso e mensagens de status

---

### 📑 3. Consulta Crédito Sapiens (Dívida)

Consulta créditos da dívida ativa no sistema Sapiens usando CPF ou CNPJ do devedor.

**Funcionalidades:**
- Formatação automática do documento (removendo pontuação)
- Cache de credenciais em arquivo local `.sapiens_cache.json`
- Consulta de múltiplos dados: NUP, espécie do crédito, status, nome do devedor etc.
- Tabela com paginação e botão de exportação para Excel
- Log de execução e mensagens em tempo real

---

### ℹ️ 4. Sobre

Exibe informações úteis sobre a aplicação, dicas de uso e procedimentos em caso de erro.

**Conteúdo:**
- Instruções de uso para cada aba
- Recomendações em caso de falhas de login, cookies ou autenticação
- Boas práticas para garantir desempenho e confiabilidade


