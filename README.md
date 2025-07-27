# Sistema de Gerenciamento de Estoque

Criei esse readme breve aqui só pra direcionar um pouco o satánas desse sistema, mas fique livre pra entrar em contato comigo e perguntar qualquer coisa.

As bibliotecas utilizadas foram o **Tkinter** para a interface gráfica e **SQLite** para a persistência de dados.

## Visão Geral

O sistema em si é um controle de inventário, tal como é solicitado na especificação do projeto. Portanto ele conta com as requerimentos solicitados pelo professor:

### **Product Catalog Management:** Adding, updating, and categorizing inventory items
Esse sisteminha infernal vai deixar que você possa adicionar, atualizar, categorizar e remover itens do inventário.
- **Interface:** A aba produtos centraliza todas essas operações.
- **Adicionar/Atualizar:** O formulário à esquerda vai possibilitar o cadastro de todos os novos produtos/edição do item selecionado na lista. O sistema vai validar os campos obrigatórios como nome, fornecedor e preços.
- **Adicionar/Atualizar:** Tem outros campos obrigatórios que eu não lembro agora 😋
- A categorização é feita na caixa de listagem "categoria" (quem diria), que permite selcionar categorias existentes ou adicionar uma nova que precisa ser... adicionada? 
- **Remoção:** Tambem é possível remover um ou mais produtos da lista para removê-los. Essa ação remove os produtos do banco de dados, e não pode ser desfeita

### **Stock Level Tracking:** Real-time tracking of inventory levels;
- **Estoque:** O estoque de um produto não é um valor único, mas sim um dicionário que mapeia cada Localização (como o "depósito central", "Loja A", etc.) à sua respectiva quantidade. O estoque total é, na verdade, uma soma das quantidades em todas as localizações.
- **Visualização detalhada:** Selecionando um único produto na lista, a tabela `"Estoque por Local do item sel.` vai exibir quantos exatas unidades cada localidade possui daquele item
- **Atualização Automática:** Qualquer operação atualiza instantaneamente os dados tanto em memória quanto no banco de dados, e carrega a interface.
- **Tô com sono:** É sério


### **Reorder Alerts:** Automated alerts for low stock and reorder points;

- **Ponto de Ressupr.:** Ao cadastrar ou atualizar um produto, um "Ponto de Ressuprimento" deve ser definido. Esse valor é o nível mínimo de estoque que, ao ser atingido, dispara um alertaaa.
- **Geraçao de Alertas:** E falando neles... Durante uma operaçao de saída (venda) que fez com que o produto atingisse ou ultrapassasse o ponto de ressuprimento, um alarme é ativado indicando a baixa desse produto no estoque.
- **Painel de Alertas:** Esses produtos em baixo estoque vão aparecer no `Painel Principal` na seção de `Alertar de baixo estoque`. Além disso, o nome da aba vai apresentar um (!) ao lado. 
> ☝️ O usuário vai poder utilizar do botão "Criar Ordem de Compra para Item Selecionado" para que possa rapidamente solicitar a compra desse produto para o estoque.

### **Supplier Management:** Managing information about suppliers;

A interface da aba `Fornecedors` é basicamente o CRUD de, adivinha só: Fornecedores!

Aqui o sistema vai armazenar o nome do contato, empresa, telefone email e endereço do indivíduo.

Como um produto nao existe sem um fornecedor, a exclusão de um fornecedor resulta na exclusão automática de todos os produtos associados a ele.

eh mole

### **Purchase Order Creation:** Generating and managing purchase orders
 O sistema tambem permite a geração e gerenciamentos de Ordens de Compra (OCs) para formalizar pedidos aos fornecedores. Eis o fluxo da coisa dentro da aba `Ordens de compra` (essa coisa ta começando a ficar muito óbvia):


1. Seleciona um fornecedor e os respectivos produtos do respectivo fornecedor
2. Os produtos escolhidos são adicionados a uma lista temporária
3. Ao salvar, a OC gerada é caregorizada como "Pendente"
4. Ao se receber os produtos, o usuário seleciona a OC e pode marcá-la como Recebida
5. O sistema vai então solicitar a **Localização** onde deve ser adicionado, e o estoque é atualizado automaticamente.

- É possível visualizar um recibo detalhado da OC e exportá-lo tanto para TXT quanto para PDF (o que vai precisar da biblioteca `reportlab`)
> Isso não é realmente necessário, o sistema vai funcionar normalmente sem isso. Porém é uma adição interessante para se usar.

### **Inventory Valuation:** Calculating the total value of the inventory on hand

Adivinha o que é que isso aqui faz, duvido

- **Cálculo:** O valor é calculado multiplicando a quantidade total de cada produto pelo seu `preço_compra`
- **Exibição:** O valor total do estoque é exibido de forma proeminente no Painel Principal e tambem no cabeçalho de relatórios de inventário. A lógica desse cálculo está na função `calcular_valor_total_estoque()`, da classe `GerenciadorEstoque` em `manager.py` 

### **Sales and Purchase History:** Tracking and analyzing sales and purchase data;
Todas as transações de entrada e saída são registradas, permitindo análise histórica.

De verdade não tem muito o que dizer aqui. A aba `Relatórios` mostra extratos completos de todas entradas, saídas e transferências para um produto específico. A aba `Ordens de Compras` funciona como um histórico de compras e os seus status permitem acompanhar o ciclo de vida de casda pedido.

E se esses fazem isso, imagina a aba que se chama `Histórico de Vendas`. Mas só por desencargo de consciência: Essa aba lista todas as vendas realizadas. Ao selecioanr uma venda, tabela ao lado detalha dos produtos, quantidades e valores daquela transação específica.


### **Multi-Location Management:** Managing inventory across multiple locations;
Esse diabinho aqui vai deixar você adicionar, gerenciar e rastrear através de múltiplos locais físicos
- A aba "Localizações e Transferências" permite o CRUD das localizações como armazéns, depósitos ou lojas.
- **Rastreamento Específico:** Como dito láaa no comecinho desse readme, o estoque de cada produto é rastreado individualmente para cada localização.
- Dentro da aba tambem é possível mover produtos entre localizações. O sistema vai validar se tem estoque o suficiente na origem, e registra a operação como uma saída da origem, para manter integro o histórico de movimentação. 



### **Inventory Reports:** Generating detailed reports on inventory status and movements.
Essa seção é dedicada para se gerar relatórios textuais detalhados sobre vários aspectos do inventário (ou ao menos todos os que eu consegui pensar). Todos disponíveis são:

- **Inventário Completo (Simplificado):** Lista todos os produtos com seus estoque total e detalhamento por local
- **Valor Total do Inventário:** Exibe o valor total do estoque com base no custo
- **Produtos com Baixo Estoque:** Lista somente os itens que atingiram o ponto de ressuprimento
- **Mais vendidos:** Ranking de produtos baseados na quantidade local vendida
- **Histórico de movimentação por Item:** Extrato detalhado para um produto
- **Relatório de Vendas por Período:** Analisa as vendas, receita e lucro dentro de um intervalo de datas inseridas pelo usuárioo

### **Barcode Scanning:** Integration of barcode scanning for inventory management.

Esse, no entanto, é um caso complicado. Eu não possuo nem tenho acesso a um leitor de código de barras fixo, portanto a solução que eu utilizei para (quase) implementar essa funcionalidade foi a seguinte:

Leitores de código de barras normalmente respondem ao computador como um teclado comum. A leitura é feita como se o número do código de barras fosse digitado e pressionado enter. Portanto, é justamente nisso que esse código se baseia.

Para utilizar dessa funcionalidade, basta digitar o número do código de barras em qualquer lugar sem foco da janela, ou seja, qualquer campo que nao seja um campo de entrada, caixa de listagem ou área de texto; só no "vazio" mesmo.

## Separação do código
O código está organizado em módulos para separar as responsabilidades:

- `main.py`: Ponto de entrada. Inicializa o banco de dados, o gerenciador e a interface gráfica
- `config.py`: Contém constante e configurações do projeto, tipo o nome do arquivo e do banco de dadooosossss
- `database.py`: Adivinha só
- `models.py`: Define a estrutura de todos os objetos de negócio (Produto, Fornecedor, Venda, etc.) usando `dataclasses`
- `manager.py`: Cérebro da aplicação, é aqui que está o desgraçado do `GerenciadorEstoque`. POssui toda a lógica de negócio e manipulação dos dados, sem interagir direamenet com a interface
- `gui.py`: De longe o arquivo com mais linhas. É a classe `App`, responsável por toda a interface gráfica com Tkinter. Constrói as telas, captura os eventos do usuário e chama os métodos do `GerenciadorEstoque`

## Estrutura do Código

O código está organizado em componentes principais:

- **Data Classes (@dataclass):** Localizadas no início do arquivo (região Data Classes), definem a estrutura de todos os objetos de negócio (Produto, Fornecedor, Venda, etc.). Elas servem como o "molde" para os dados da aplicação.

- **DatabaseManager:** Classe responsável por toda a interação com o banco de dados SQLite. Abstrai a execução de queries, conexões e commits.

- **GerenciadorEstoque:** O "cérebro" da aplicação. Contém toda a lógica de negócio:
  - Mantém o estado da aplicação em memória (dicionários de produtos, fornecedores, etc.) para acesso rápido.
  - Contém os métodos para carregar dados do banco, adicionar, atualizar, remover, movimentar estoque, criar OCs, registrar vendas e gerar relatórios.
  - Não interage diretamente com a interface gráfica.

- **App:** A classe responsável por toda a interface gráfica (coisa do Tkinter).
  - Constrói todas as janelas, abas, botões e tabelas.
  - Captura as interações do usuário (cliques, preenchimento de formulários).
  - Chama os métodos do GerenciadorEstoque para executar as ações solicitadas.
  - Atualiza a interface com base nos dados retornados pelo gerenciador.

## Como Executar o Projeto

### Pré-requisitos

- **Python 3.x**
- **Tkinter:** Geralmente já vem instalado com o Python no Windows. Se caso você estiver utilizando um Linux, pode ser necessário instalar:
  ```bash
  sudo apt-get install python3-tk
  ```
- **ReportLab (Opcional):** Necessário apenas para a funcionalidade de exportar recibos de Ordens de Compra para PDF (tudo vai funcionar normalmente sem).
> *Essa funcão de exportar os recibos em txt ou pdf foi só uma outra funçãozinha divertida que eu inseri, mas de novo, não é algo essencial pro programa. Esse sistema tá cheio dessas coisinhas, na verdade.*

### Instalação de Dependências

Para habilitar a exportação para PDF, instale a biblioteca reportlab:

```bash
pip install reportlab
```

### Execução

Para o executar esse diabo, basta clonar o repositório no seu ambiente e executar o arquivo a partir do seu terminal:

```bash
python main.py
```

### Primeira Execução

- Na primeira vez que o programa for executado, ele criará um arquivo de banco de dados chamado `estoque_database.db` no mesmo diretório.
- O sistema detectará que o banco está vazio e o populará com dados de exemplo (fornecedores, localizações e produtos) para que as funcionalidades possam ser testadas imediatamente.

#### Xero!
