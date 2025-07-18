import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, time
from collections import defaultdict, Counter
from dataclasses import dataclass, field
import sqlite3
import os  

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch
    REPORTLAB_DISPONIVEL = True
except ImportError:
    REPORTLAB_DISPONIVEL = False

DB_FILE = "estoque_database.db"

@dataclass
class Fornecedor:
    id: int
    nome: str
    contato: str
    email: str

    def __str__(self):
        return f"{self.id} - {self.nome}"

@dataclass
class Localizacao:
    id: int
    nome: str
    endereco: str = ""

    def __str__(self):
        return f"{self.id} - {self.nome}"

@dataclass
class Produto:
    id: int
    nome: str
    descricao: str
    categoria: str
    fornecedor: Fornecedor
    codigo_barras: str
    preco_compra: float
    preco_venda: float
    ponto_ressuprimento: int
    estoque_por_local: defaultdict[str, int] = field(default_factory=lambda: defaultdict(int))

    def get_estoque_total(self) -> int:
        return sum(self.estoque_por_local.values())

@dataclass
class HistoricoMovimento:
    produto: Produto
    tipo: str
    quantidade: int
    localizacao: Localizacao
    data: datetime = field(default_factory=datetime.now)

@dataclass
class ItemOrdemCompra:
    produto: Produto
    quantidade: int
    preco_unitario: float

    @property
    def subtotal(self) -> float:
        return self.quantidade * self.preco_unitario

@dataclass
class OrdemCompra:
    id: int
    fornecedor: Fornecedor
    itens: list[ItemOrdemCompra]
    status: str
    data_criacao: datetime = field(default_factory=datetime.now)

    @property
    def valor_total(self) -> float:
        return sum(item.subtotal for item in self.itens)

class DatabaseManager:
    def __init__(self, db_file):
        self.db_file = db_file
        self.conn = None
        self.cursor = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_file)
        self.conn.execute("PRAGMA foreign_keys = ON;") 
        self.cursor = self.conn.cursor()

    def close(self):
        if self.conn:
            self.conn.close()

    def execute_query(self, query, params=(), fetch=None):
        """Executa uma query genérica."""
        self.cursor.execute(query, params)
        if fetch == 'one':
            return self.cursor.fetchone()
        if fetch == 'all':
            return self.cursor.fetchall()
        self.conn.commit()
        return self.cursor.lastrowid

    def create_tables(self):
        """Cria todas as tabelas necessárias se elas não existirem."""
        queries = [
            """
            CREATE TABLE IF NOT EXISTS fornecedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                contato TEXT,
                email TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS localizacoes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL UNIQUE,
                endereco TEXT
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS produtos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                descricao TEXT,
                categoria TEXT,
                codigo_barras TEXT,
                preco_compra REAL NOT NULL,
                preco_venda REAL NOT NULL,
                ponto_ressuprimento INTEGER NOT NULL,
                fornecedor_id INTEGER NOT NULL,
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS estoque (
                produto_id INTEGER NOT NULL,
                localizacao_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                PRIMARY KEY (produto_id, localizacao_id),
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
                FOREIGN KEY (localizacao_id) REFERENCES localizacoes (id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS historico_movimentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                produto_id INTEGER NOT NULL,
                localizacao_id INTEGER NOT NULL,
                tipo TEXT NOT NULL,
                quantidade INTEGER NOT NULL,
                data TEXT NOT NULL,
                FOREIGN KEY (produto_id) REFERENCES produtos (id) ON DELETE CASCADE,
                FOREIGN KEY (localizacao_id) REFERENCES localizacoes (id) ON DELETE CASCADE
            );
            """,
             """
            CREATE TABLE IF NOT EXISTS ordens_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fornecedor_id INTEGER NOT NULL,
                status TEXT NOT NULL,
                data_criacao TEXT NOT NULL,
                FOREIGN KEY (fornecedor_id) REFERENCES fornecedores(id) ON DELETE CASCADE
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS itens_ordem_compra (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ordem_id INTEGER NOT NULL,
                produto_id INTEGER NOT NULL,
                quantidade INTEGER NOT NULL,
                preco_unitario REAL NOT NULL,
                FOREIGN KEY (ordem_id) REFERENCES ordens_compra(id) ON DELETE CASCADE,
                FOREIGN KEY (produto_id) REFERENCES produtos(id) ON DELETE CASCADE
            );
            """
        ]
        for query in queries:
            self.execute_query(query)

class GerenciadorEstoque:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.produtos: dict[int, Produto] = {}
        self.fornecedores: dict[int, Fornecedor] = {}
        self.localizacoes: dict[int, Localizacao] = {}
        self.historico: list[HistoricoMovimento] = []
        self.ordens_compra: dict[int, OrdemCompra] = {}

    def carregar_dados_do_banco(self):
        print("Carregando dados do banco...")
        for row in self.db.execute_query("SELECT * FROM fornecedores", fetch='all'):
            self.fornecedores[row[0]] = Fornecedor(*row)
            
        for row in self.db.execute_query("SELECT * FROM localizacoes", fetch='all'):
            self.localizacoes[row[0]] = Localizacao(*row)

        for row in self.db.execute_query("SELECT * FROM produtos", fetch='all'):
            prod_id, nome, desc, cat, cod, p_compra, p_venda, p_ress, forn_id = row
            fornecedor_obj = self.fornecedores.get(forn_id)
            if fornecedor_obj:
                self.produtos[prod_id] = Produto(prod_id, nome, desc, cat, fornecedor_obj, cod, p_compra, p_venda, p_ress)

        query = "SELECT p.id, l.nome, e.quantidade FROM estoque e JOIN produtos p ON e.produto_id = p.id JOIN localizacoes l ON e.localizacao_id = l.id"
        for prod_id, local_nome, qtd in self.db.execute_query(query, fetch='all'):
            if prod_id in self.produtos:
                self.produtos[prod_id].estoque_por_local[local_nome] = qtd
        
        query = "SELECT produto_id, localizacao_id, tipo, quantidade, data FROM historico_movimentos"
        for p_id, l_id, tipo, qtd, data_str in self.db.execute_query(query, fetch='all'):
             if (produto := self.produtos.get(p_id)) and (localizacao := self.localizacoes.get(l_id)):
                self.historico.append(HistoricoMovimento(produto, tipo, qtd, localizacao, datetime.fromisoformat(data_str)))

        for row in self.db.execute_query("SELECT * FROM ordens_compra", fetch='all'):
            oc_id, forn_id, status, data_str = row
            if fornecedor := self.fornecedores.get(forn_id):
                 self.ordens_compra[oc_id] = OrdemCompra(oc_id, fornecedor, [], status, datetime.fromisoformat(data_str))

        query = "SELECT ordem_id, produto_id, quantidade, preco_unitario FROM itens_ordem_compra"
        for oc_id, p_id, qtd, preco in self.db.execute_query(query, fetch='all'):
             if (oc := self.ordens_compra.get(oc_id)) and (produto := self.produtos.get(p_id)):
                 item = ItemOrdemCompra(produto, qtd, preco)
                 oc.itens.append(item)
        print("Dados carregados com sucesso.")

    def adicionar_fornecedor(self, **kwargs):
        query = "INSERT INTO fornecedores (nome, contato, email) VALUES (?, ?, ?)"
        params = (kwargs['nome'], kwargs.get('contato', ''), kwargs.get('email', ''))
        novo_id = self.db.execute_query(query, params)
        
        novo_fornecedor = Fornecedor(id=novo_id, **kwargs)
        self.fornecedores[novo_id] = novo_fornecedor
        return novo_fornecedor

    def adicionar_localizacao(self, **kwargs):
        query = "INSERT INTO localizacoes (nome, endereco) VALUES (?, ?)"
        params = (kwargs['nome'], kwargs.get('endereco', ''))
        novo_id = self.db.execute_query(query, params)

        nova_localizacao = Localizacao(id=novo_id, **kwargs)
        self.localizacoes[novo_id] = nova_localizacao
        return nova_localizacao

    def adicionar_produto(self, fornecedor_id, **kwargs):
        if not (fornecedor := self.fornecedores.get(fornecedor_id)):
            raise ValueError("Fornecedor não encontrado.")

        query = """INSERT INTO produtos (nome, descricao, categoria, codigo_barras, preco_compra, preco_venda, ponto_ressuprimento, fornecedor_id) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (
            kwargs['nome'], kwargs.get('descricao', ''), kwargs.get('categoria', ''), 
            kwargs.get('codigo_barras', ''), kwargs['preco_compra'], kwargs['preco_venda'], 
            kwargs['ponto_ressuprimento'], fornecedor_id
        )
        novo_id = self.db.execute_query(query, params)
        
        novo_produto = Produto(id=novo_id, fornecedor=fornecedor, **kwargs)
        self.produtos[novo_id] = novo_produto
        return novo_produto

    def atualizar_produto(self, produto_id, **kwargs):
        if produto_id not in self.produtos:
            return False
        
        query = """UPDATE produtos SET nome=?, descricao=?, categoria=?, codigo_barras=?, 
                   preco_compra=?, preco_venda=?, ponto_ressuprimento=?, fornecedor_id=?
                   WHERE id=?"""
        
        fornecedor_id = int(kwargs.get('fornecedor'))
        fornecedor_obj = self.fornecedores.get(fornecedor_id)
        if not fornecedor_obj: return False

        params = (
            kwargs['nome'], kwargs['descricao'], kwargs['categoria'], kwargs['codigo_barras'],
            kwargs['preco_compra'], kwargs['preco_venda'], kwargs['ponto_ressuprimento'],
            fornecedor_id, produto_id
        )
        self.db.execute_query(query, params)
        
        produto = self.produtos[produto_id]
        for key, value in kwargs.items():
            if key == 'fornecedor':
                setattr(produto, key, fornecedor_obj)
            elif hasattr(produto, key):
                setattr(produto, key, value)
        return True

    def remover_produto(self, produto_id):
        if produto_id in self.produtos:
            self.db.execute_query("DELETE FROM produtos WHERE id=?", (produto_id,))
            del self.produtos[produto_id]
            return True
        return False

    def movimentar_estoque(self, produto_id, localizacao_id, quantidade, tipo_movimento):
        produto = self.produtos.get(produto_id)
        localizacao = self.localizacoes.get(localizacao_id)
        if not all([produto, localizacao]):
            raise ValueError("Produto ou Localização inválido.")

        estoque_anterior = produto.get_estoque_total()
        estoque_local_anterior = produto.estoque_por_local.get(localizacao.nome, 0)

        if quantidade < 0 and estoque_local_anterior < abs(quantidade):
            raise ValueError(f"Estoque insuficiente de '{produto.nome}' em '{localizacao.nome}'.")
        
        novo_estoque_local = estoque_local_anterior + quantidade
        query_estoque = """
        INSERT INTO estoque (produto_id, localizacao_id, quantidade) VALUES (?, ?, ?)
        ON CONFLICT(produto_id, localizacao_id) DO UPDATE SET quantidade = ?;
        """
        self.db.execute_query(query_estoque, (produto_id, localizacao_id, novo_estoque_local, novo_estoque_local))
        
        agora = datetime.now()
        query_hist = "INSERT INTO historico_movimentos (produto_id, localizacao_id, tipo, quantidade, data) VALUES (?, ?, ?, ?, ?)"
        self.db.execute_query(query_hist, (produto_id, localizacao_id, tipo_movimento, quantidade, agora.isoformat()))
        
        produto.estoque_por_local[localizacao.nome] = novo_estoque_local
        self.historico.append(HistoricoMovimento(produto, tipo_movimento, quantidade, localizacao, agora))
        
        produto_para_alertar = None
        if estoque_anterior > produto.ponto_ressuprimento and produto.get_estoque_total() <= produto.ponto_ressuprimento:
            produto_para_alertar = produto

        return True, produto_para_alertar

    def criar_ordem_compra(self, fornecedor_id: int, itens_info: list[dict]) -> OrdemCompra:
        if not (fornecedor := self.fornecedores.get(fornecedor_id)):
            raise ValueError("Fornecedor não encontrado.")
        if not itens_info:
            raise ValueError("A ordem de compra deve ter pelo menos um item.")
        
        agora = datetime.now()
        query_oc = "INSERT INTO ordens_compra (fornecedor_id, status, data_criacao) VALUES (?, ?, ?)"
        novo_id_oc = self.db.execute_query(query_oc, (fornecedor_id, "Pendente", agora.isoformat()))

        itens_oc_obj = []
        for item_info in itens_info:
            produto_id = item_info['produto_id']
            quantidade = item_info['quantidade']
            if not (produto := self.produtos.get(produto_id)):
                raise ValueError(f"Produto com ID {produto_id} não encontrado.")
            if produto.fornecedor.id != fornecedor_id:
                raise ValueError(f"Produto '{produto.nome}' não pertence ao fornecedor '{fornecedor.nome}'.")

            preco_unitario = produto.preco_compra
            query_item = "INSERT INTO itens_ordem_compra (ordem_id, produto_id, quantidade, preco_unitario) VALUES (?, ?, ?, ?)"
            self.db.execute_query(query_item, (novo_id_oc, produto_id, quantidade, preco_unitario))
            
            item_obj = ItemOrdemCompra(produto, quantidade, preco_unitario)
            itens_oc_obj.append(item_obj)

        nova_ordem = OrdemCompra(novo_id_oc, fornecedor, itens_oc_obj, "Pendente", agora)
        self.ordens_compra[novo_id_oc] = nova_ordem
        return nova_ordem

    def atualizar_status_ordem(self, ordem_id: int, novo_status: str, localizacao_id: int | None = None):
        if not (ordem := self.ordens_compra.get(ordem_id)):
            raise ValueError("Ordem de Compra não encontrada.")

        if novo_status == "Recebida":
            if ordem.status == "Recebida":
                raise ValueError("Esta ordem já foi recebida.")
            if not localizacao_id or not (localizacao := self.localizacoes.get(localizacao_id)):
                raise ValueError("A localização é obrigatória e válida para receber uma ordem.")

            for item in ordem.itens:
                self.movimentar_estoque(
                    produto_id=item.produto.id,
                    localizacao_id=localizacao_id,
                    quantidade=item.quantidade,
                    tipo_movimento=f"Entrada OC #{ordem.id}"
                )
        
        self.db.execute_query("UPDATE ordens_compra SET status = ? WHERE id = ?", (novo_status, ordem_id))
        ordem.status = novo_status
        return True

    def verificar_alertas_ressuprimento(self):
        return [p for p in self.produtos.values() if p.get_estoque_total() <= p.ponto_ressuprimento]

    def calcular_valor_total_estoque(self):
        return sum(p.get_estoque_total() * p.preco_compra for p in self.produtos.values())
        
    def gerar_relatorio_estoque_simplificado(self):
        report = f"""RELATÓRIO DE ESTOQUE (SIMPLIFICADO)
Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Valor Total do Estoque: R$ {self.calcular_valor_total_estoque():.2f}
{'='*60}\n\n"""
        for produto in self.produtos.values():
            estoque_locais = "\n".join([f"     - {local}: {qtd} unidades" for local, qtd in produto.estoque_por_local.items() if qtd > 0])
            if not estoque_locais:
                estoque_locais = "     - Sem estoque registrado"

            report += f"""ID: {produto.id} - {produto.nome} ({produto.categoria})
   Estoque Total: {produto.get_estoque_total()} unidades
   Ponto de Ressuprimento: {produto.ponto_ressuprimento}
   Estoque por Local:
{estoque_locais}
{'-'*25}\n"""
        return report

    def gerar_relatorio_valor_total(self):
        valor_total = self.calcular_valor_total_estoque()
        return f"""RELATÓRIO DE VALOR TOTAL DO INVENTÁRIO
Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
{'='*60}
O valor total do seu inventário (baseado no preço de compra) é: R$ {valor_total:.2f}
"""

    def gerar_relatorio_baixo_estoque(self):
        produtos_baixo_estoque = self.verificar_alertas_ressuprimento()
        report = f"""RELATÓRIO DE PRODUTOS COM BAIXO ESTOQUE
Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
{'='*60}\n
"""
        if not produtos_baixo_estoque:
            return report + "Nenhum produto com baixo estoque no momento."
        
        for p in produtos_baixo_estoque:
            report += (f"ID: {p.id} - {p.nome}\n"
                       f"   Estoque Atual: {p.get_estoque_total()} | Mínimo Definido: {p.ponto_ressuprimento}\n\n")
        return report

    def gerar_relatorio_mais_vendidos(self):
        vendas = Counter()
        for mov in self.historico:
            if "Venda" in mov.tipo or "Saída" in mov.tipo:
                vendas[mov.produto.nome] += abs(mov.quantidade)
        
        report = f"""RELATÓRIO DE PRODUTOS MAIS VENDIDOS
Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
{'='*60}\n
"""
        if not vendas:
            return report + "Nenhuma venda registrada até o momento."
            
        for i, (nome_produto, qtd) in enumerate(vendas.most_common(), 1):
            report += f"{i}º. {nome_produto} - {qtd} unidades vendidas\n"
            
        return report

    def gerar_relatorio_movimentacao_item(self, produto_id: int):
        if not (produto := self.produtos.get(produto_id)):
            return "Erro: Produto não encontrado."

        movimentos_produto = [m for m in self.historico if m.produto.id == produto_id]

        report = f"""HISTÓRICO DE MOVIMENTAÇÃO DO PRODUTO: {produto.nome.upper()} (ID: {produto.id})
Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
{'='*70}\n
"""
        if not movimentos_produto:
            return report + "Nenhuma movimentação registrada para este produto."
        
        for mov in sorted(movimentos_produto, key=lambda m: m.data, reverse=True):
            sinal = '+' if mov.quantidade > 0 else ''
            report += (f"Data: {mov.data.strftime('%d/%m/%Y %H:%M')} | "
                       f"Tipo: {mov.tipo:<18} | "
                       f"Qtd: {sinal}{mov.quantidade:<4} | "
                       f"Local: {mov.localizacao.nome}\n")
        return report

    def gerar_relatorio_vendas_periodo(self, data_inicio: datetime, data_fim: datetime):
        vendas_periodo = [
            m for m in self.historico 
            if ("Venda" in m.tipo or "Saída" in m.tipo) and data_inicio <= m.data <= data_fim
        ]
        
        report = f"""RELATÓRIO DE VENDAS POR PERÍODO
Período: {data_inicio.strftime('%d/%m/%Y')} a {data_fim.strftime('%d/%m/%Y')}
{'='*70}\n
"""
        if not vendas_periodo:
            return report + "Nenhuma venda registrada no período selecionado."

        total_itens = 0
        receita_total = 0.0
        lucro_total = 0.0
        
        for venda in vendas_periodo:
            qtd_vendida = abs(venda.quantidade)
            receita_item = qtd_vendida * venda.produto.preco_venda
            lucro_item = qtd_vendida * (venda.produto.preco_venda - venda.produto.preco_compra)
            
            total_itens += qtd_vendida
            receita_total += receita_item
            lucro_total += lucro_item
            
            report += (f"Data: {venda.data.strftime('%d/%m/%Y')} | "
                       f"Produto: {venda.produto.nome:<25} | "
                       f"Qtd: {qtd_vendida}\n")
        
        report += f"\n{'-'*30}\nRESUMO DO PERÍODO\n{'-'*30}\n"
        report += f"Total de Itens Vendidos: {total_itens}\n"
        report += f"Receita Bruta Total: R$ {receita_total:.2f}\n"
        report += f"Lucro Bruto Total: R$ {lucro_total:.2f}\n"
        
        return report

class App:
    def __init__(self, root: tk.Tk, gerenciador: GerenciadorEstoque):
        self.root = root
        self.gerenciador = gerenciador
        self.root.title("Software de Gerenciamento de Estoque (com DB SQLite)")
        self.root.geometry("1280x780")

        self.vcmd_int = (self.root.register(lambda v: v.isdigit() or v == ""), '%P')
        self.vcmd_float = (self.root.register(self.validar_float), '%P')
        
        self.itens_oc_atual = []

        style = ttk.Style()
        style.theme_use('clam')
        style.map("Treeview", background=[('selected', '#B0E2FF')], foreground=[('selected', 'black')])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        self.criar_aba_dashboard()
        self.criar_aba_produtos()
        self.criar_aba_fornecedores()
        self.criar_aba_ordens_compra()
        self.criar_aba_relatorios()

        self.atualizar_tudo()

    def validar_float(self, val):
        if val == "": return True
        try:
            float(val.replace(',', '.'))
            return True
        except ValueError:
            return False

    def _criar_frame_com_titulo(self, parent, text):
        return ttk.LabelFrame(parent, text=text, padding=(10, 5))

    def _criar_campo_formulario(self, parent, texto_label, tipo_widget, grid_row, **kwargs):
        label = ttk.Label(parent, text=texto_label)
        label.grid(row=grid_row, column=0, sticky='w', padx=5, pady=5)
        
        widget = tipo_widget(parent, **kwargs)
        widget.grid(row=grid_row, column=1, sticky='ew', padx=5, pady=5)
        return widget

    def criar_aba_dashboard(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Painel Principal')

        frame_metricas = self._criar_frame_com_titulo(aba, "Métricas Principais")
        frame_metricas.pack(fill='x', pady=5)
        self.lbl_valor_estoque = ttk.Label(frame_metricas, text="Valor Total do Estoque: R$ 0.00", font=("Helvetica", 12, "bold"))
        self.lbl_valor_estoque.pack(pady=5, padx=10, anchor="w")
        self.lbl_itens_unicos = ttk.Label(frame_metricas, text="Itens Únicos: 0", font=("Helvetica", 12, "bold"))
        self.lbl_itens_unicos.pack(pady=5, padx=10, anchor="w")

        frame_alertas = self._criar_frame_com_titulo(aba, "Alertas de Baixo Estoque (Itens que precisam de reposição)")
        frame_alertas.pack(fill='both', expand=True, pady=10)
        self.tree_alertas = ttk.Treeview(frame_alertas, columns=("ID", "Nome", "Estoque Atual", "Mínimo"), show="headings")
        for col in self.tree_alertas['columns']:
            self.tree_alertas.heading(col, text=col)
        self.tree_alertas.pack(fill='both', expand=True)

    def criar_aba_produtos(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Produtos')

        left_container = ttk.Frame(aba)
        left_container.pack(side="left", fill="y", padx=(0, 10))

        form_frame = self._criar_frame_com_titulo(left_container, "Gerenciar Produto")
        form_frame.pack(fill="x", expand=False)

        self.entries_prod = {}
        campos = {
            "Nome:": (ttk.Entry, {}), "Descrição:": (ttk.Entry, {}),
            "Categoria:": (ttk.Combobox, {'values': ["Eletrônicos", "Periféricos", "Outro"]}),
            "Cód. Barras:": (ttk.Entry, {}), "Fornecedor:": (ttk.Combobox, {'state': 'readonly'}),
            "Preço Compra:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_float}),
            "Preço Venda:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_float}),
            "Ponto Ressupr.:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_int}),
            "Qtd. Inicial:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_int}),
            "Localização Inicial:": (ttk.Combobox, {'state': 'readonly'})
        }
        for i, (texto, (widget_class, kwargs)) in enumerate(campos.items()):
            self.entries_prod[texto] = self._criar_campo_formulario(form_frame, texto, widget_class, i, width=30, **kwargs)
        self.entries_prod["Categoria:"].set("Eletrônicos")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(campos), column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Adicionar Novo", command=self.adicionar_produto_gui).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Atualizar Selecionado", command=self.atualizar_produto_gui).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Remover Selecionado", command=self.remover_produto_gui).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(btn_frame, text="Limpar Formulário", command=self.limpar_formulario_produtos).grid(row=1, column=1, padx=5, pady=5)
        
        movimento_frame = self._criar_frame_com_titulo(left_container, "Movimentar Estoque do Item Selecionado")
        movimento_frame.pack(fill='x', expand=False, pady=(20, 0))

        self.mov_qtd = self._criar_campo_formulario(movimento_frame, "Quantidade:", ttk.Entry, 0, validate='key', validatecommand=self.vcmd_int)
        self.mov_local = self._criar_campo_formulario(movimento_frame, "Localização:", ttk.Combobox, 1, state='readonly')

        mov_btn_frame = ttk.Frame(movimento_frame)
        mov_btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(mov_btn_frame, text="Registrar Entrada (Compra)", command=lambda: self.movimentar_estoque_gui("Entrada")).pack(side="left", padx=5)
        ttk.Button(mov_btn_frame, text="Registrar Saída (Venda)", command=lambda: self.movimentar_estoque_gui("Saída")).pack(side="left", padx=5)

        table_frame = self._criar_frame_com_titulo(aba, "Catálogo de Produtos")
        table_frame.pack(side="right", fill='both', expand=True)
        self.tree_produtos = ttk.Treeview(table_frame, columns=("ID", "Nome", "Categoria", "Fornecedor", "Estoque", "Preço (R$)"), show="headings")
        col_widths = {"ID": 50, "Nome": 200, "Estoque": 80, "Preço (R$)": 100}
        for col in self.tree_produtos['columns']:
            self.tree_produtos.heading(col, text=col)
            self.tree_produtos.column(col, width=col_widths.get(col, 120), anchor='center' if col in ["ID", "Estoque"] else 'w')
        self.tree_produtos.column("Preço (R$)", anchor='e')
        self.tree_produtos.pack(fill='both', expand=True)
        self.tree_produtos.bind("<<TreeviewSelect>>", self.carregar_produto_para_formulario)

    def criar_aba_fornecedores(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Fornecedores')
        ttk.Label(aba, text="Gerenciamento de Fornecedores (a ser implementado)").pack(pady=20)

    def criar_aba_ordens_compra(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Ordens de Compra')
        
        main_pane = ttk.PanedWindow(aba, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        frame_criar = self._criar_frame_com_titulo(main_pane, "Criar Nova Ordem de Compra")
        main_pane.add(frame_criar, weight=1)

        frame_adicionar_item = ttk.Frame(frame_criar)
        frame_adicionar_item.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        
        self.oc_fornecedor_var = tk.StringVar()
        self.oc_combo_fornecedor = self._criar_campo_formulario(frame_adicionar_item, "Fornecedor:", ttk.Combobox, 0, state='readonly', textvariable=self.oc_fornecedor_var)
        self.oc_fornecedor_var.trace_add("write", self._atualizar_combo_produtos_oc)

        self.oc_combo_produto = self._criar_campo_formulario(frame_adicionar_item, "Produto:", ttk.Combobox, 1, state='readonly')
        self.oc_entry_quantidade = self._criar_campo_formulario(frame_adicionar_item, "Quantidade:", ttk.Entry, 2, validate='key', validatecommand=self.vcmd_int)
        
        btn_add_item = ttk.Button(frame_adicionar_item, text="Adicionar Item ➔", command=self._adicionar_item_oc_lista)
        btn_add_item.grid(row=3, column=0, columnspan=2, pady=10)

        frame_itens_oc = self._criar_frame_com_titulo(frame_criar, "Itens da Nova Ordem")
        frame_itens_oc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.tree_itens_nova_oc = ttk.Treeview(frame_itens_oc, columns=("ID", "Nome", "Qtd", "Preço Un.", "Subtotal"), show="headings")
        for col in self.tree_itens_nova_oc['columns']: self.tree_itens_nova_oc.heading(col, text=col)
        self.tree_itens_nova_oc.column("ID", width=40); self.tree_itens_nova_oc.column("Qtd", width=50); self.tree_itens_nova_oc.column("Preço Un.", width=80); self.tree_itens_nova_oc.column("Subtotal", width=80)
        self.tree_itens_nova_oc.pack(fill=tk.BOTH, expand=True)

        btn_remover_item = ttk.Button(frame_itens_oc, text="Remover Item Selecionado", command=self._remover_item_oc_lista)
        btn_remover_item.pack(pady=5)

        frame_salvar_oc = ttk.Frame(frame_criar)
        frame_salvar_oc.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        btn_salvar = ttk.Button(frame_salvar_oc, text="Salvar Ordem de Compra", command=self._salvar_oc)
        btn_salvar.pack(pady=10)
        btn_limpar = ttk.Button(frame_salvar_oc, text="Limpar Formulário", command=self._limpar_form_oc)
        btn_limpar.pack()

        frame_lista = self._criar_frame_com_titulo(main_pane, "Ordens de Compra Registradas")
        main_pane.add(frame_lista, weight=1)

        self.tree_lista_ocs = ttk.Treeview(frame_lista, columns=("ID", "Fornecedor", "Data", "Valor Total", "Status"), show="headings")
        for col in self.tree_lista_ocs['columns']: self.tree_lista_ocs.heading(col, text=col)
        self.tree_lista_ocs.pack(fill=tk.BOTH, expand=True, pady=5)

        frame_botoes_lista = ttk.Frame(frame_lista)
        frame_botoes_lista.pack(fill=tk.X, pady=5)
        ttk.Button(frame_botoes_lista, text="Visualizar/Salvar Recibo", command=self._visualizar_oc).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_lista, text="Marcar como Recebida", command=self._marcar_oc_recebida).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_lista, text="Marcar como Enviada", command=lambda: self._atualizar_status_oc_gui("Enviada")).pack(side=tk.LEFT, padx=5)

    def criar_aba_relatorios(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Relatórios')

        painel_controle = self._criar_frame_com_titulo(aba, "Opções de Relatório")
        painel_controle.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(painel_controle, text="Tipo de Relatório:").grid(row=0, column=0, sticky='w', padx=5, pady=(0, 5))
        self.relatorio_combo_tipo = ttk.Combobox(painel_controle, state='readonly', values=[
            "Inventário Completo (Simplificado)",
            "Valor Total do Inventário",
            "Produtos com Baixo Estoque",
            "Produtos Mais Vendidos",
            "Histórico de Movimentação por Item",
            "Relatório de Vendas por Período"
        ])
        self.relatorio_combo_tipo.grid(row=1, column=0, sticky='ew', padx=5, pady=(0, 10))
        self.relatorio_combo_tipo.bind("<<ComboboxSelected>>", self._atualizar_filtros_relatorio)

        self.relatorio_frame_filtros = self._criar_frame_com_titulo(painel_controle, "Filtros")
        self.relatorio_frame_filtros.grid(row=2, column=0, sticky='ew', padx=5)
        
        self.relatorio_lbl_produto = ttk.Label(self.relatorio_frame_filtros, text="Selecione o Produto:")
        self.relatorio_combo_produto = ttk.Combobox(self.relatorio_frame_filtros, state='readonly')
        
        self.relatorio_lbl_data_inicio = ttk.Label(self.relatorio_frame_filtros, text="Data de Início (DD/MM/AAAA):")
        self.relatorio_entry_data_inicio = ttk.Entry(self.relatorio_frame_filtros)
        self.relatorio_lbl_data_fim = ttk.Label(self.relatorio_frame_filtros, text="Data de Fim (DD/MM/AAAA):")
        self.relatorio_entry_data_fim = ttk.Entry(self.relatorio_frame_filtros)

        ttk.Button(painel_controle, text="Gerar Relatório", command=self._gerar_relatorio_detalhado_gui).grid(row=3, column=0, pady=20, padx=5)

        frame_resultado = self._criar_frame_com_titulo(aba, "Visualização do Relatório")
        frame_resultado.pack(side="right", fill="both", expand=True)

        self.txt_relatorio = tk.Text(frame_resultado, wrap='word', height=20, font=("Courier New", 10))
        self.txt_relatorio.pack(fill='both', expand=True)
    
    def _get_id_from_combobox(self, combo_value):
        try:
            return int(combo_value.split(" - ")[0])
        except (ValueError, IndexError):
            return None
        
    def _exibir_alerta_reabastecimento(self, produto: Produto):
        messagebox.showwarning(
            "Alerta de Reabastecimento",
            f"O estoque do produto atingiu o nível mínimo!\n\n"
            f"Produto: {produto.nome}\n"
            f"Estoque Atual: {produto.get_estoque_total()} unidades\n"
            f"Nível Mínimo: {produto.ponto_ressuprimento} unidades\n\n"
            "Recomenda-se criar uma nova Ordem de Compra."
        )

    def movimentar_estoque_gui(self, tipo):
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um produto da lista para movimentar o estoque.")

        produto_id = int(selected_items[0])
        
        try:
            quantidade = int(self.mov_qtd.get())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Erro", "Por favor, insira uma quantidade válida (número inteiro maior que zero).")

        localizacao_str = self.mov_local.get()
        if not localizacao_str:
            return messagebox.showerror("Erro", "Por favor, selecione uma localização.")
        
        localizacao_id = self._get_id_from_combobox(localizacao_str)
        produto_nome = self.gerenciador.produtos[produto_id].nome

        qtd_movimento = quantidade if tipo == "Entrada" else -quantidade
        tipo_movimento_str = "Compra/Entrada" if tipo == "Entrada" else "Venda/Saída"

        if messagebox.askyesno("Confirmar Movimentação", f"Confirma a {tipo.lower()} de {quantidade} unidade(s) de '{produto_nome}'?"):
            try:
                sucesso, produto_para_alertar = self.gerenciador.movimentar_estoque(produto_id, localizacao_id, qtd_movimento, tipo_movimento_str)
                if sucesso:
                    messagebox.showinfo("Sucesso", f"{tipo} registrada com sucesso!")
                    self.atualizar_tudo()
                    self.mov_qtd.delete(0, tk.END)
                    if produto_para_alertar:
                        self._exibir_alerta_reabastecimento(produto_para_alertar)
            except ValueError as e:
                messagebox.showerror("Erro de Estoque", str(e))
            except Exception as e:
                messagebox.showerror("Erro Inesperado", f"Ocorreu um erro: {str(e)}")

    def adicionar_produto_gui(self):
        dados = {k.replace(':', ''): v.get() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        if not all(obrigatorios):
            return messagebox.showerror("Erro", "Campos obrigatórios: Nome, Fornecedor, Preços e Ponto de Ressuprimento.")
        if dados['Qtd. Inicial'] and not dados['Localização Inicial']:
            return messagebox.showerror("Erro", "Se a quantidade inicial for informada, a localização é obrigatória.")

        try:
            fornecedor_id = self._get_id_from_combobox(dados['Fornecedor'])
            if not fornecedor_id:
                raise ValueError("Fornecedor inválido ou não selecionado.")

            preco_compra = float(dados['Preço Compra'].replace(',', '.'))
            preco_venda = float(dados['Preço Venda'].replace(',', '.'))

            novo_produto = self.gerenciador.adicionar_produto(
                nome=dados['Nome'], descricao=dados['Descrição'] or "N/A", categoria=dados['Categoria'] or "Outro",
                fornecedor_id=fornecedor_id,
                codigo_barras=dados['Cód. Barras'] or "N/A", preco_compra=preco_compra,
                preco_venda=preco_venda, ponto_ressuprimento=int(dados['Ponto Ressupr.'])
            )
            if dados['Qtd. Inicial']:
                local_id = self._get_id_from_combobox(dados['Localização Inicial'])
                if not local_id:
                    self.gerenciador.remover_produto(novo_produto.id)
                    raise ValueError("Localização inicial inválida ou não selecionada.")
                
                _, produto_para_alertar = self.gerenciador.movimentar_estoque(novo_produto.id, local_id, int(dados['Qtd. Inicial']), "Compra Inicial")
                if produto_para_alertar:
                    self._exibir_alerta_reabastecimento(produto_para_alertar)

            messagebox.showinfo("Sucesso", "Produto adicionado!")
            self.limpar_formulario_produtos()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Adicionar", str(e))

    def atualizar_produto_gui(self):
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um produto para atualizar.")
        
        dados = {k.replace(':', ''): v.get() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        if not all(obrigatorios):
            return messagebox.showerror("Erro", "Campos obrigatórios não podem ficar vazios na atualização.")

        try:
            fornecedor_id = self._get_id_from_combobox(dados['Fornecedor'])
            if not fornecedor_id:
                raise ValueError("Fornecedor inválido ou não selecionado.")
            
            preco_compra = float(dados['Preço Compra'].replace(',', '.'))
            preco_venda = float(dados['Preço Venda'].replace(',', '.'))

            dados_atualizados = {
                'nome': dados['Nome'], 'descricao': dados['Descrição'] or "N/A",
                'categoria': dados['Categoria'], 'codigo_barras': dados['Cód. Barras'] or "N/A",
                'preco_compra': preco_compra, 'preco_venda': preco_venda,
                'ponto_ressuprimento': int(dados['Ponto Ressupr.']),
                'fornecedor': str(fornecedor_id)
            }
            self.gerenciador.atualizar_produto(int(selected_items[0]), **dados_atualizados)
            messagebox.showinfo("Sucesso", "Produto atualizado!")
            self.limpar_formulario_produtos()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Atualizar", str(e))

    def remover_produto_gui(self):
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um produto para remover.")
        
        produto_id = int(selected_items[0])
        produto_nome = self.gerenciador.produtos[produto_id].nome
        if messagebox.askyesno("Confirmar Remoção", f"Tem certeza que deseja remover o produto '{produto_nome}'? Esta ação não pode ser desfeita e removerá todo o histórico associado."):
            if self.gerenciador.remover_produto(produto_id):
                messagebox.showinfo("Sucesso", "Produto removido!")
                self.limpar_formulario_produtos()
                self.atualizar_tudo()
            else:
                 messagebox.showerror("Erro", "Não foi possível remover o produto.")

    def carregar_produto_para_formulario(self, event=None):
        if not (selected_items := self.tree_produtos.selection()): return
        
        produto = self.gerenciador.produtos.get(int(selected_items[0]))
        if not produto: return

        for widget in self.entries_prod.values():
            widget.config(state='normal') 
            if isinstance(widget, ttk.Combobox):
                widget.set('')
            else:
                widget.delete(0, tk.END)

        self.entries_prod["Nome:"].insert(0, produto.nome)
        self.entries_prod["Descrição:"].insert(0, produto.descricao)
        self.entries_prod["Categoria:"].set(produto.categoria)
        self.entries_prod["Cód. Barras:"].insert(0, produto.codigo_barras)
        self.entries_prod["Preço Compra:"].insert(0, str(produto.preco_compra).replace('.', ','))
        self.entries_prod["Preço Venda:"].insert(0, str(produto.preco_venda).replace('.', ','))   
        self.entries_prod["Ponto Ressupr.:"].insert(0, str(produto.ponto_ressuprimento))
        self.entries_prod["Fornecedor:"].set(str(produto.fornecedor))
        
        self.entries_prod["Qtd. Inicial:"].config(state='disabled')
        self.entries_prod["Localização Inicial:"].config(state='disabled')
        self.entries_prod["Fornecedor:"].config(state='readonly')
        self.entries_prod["Categoria:"].config(state='readonly')

    def limpar_formulario_produtos(self):
        if self.tree_produtos.selection():
            self.tree_produtos.selection_remove(self.tree_produtos.selection())
            
        for widget in self.entries_prod.values():
            if isinstance(widget, ttk.Combobox):
                widget.set('')
                widget.config(state='readonly')
            else:
                widget.config(state='normal')
                widget.delete(0, tk.END)
        self.entries_prod["Categoria:"].set("Eletrônicos")
        self.mov_qtd.delete(0, tk.END)
        self.mov_local.set('')

    def _atualizar_combo_produtos_oc(self, *args):
        self.oc_combo_produto.set('')
        fornecedor_id = self._get_id_from_combobox(self.oc_fornecedor_var.get())
        if not fornecedor_id:
            self.oc_combo_produto['values'] = []
            return
        
        produtos_fornecedor = [
            f"{p.id} - {p.nome}" for p in self.gerenciador.produtos.values()
            if p.fornecedor.id == fornecedor_id
        ]
        self.oc_combo_produto['values'] = produtos_fornecedor

    def _adicionar_item_oc_lista(self):
        try:
            produto_id = self._get_id_from_combobox(self.oc_combo_produto.get())
            if not produto_id:
                raise ValueError("Selecione um produto.")
            
            quantidade = int(self.oc_entry_quantidade.get())
            if quantidade <= 0:
                raise ValueError("A quantidade deve ser maior que zero.")
            
            produto = self.gerenciador.produtos[produto_id]

            for item in self.itens_oc_atual:
                if item['produto_id'] == produto_id:
                    item['quantidade'] += quantidade
                    item['subtotal'] = item['quantidade'] * item['preco_unitario']
                    self._atualizar_tree_itens_nova_oc()
                    return

            self.itens_oc_atual.append({
                "produto_id": produto.id,
                "nome": produto.nome,
                "quantidade": quantidade,
                "preco_unitario": produto.preco_compra,
                "subtotal": quantidade * produto.preco_compra
            })
            self._atualizar_tree_itens_nova_oc()
            self.oc_combo_produto.set('')
            self.oc_entry_quantidade.delete(0, 'end')

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _remover_item_oc_lista(self):
        if not (selected_tree_items := self.tree_itens_nova_oc.selection()):
            return messagebox.showwarning("Aviso", "Selecione um item da lista para remover.")
        
        item_id = int(selected_tree_items[0])
        self.itens_oc_atual = [item for item in self.itens_oc_atual if item['produto_id'] != item_id]
        self._atualizar_tree_itens_nova_oc()

    def _salvar_oc(self):
        if not self.itens_oc_atual:
            return messagebox.showerror("Erro", "Adicione pelo menos um item à ordem de compra.")
        
        fornecedor_id = self._get_id_from_combobox(self.oc_fornecedor_var.get())
        if not fornecedor_id:
            return messagebox.showerror("Erro", "Selecione um fornecedor.")

        try:
            self.gerenciador.criar_ordem_compra(fornecedor_id, self.itens_oc_atual)
            messagebox.showinfo("Sucesso", "Ordem de Compra criada com sucesso!")
            self._limpar_form_oc()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", str(e))

    def _limpar_form_oc(self):
        self.oc_fornecedor_var.set('')
        self.oc_combo_produto.set('')
        self.oc_combo_produto['values'] = []
        self.oc_entry_quantidade.delete(0, tk.END)
        self.itens_oc_atual.clear()
        self._atualizar_tree_itens_nova_oc()

    def _marcar_oc_recebida(self):
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        ordem = self.gerenciador.ordens_compra.get(ordem_id)

        if ordem.status == "Recebida":
            return messagebox.showinfo("Informação", "Esta ordem já foi recebida.")

        localizacoes = list(self.gerenciador.localizacoes.values())
        if not localizacoes:
            return messagebox.showerror("Erro", "Nenhuma localização de estoque cadastrada. Cadastre uma localização primeiro.")
        
        local_selecionada = simpledialog.askstring("Selecionar Localização", 
            "Em qual localização o estoque será recebido?\n\nDigite o ID da localização desejada:\n" + "\n".join([str(l) for l in localizacoes]),
            parent=self.root)
        
        if not local_selecionada: return
        
        try:
            local_id = int(local_selecionada)
            if local_id not in self.gerenciador.localizacoes:
                raise ValueError("ID de localização inválido.")

            self.gerenciador.atualizar_status_ordem(ordem_id, "Recebida", localizacao_id=local_id)
            messagebox.showinfo("Sucesso", f"Ordem de Compra #{ordem_id} marcada como recebida!\nEstoque atualizado.")
            self.atualizar_tudo()

        except ValueError:
             messagebox.showerror("Erro", "Por favor, insira um ID de localização válido (apenas números).")
        except Exception as e:
            messagebox.showerror("Erro", str(e))
    
    def _atualizar_status_oc_gui(self, novo_status: str):
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        
        try:
            self.gerenciador.atualizar_status_ordem(ordem_id, novo_status)
            messagebox.showinfo("Sucesso", f"Status da Ordem de Compra #{ordem_id} atualizado para '{novo_status}'.")
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
    
    def _visualizar_oc(self):
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        ordem = self.gerenciador.ordens_compra.get(ordem_id)
        if not ordem: return

        top = tk.Toplevel(self.root)
        top.title(f"Recibo da Ordem de Compra #{ordem.id}")
        top.geometry("650x500")
        top.transient(self.root)
        top.grab_set()

        frame_visualizacao = ttk.Frame(top)
        frame_visualizacao.pack(fill=tk.BOTH, expand=True)

        frame_texto = ttk.Frame(frame_visualizacao, padding=10)
        frame_texto.pack(fill=tk.X)

        texto_cabecalho = f"""ORDEM DE COMPRA (PURCHASE ORDER)
Número: {ordem.id} | Data: {ordem.data_criacao.strftime('%d/%m/%Y %H:%M:%S')} | Status: {ordem.status}

PARA:
{ordem.fornecedor.nome} (ID: {ordem.fornecedor.id})
Contato: {ordem.fornecedor.contato} | Email: {ordem.fornecedor.email}
"""
        lbl_cabecalho = ttk.Label(frame_texto, text=texto_cabecalho, justify=tk.LEFT, font=("Courier New", 10))
        lbl_cabecalho.pack(anchor='w')

        frame_itens = self._criar_frame_com_titulo(frame_visualizacao, "Itens do Pedido")
        frame_itens.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        itens_tree = ttk.Treeview(frame_itens, columns=("ID", "Produto", "Qtd", "Preço Un.", "Subtotal"), show="headings")
        itens_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(frame_itens, orient="vertical", command=itens_tree.yview)

class App:
    def __init__(self, root: tk.Tk, gerenciador: GerenciadorEstoque):
        self.root = root
        self.gerenciador = gerenciador
        self.root.title("Software de Gerenciamento de Estoque (com DB SQLite)")
        self.root.geometry("1280x780")

        self.vcmd_int = (self.root.register(lambda v: v.isdigit() or v == ""), '%P')
        self.vcmd_float = (self.root.register(self.validar_float), '%P')
        
        self.itens_oc_atual = []

        style = ttk.Style()
        style.theme_use('clam')
        style.map("Treeview", background=[('selected', '#B0E2FF')], foreground=[('selected', 'black')])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        self.criar_aba_dashboard()
        self.criar_aba_produtos()
        self.criar_aba_fornecedores()
        self.criar_aba_ordens_compra()
        self.criar_aba_relatorios()

        self.atualizar_tudo()

    def validar_float(self, val):
        if val == "": return True
        try:
            float(val.replace(',', '.')) 
            return True
        except ValueError:
            return False

    def _criar_frame_com_titulo(self, parent, text):
        return ttk.LabelFrame(parent, text=text, padding=(10, 5))

    def _criar_campo_formulario(self, parent, texto_label, tipo_widget, grid_row, **kwargs):
        label = ttk.Label(parent, text=texto_label)
        label.grid(row=grid_row, column=0, sticky='w', padx=5, pady=5)
        
        widget = tipo_widget(parent, **kwargs)
        widget.grid(row=grid_row, column=1, sticky='ew', padx=5, pady=5)
        return widget

    def criar_aba_dashboard(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Painel Principal')

        frame_metricas = self._criar_frame_com_titulo(aba, "Métricas Principais")
        frame_metricas.pack(fill='x', pady=5)
        self.lbl_valor_estoque = ttk.Label(frame_metricas, text="Valor Total do Estoque: R$ 0.00", font=("Helvetica", 12, "bold"))
        self.lbl_valor_estoque.pack(pady=5, padx=10, anchor="w")
        self.lbl_itens_unicos = ttk.Label(frame_metricas, text="Itens Únicos: 0", font=("Helvetica", 12, "bold"))
        self.lbl_itens_unicos.pack(pady=5, padx=10, anchor="w")

        frame_alertas = self._criar_frame_com_titulo(aba, "Alertas de Baixo Estoque (Itens que precisam de reposição)")
        frame_alertas.pack(fill='both', expand=True, pady=10)
        self.tree_alertas = ttk.Treeview(frame_alertas, columns=("ID", "Nome", "Estoque Atual", "Mínimo"), show="headings")
        for col in self.tree_alertas['columns']:
            self.tree_alertas.heading(col, text=col)
        self.tree_alertas.pack(fill='both', expand=True)

    def criar_aba_produtos(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Produtos')

        left_container = ttk.Frame(aba)
        left_container.pack(side="left", fill="y", padx=(0, 10))

        form_frame = self._criar_frame_com_titulo(left_container, "Gerenciar Produto")
        form_frame.pack(fill="x", expand=False)

        self.entries_prod = {}
        campos = {
            "Nome:": (ttk.Entry, {}), "Descrição:": (ttk.Entry, {}),
            "Categoria:": (ttk.Combobox, {'values': ["Eletrônicos", "Periféricos", "Outro"]}),
            "Cód. Barras:": (ttk.Entry, {}), "Fornecedor:": (ttk.Combobox, {'state': 'readonly'}),
            "Preço Compra:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_float}),
            "Preço Venda:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_float}),
            "Ponto Ressupr.:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_int}),
            "Qtd. Inicial:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_int}),
            "Localização Inicial:": (ttk.Combobox, {'state': 'readonly'})
        }
        for i, (texto, (widget_class, kwargs)) in enumerate(campos.items()):
            self.entries_prod[texto] = self._criar_campo_formulario(form_frame, texto, widget_class, i, width=30, **kwargs)
        self.entries_prod["Categoria:"].set("Eletrônicos")

        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(campos), column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Adicionar Novo", command=self.adicionar_produto_gui).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Atualizar Selecionado", command=self.atualizar_produto_gui).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Remover Selecionado", command=self.remover_produto_gui).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(btn_frame, text="Limpar Formulário", command=self.limpar_formulario_produtos).grid(row=1, column=1, padx=5, pady=5)
        
        movimento_frame = self._criar_frame_com_titulo(left_container, "Movimentar Estoque do Item Selecionado")
        movimento_frame.pack(fill='x', expand=False, pady=(20, 0))

        self.mov_qtd = self._criar_campo_formulario(movimento_frame, "Quantidade:", ttk.Entry, 0, validate='key', validatecommand=self.vcmd_int)
        self.mov_local = self._criar_campo_formulario(movimento_frame, "Localização:", ttk.Combobox, 1, state='readonly')

        mov_btn_frame = ttk.Frame(movimento_frame)
        mov_btn_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(mov_btn_frame, text="Registrar Entrada (Compra)", command=lambda: self.movimentar_estoque_gui("Entrada")).pack(side="left", padx=5)
        ttk.Button(mov_btn_frame, text="Registrar Saída (Venda)", command=lambda: self.movimentar_estoque_gui("Saída")).pack(side="left", padx=5)

        table_frame = self._criar_frame_com_titulo(aba, "Catálogo de Produtos")
        table_frame.pack(side="right", fill='both', expand=True)
        self.tree_produtos = ttk.Treeview(table_frame, columns=("ID", "Nome", "Categoria", "Fornecedor", "Estoque", "Preço (R$)"), show="headings")
        col_widths = {"ID": 50, "Nome": 200, "Estoque": 80, "Preço (R$)": 100}
        for col in self.tree_produtos['columns']:
            self.tree_produtos.heading(col, text=col)
            self.tree_produtos.column(col, width=col_widths.get(col, 120), anchor='center' if col in ["ID", "Estoque"] else 'w')
        self.tree_produtos.column("Preço (R$)", anchor='e')
        self.tree_produtos.pack(fill='both', expand=True)
        self.tree_produtos.bind("<<TreeviewSelect>>", self.carregar_produto_para_formulario)

    def criar_aba_fornecedores(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Fornecedores')
        ttk.Label(aba, text="Gerenciamento de Fornecedores (a ser implementado)").pack(pady=20)

    def criar_aba_ordens_compra(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Ordens de Compra')
        
        main_pane = ttk.PanedWindow(aba, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        frame_criar = self._criar_frame_com_titulo(main_pane, "Criar Nova Ordem de Compra")
        main_pane.add(frame_criar, weight=1)

        frame_adicionar_item = ttk.Frame(frame_criar)
        frame_adicionar_item.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        
        self.oc_fornecedor_var = tk.StringVar()
        self.oc_combo_fornecedor = self._criar_campo_formulario(frame_adicionar_item, "Fornecedor:", ttk.Combobox, 0, state='readonly', textvariable=self.oc_fornecedor_var)
        self.oc_fornecedor_var.trace_add("write", self._atualizar_combo_produtos_oc)

        self.oc_combo_produto = self._criar_campo_formulario(frame_adicionar_item, "Produto:", ttk.Combobox, 1, state='readonly')
        self.oc_entry_quantidade = self._criar_campo_formulario(frame_adicionar_item, "Quantidade:", ttk.Entry, 2, validate='key', validatecommand=self.vcmd_int)
        
        btn_add_item = ttk.Button(frame_adicionar_item, text="Adicionar Item ➔", command=self._adicionar_item_oc_lista)
        btn_add_item.grid(row=3, column=0, columnspan=2, pady=10)

        frame_itens_oc = self._criar_frame_com_titulo(frame_criar, "Itens da Nova Ordem")
        frame_itens_oc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.tree_itens_nova_oc = ttk.Treeview(frame_itens_oc, columns=("ID", "Nome", "Qtd", "Preço Un.", "Subtotal"), show="headings")
        for col in self.tree_itens_nova_oc['columns']: self.tree_itens_nova_oc.heading(col, text=col)
        self.tree_itens_nova_oc.column("ID", width=40); self.tree_itens_nova_oc.column("Qtd", width=50); self.tree_itens_nova_oc.column("Preço Un.", width=80); self.tree_itens_nova_oc.column("Subtotal", width=80)
        self.tree_itens_nova_oc.pack(fill=tk.BOTH, expand=True)

        btn_remover_item = ttk.Button(frame_itens_oc, text="Remover Item Selecionado", command=self._remover_item_oc_lista)
        btn_remover_item.pack(pady=5)

        frame_salvar_oc = ttk.Frame(frame_criar)
        frame_salvar_oc.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        btn_salvar = ttk.Button(frame_salvar_oc, text="Salvar Ordem de Compra", command=self._salvar_oc)
        btn_salvar.pack(pady=10)
        btn_limpar = ttk.Button(frame_salvar_oc, text="Limpar Formulário", command=self._limpar_form_oc)
        btn_limpar.pack()

        frame_lista = self._criar_frame_com_titulo(main_pane, "Ordens de Compra Registradas")
        main_pane.add(frame_lista, weight=1)

        self.tree_lista_ocs = ttk.Treeview(frame_lista, columns=("ID", "Fornecedor", "Data", "Valor Total", "Status"), show="headings")
        for col in self.tree_lista_ocs['columns']: self.tree_lista_ocs.heading(col, text=col)
        self.tree_lista_ocs.pack(fill=tk.BOTH, expand=True, pady=5)

        frame_botoes_lista = ttk.Frame(frame_lista)
        frame_botoes_lista.pack(fill=tk.X, pady=5)
        ttk.Button(frame_botoes_lista, text="Visualizar/Salvar Recibo", command=self._visualizar_oc).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_lista, text="Marcar como Recebida", command=self._marcar_oc_recebida).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_lista, text="Marcar como Enviada", command=lambda: self._atualizar_status_oc_gui("Enviada")).pack(side=tk.LEFT, padx=5)

    def criar_aba_relatorios(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Relatórios')

        painel_controle = self._criar_frame_com_titulo(aba, "Opções de Relatório")
        painel_controle.pack(side="left", fill="y", padx=(0, 10))

        ttk.Label(painel_controle, text="Tipo de Relatório:").grid(row=0, column=0, sticky='w', padx=5, pady=(0, 5))
        self.relatorio_combo_tipo = ttk.Combobox(painel_controle, state='readonly', values=[
            "Inventário Completo (Simplificado)",
            "Valor Total do Inventário",
            "Produtos com Baixo Estoque",
            "Produtos Mais Vendidos",
            "Histórico de Movimentação por Item",
            "Relatório de Vendas por Período"
        ])
        self.relatorio_combo_tipo.grid(row=1, column=0, sticky='ew', padx=5, pady=(0, 10))
        self.relatorio_combo_tipo.bind("<<ComboboxSelected>>", self._atualizar_filtros_relatorio)

        self.relatorio_frame_filtros = self._criar_frame_com_titulo(painel_controle, "Filtros")
        self.relatorio_frame_filtros.grid(row=2, column=0, sticky='ew', padx=5)
        
        self.relatorio_lbl_produto = ttk.Label(self.relatorio_frame_filtros, text="Selecione o Produto:")
        self.relatorio_combo_produto = ttk.Combobox(self.relatorio_frame_filtros, state='readonly')
        
        self.relatorio_lbl_data_inicio = ttk.Label(self.relatorio_frame_filtros, text="Data de Início (DD/MM/AAAA):")
        self.relatorio_entry_data_inicio = ttk.Entry(self.relatorio_frame_filtros)
        self.relatorio_lbl_data_fim = ttk.Label(self.relatorio_frame_filtros, text="Data de Fim (DD/MM/AAAA):")
        self.relatorio_entry_data_fim = ttk.Entry(self.relatorio_frame_filtros)

        ttk.Button(painel_controle, text="Gerar Relatório", command=self._gerar_relatorio_detalhado_gui).grid(row=3, column=0, pady=20, padx=5)

        frame_resultado = self._criar_frame_com_titulo(aba, "Visualização do Relatório")
        frame_resultado.pack(side="right", fill="both", expand=True)

        self.txt_relatorio = tk.Text(frame_resultado, wrap='word', height=20, font=("Courier New", 10))
        self.txt_relatorio.pack(fill='both', expand=True)
    
    def _get_id_from_combobox(self, combo_value):
        try:
            return int(combo_value.split(" - ")[0])
        except (ValueError, IndexError):
            return None
        
    def _exibir_alerta_reabastecimento(self, produto: Produto):
        messagebox.showwarning(
            "Alerta de Reabastecimento",
            f"O estoque do produto atingiu o nível mínimo!\n\n"
            f"Produto: {produto.nome}\n"
            f"Estoque Atual: {produto.get_estoque_total()} unidades\n"
            f"Nível Mínimo: {produto.ponto_ressuprimento} unidades\n\n"
            "Recomenda-se criar uma nova Ordem de Compra."
        )

    def movimentar_estoque_gui(self, tipo):
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um produto da lista para movimentar o estoque.")

        produto_id = int(selected_items[0])
        
        try:
            quantidade = int(self.mov_qtd.get())
            if quantidade <= 0:
                raise ValueError
        except ValueError:
            return messagebox.showerror("Erro", "Por favor, insira uma quantidade válida (número inteiro maior que zero).")

        localizacao_str = self.mov_local.get()
        if not localizacao_str:
            return messagebox.showerror("Erro", "Por favor, selecione uma localização.")
        
        localizacao_id = self._get_id_from_combobox(localizacao_str)
        produto_nome = self.gerenciador.produtos[produto_id].nome

        qtd_movimento = quantidade if tipo == "Entrada" else -quantidade
        tipo_movimento_str = "Compra/Entrada" if tipo == "Entrada" else "Venda/Saída"

        if messagebox.askyesno("Confirmar Movimentação", f"Confirma a {tipo.lower()} de {quantidade} unidade(s) de '{produto_nome}'?"):
            try:
                sucesso, produto_para_alertar = self.gerenciador.movimentar_estoque(produto_id, localizacao_id, qtd_movimento, tipo_movimento_str)
                if sucesso:
                    messagebox.showinfo("Sucesso", f"{tipo} registrada com sucesso!")
                    self.atualizar_tudo()
                    self.mov_qtd.delete(0, tk.END)
                    if produto_para_alertar:
                        self._exibir_alerta_reabastecimento(produto_para_alertar)
            except ValueError as e:
                messagebox.showerror("Erro de Estoque", str(e))
            except Exception as e:
                messagebox.showerror("Erro Inesperado", f"Ocorreu um erro: {str(e)}")

    def adicionar_produto_gui(self):
        dados = {k.replace(':', ''): v.get() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        if not all(obrigatorios):
            return messagebox.showerror("Erro", "Campos obrigatórios: Nome, Fornecedor, Preços e Ponto de Ressuprimento.")
        if dados['Qtd. Inicial'] and not dados['Localização Inicial']:
            return messagebox.showerror("Erro", "Se a quantidade inicial for informada, a localização é obrigatória.")

        try:
            fornecedor_id = self._get_id_from_combobox(dados['Fornecedor'])
            if not fornecedor_id:
                raise ValueError("Fornecedor inválido ou não selecionado.")

            preco_compra = float(dados['Preço Compra'].replace(',', '.'))
            preco_venda = float(dados['Preço Venda'].replace(',', '.'))

            novo_produto = self.gerenciador.adicionar_produto(
                nome=dados['Nome'], descricao=dados['Descrição'] or "N/A", categoria=dados['Categoria'] or "Outro",
                fornecedor_id=fornecedor_id,
                codigo_barras=dados['Cód. Barras'] or "N/A", preco_compra=preco_compra,
                preco_venda=preco_venda, ponto_ressuprimento=int(dados['Ponto Ressupr.'])
            )
            if dados['Qtd. Inicial']:
                local_id = self._get_id_from_combobox(dados['Localização Inicial'])
                if not local_id:
                    self.gerenciador.remover_produto(novo_produto.id)
                    raise ValueError("Localização inicial inválida ou não selecionada.")
                
                self.gerenciador.movimentar_estoque(novo_produto.id, local_id,
                                                   int(dados['Qtd. Inicial']), "Compra Inicial")

            messagebox.showinfo("Sucesso", "Produto adicionado!")
            self.limpar_formulario_produtos()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Adicionar", str(e))


    def atualizar_produto_gui(self):
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um produto para atualizar.")
        
        dados = {k.replace(':', ''): v.get() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        if not all(obrigatorios):
            return messagebox.showerror("Erro", "Campos obrigatórios não podem ficar vazios na atualização.")

        try:
            fornecedor_id = self._get_id_from_combobox(dados['Fornecedor'])
            if not fornecedor_id:
                raise ValueError("Fornecedor inválido ou não selecionado.")
            
            preco_compra = float(dados['Preço Compra'].replace(',', '.'))
            preco_venda = float(dados['Preço Venda'].replace(',', '.'))

            dados_atualizados = {
                'nome': dados['Nome'], 'descricao': dados['Descrição'] or "N/A",
                'categoria': dados['Categoria'], 'codigo_barras': dados['Cód. Barras'] or "N/A",
                'preco_compra': preco_compra, 'preco_venda': preco_venda,
                'ponto_ressuprimento': int(dados['Ponto Ressupr.']),
                'fornecedor': str(fornecedor_id) 
            }
            self.gerenciador.atualizar_produto(int(selected_items[0]), **dados_atualizados)
            messagebox.showinfo("Sucesso", "Produto atualizado!")
            self.limpar_formulario_produtos()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Atualizar", str(e))


    def remover_produto_gui(self):
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um produto para remover.")
        
        produto_id = int(selected_items[0])
        produto_nome = self.gerenciador.produtos[produto_id].nome
        if messagebox.askyesno("Confirmar Remoção", f"Tem certeza que deseja remover o produto '{produto_nome}'? Esta ação não pode ser desfeita e removerá todo o histórico associado."):
            if self.gerenciador.remover_produto(produto_id):
                messagebox.showinfo("Sucesso", "Produto removido!")
                self.limpar_formulario_produtos()
                self.atualizar_tudo()
            else:
                 messagebox.showerror("Erro", "Não foi possível remover o produto.")

    def carregar_produto_para_formulario(self, event=None):
        if not (selected_items := self.tree_produtos.selection()): return
        
        produto = self.gerenciador.produtos.get(int(selected_items[0]))
        if not produto: return

        for widget in self.entries_prod.values():
            widget.config(state='normal') 
            if isinstance(widget, ttk.Combobox):
                widget.set('')
            else:
                widget.delete(0, tk.END)

        self.entries_prod["Nome:"].insert(0, produto.nome)
        self.entries_prod["Descrição:"].insert(0, produto.descricao)
        self.entries_prod["Categoria:"].set(produto.categoria)
        self.entries_prod["Cód. Barras:"].insert(0, produto.codigo_barras)

        self.entries_prod["Preço Compra:"].insert(0, str(produto.preco_compra).replace('.', ','))
        self.entries_prod["Preço Venda:"].insert(0, str(produto.preco_venda).replace('.', ','))   
        self.entries_prod["Ponto Ressupr.:"].insert(0, str(produto.ponto_ressuprimento))
        self.entries_prod["Fornecedor:"].set(str(produto.fornecedor))
        
        self.entries_prod["Qtd. Inicial:"].config(state='disabled')
        self.entries_prod["Localização Inicial:"].config(state='disabled')

        self.entries_prod["Fornecedor:"].config(state='readonly')
        self.entries_prod["Categoria:"].config(state='readonly')

    def limpar_formulario_produtos(self):
        if self.tree_produtos.selection():
            self.tree_produtos.selection_remove(self.tree_produtos.selection())
            
        for widget in self.entries_prod.values():
            if isinstance(widget, ttk.Combobox):
                widget.set('')
                widget.config(state='readonly')
            else:
                widget.config(state='normal')
                widget.delete(0, tk.END)
        self.entries_prod["Categoria:"].set("Eletrônicos")
        self.mov_qtd.delete(0, tk.END)
        self.mov_local.set('')

    def _atualizar_combo_produtos_oc(self, *args):
        self.oc_combo_produto.set('')
        fornecedor_id = self._get_id_from_combobox(self.oc_fornecedor_var.get())
        if not fornecedor_id:
            self.oc_combo_produto['values'] = []
            return
        
        produtos_fornecedor = [
            f"{p.id} - {p.nome}" for p in self.gerenciador.produtos.values()
            if p.fornecedor.id == fornecedor_id
        ]
        self.oc_combo_produto['values'] = produtos_fornecedor

    def _adicionar_item_oc_lista(self):
        try:
            produto_id = self._get_id_from_combobox(self.oc_combo_produto.get())
            if not produto_id:
                raise ValueError("Selecione um produto.")
            
            quantidade = int(self.oc_entry_quantidade.get())
            if quantidade <= 0:
                raise ValueError("A quantidade deve ser maior que zero.")
            
            produto = self.gerenciador.produtos[produto_id]

            for item in self.itens_oc_atual:
                if item['produto_id'] == produto_id:
                    item['quantidade'] += quantidade
                    item['subtotal'] = item['quantidade'] * item['preco_unitario']
                    self._atualizar_tree_itens_nova_oc()
                    return

            self.itens_oc_atual.append({
                "produto_id": produto.id,
                "nome": produto.nome,
                "quantidade": quantidade,
                "preco_unitario": produto.preco_compra,
                "subtotal": quantidade * produto.preco_compra
            })
            self._atualizar_tree_itens_nova_oc()
            self.oc_combo_produto.set('')
            self.oc_entry_quantidade.delete(0, 'end')

        except Exception as e:
            messagebox.showerror("Erro", str(e))

    def _remover_item_oc_lista(self):
        if not (selected_tree_items := self.tree_itens_nova_oc.selection()):
            return messagebox.showwarning("Aviso", "Selecione um item da lista para remover.")
        
        item_id = int(selected_tree_items[0])
        self.itens_oc_atual = [item for item in self.itens_oc_atual if item['produto_id'] != item_id]
        self._atualizar_tree_itens_nova_oc()

    def _salvar_oc(self):
        if not self.itens_oc_atual:
            return messagebox.showerror("Erro", "Adicione pelo menos um item à ordem de compra.")
        
        fornecedor_id = self._get_id_from_combobox(self.oc_fornecedor_var.get())
        if not fornecedor_id:
            return messagebox.showerror("Erro", "Selecione um fornecedor.")

        try:
            self.gerenciador.criar_ordem_compra(fornecedor_id, self.itens_oc_atual)
            messagebox.showinfo("Sucesso", "Ordem de Compra criada com sucesso!")
            self._limpar_form_oc()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", str(e))

    def _limpar_form_oc(self):
        self.oc_fornecedor_var.set('')
        self.oc_combo_produto.set('')
        self.oc_combo_produto['values'] = []
        self.oc_entry_quantidade.delete(0, tk.END)
        self.itens_oc_atual.clear()
        self._atualizar_tree_itens_nova_oc()

    def _marcar_oc_recebida(self):
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        ordem = self.gerenciador.ordens_compra.get(ordem_id)

        if ordem.status == "Recebida":
            return messagebox.showinfo("Informação", "Esta ordem já foi recebida.")

        localizacoes = list(self.gerenciador.localizacoes.values())
        if not localizacoes:
            return messagebox.showerror("Erro", "Nenhuma localização de estoque cadastrada. Cadastre uma localização primeiro.")
        
        local_selecionada = simpledialog.askstring("Selecionar Localização", 
            "Em qual localização o estoque será recebido?\n\nDigite o ID da localização desejada:\n" + "\n".join([str(l) for l in localizacoes]),
            parent=self.root)
        
        if not local_selecionada: return
        
        try:
            local_id = int(local_selecionada) 
            if not local_id or local_id not in self.gerenciador.localizacoes:
                raise ValueError("ID de localização inválido.")

            self.gerenciador.atualizar_status_ordem(ordem_id, "Recebida", localizacao_id=local_id)
            messagebox.showinfo("Sucesso", f"Ordem de Compra #{ordem_id} marcada como recebida!\nEstoque atualizado.")
            self.atualizar_tudo()

        except ValueError:
             messagebox.showerror("Erro", "Por favor, insira um ID de localização válido (apenas números).")
        except Exception as e:
            messagebox.showerror("Erro", str(e))
    
    def _atualizar_status_oc_gui(self, novo_status: str):
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        
        try:
            self.gerenciador.atualizar_status_ordem(ordem_id, novo_status)
            messagebox.showinfo("Sucesso", f"Status da Ordem de Compra #{ordem_id} atualizado para '{novo_status}'.")
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro", str(e))
    
    def _visualizar_oc(self):
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        ordem = self.gerenciador.ordens_compra.get(ordem_id)
        if not ordem: return

        top = tk.Toplevel(self.root)
        top.title(f"Recibo da Ordem de Compra #{ordem.id}")
        top.geometry("650x500")
        top.transient(self.root)
        top.grab_set()

        frame_visualizacao = ttk.Frame(top)
        frame_visualizacao.pack(fill=tk.BOTH, expand=True)

        frame_texto = ttk.Frame(frame_visualizacao, padding=10)
        frame_texto.pack(fill=tk.X)

        texto_cabecalho = f"""ORDEM DE COMPRA (PURCHASE ORDER)
Número: {ordem.id} | Data: {ordem.data_criacao.strftime('%d/%m/%Y %H:%M:%S')} | Status: {ordem.status}

PARA:
{ordem.fornecedor.nome} (ID: {ordem.fornecedor.id})
Contato: {ordem.fornecedor.contato} | Email: {ordem.fornecedor.email}
"""
        lbl_cabecalho = ttk.Label(frame_texto, text=texto_cabecalho, justify=tk.LEFT, font=("Courier New", 10))
        lbl_cabecalho.pack(anchor='w')

        frame_itens = self._criar_frame_com_titulo(frame_visualizacao, "Itens do Pedido")
        frame_itens.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        itens_tree = ttk.Treeview(frame_itens, columns=("ID", "Produto", "Qtd", "Preço Un.", "Subtotal"), show="headings")
        itens_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(frame_itens, orient="vertical", command=itens_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        itens_tree.configure(yscrollcommand=scrollbar.set)
        
        col_widths_oc = {"ID": 40, "Qtd": 50, "Preço Un.": 100, "Subtotal": 100, "Produto": 200}
        for col, width in col_widths_oc.items(): 
            itens_tree.heading(col, text=col)
            itens_tree.column(col, width=width, anchor='w')

        for item in ordem.itens:
            itens_tree.insert("", "end", values=(
                item.produto.id, item.produto.nome, item.quantidade, f"R$ {item.preco_unitario:.2f}", f"R$ {item.subtotal:.2f}"
            ))

        total_text = f"VALOR TOTAL DO PEDIDO: R$ {ordem.valor_total:.2f}"
        lbl_total = ttk.Label(frame_visualizacao, text=total_text, font=("Helvetica", 12, "bold"), padding=(0,5,10,10))
        lbl_total.pack(anchor='e')

        frame_botoes_salvar = ttk.Frame(top, padding=10)
        frame_botoes_salvar.pack(fill=tk.X)
        
        btn_pdf = ttk.Button(frame_botoes_salvar, text="Salvar como PDF", command=lambda: self._salvar_oc_pdf(ordem))
        btn_pdf.pack(side=tk.RIGHT, padx=5)
        if not REPORTLAB_DISPONIVEL:
            btn_pdf.config(state="disabled")

        ttk.Button(frame_botoes_salvar, text="Salvar como TXT", command=lambda: self._salvar_oc_txt(ordem)).pack(side=tk.RIGHT)

    def _gerar_texto_recibo(self, ordem: OrdemCompra) -> str:
        linhas = [
            "==========================================",
            "        ORDEM DE COMPRA (RECIBO)        ",
            "==========================================",
            f"Número do Pedido: {ordem.id}",
            f"Data de Emissão: {ordem.data_criacao.strftime('%d/%m/%Y %H:%M:%S')}",
            f"Status: {ordem.status}",
            "\n--- DADOS DO FORNECEDOR ---",
            f"Nome: {ordem.fornecedor.nome}",
            f"Contato: {ordem.fornecedor.contato}",
            f"Email: {ordem.fornecedor.email}",
            "\n--- ITENS DO PEDIDO ---"
        ]
        
        header = f'{"ID":<5}{"Produto":<30}{"Qtd":>5} {"Preço Un.":>12} {"Subtotal":>15}'
        linhas.append(header)
        linhas.append("-" * len(header))

        for item in ordem.itens:
            linha_item = (f"{item.produto.id:<5}"
                          f"{item.produto.nome[:29]:<30}"
                          f"{item.quantidade:>5} "
                          f"{f'R$ {item.preco_unitario:.2f}':>12}"
                          f"{f'R$ {item.subtotal:.2f}':>15}")
            linhas.append(linha_item)
        
        linhas.append("-" * len(header))
        linhas.append(f"{'VALOR TOTAL:':>53} {f'R$ {ordem.valor_total:.2f}':>15}")
        
        return "\n".join(linhas)
        
    def _salvar_oc_txt(self, ordem: OrdemCompra):
        texto_recibo = self._gerar_texto_recibo(ordem)
        filepath = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title="Salvar Recibo como TXT",
            initialfile=f"Ordem_de_Compra_{ordem.id}.txt"
        )
        if not filepath:
            return
            
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(texto_recibo)
            messagebox.showinfo("Sucesso", f"Recibo salvo com sucesso em:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo.\nErro: {e}")

    def _salvar_oc_pdf(self, ordem: OrdemCompra):
        if not REPORTLAB_DISPONIVEL:
            messagebox.showerror(
                "Biblioteca Faltando",
                "A biblioteca 'reportlab' é necessária para gerar PDFs.\n\n"
                "Por favor, instale-a executando o comando no seu terminal:\n"
                "pip install reportlab"
            )
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            title="Salvar Recibo como PDF",
            initialfile=f"Ordem_de_Compra_{ordem.id}.pdf"
        )
        if not filepath:
            return

        try:
            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter
            
            y = height - inch
            c.setFont("Helvetica-Bold", 16)
            c.drawString(inch, y, f"ORDEM DE COMPRA #{ordem.id}")
            y -= 0.5 * inch
            
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, f"Data de Emissão: {ordem.data_criacao.strftime('%d/%m/%Y')}")
            c.drawString(width - 2.5*inch, y, f"Status: {ordem.status}")
            y -= 0.3 * inch

            c.line(inch, y, width - inch, y)
            y -= 0.3 * inch
            
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y, "Dados do Fornecedor:")
            y -= 0.2 * inch
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, f"Nome: {ordem.fornecedor.nome}")
            y -= 0.2 * inch
            c.drawString(inch, y, f"Contato: {ordem.fornecedor.contato} | Email: {ordem.fornecedor.email}")
            y -= 0.4 * inch
            
            c.line(inch, y, width - inch, y)
            y -= 0.3 * inch
            
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y, "Itens do Pedido:")
            y -= 0.25 * inch

            c.setFont("Helvetica-Bold", 10)
            c.drawString(inch, y, "ID")
            c.drawString(inch + 0.5*inch, y, "Produto")
            c.drawString(width - 3.5*inch, y, "Qtd.")
            c.drawString(width - 2.8*inch, y, "Preço Un.")
            c.drawString(width - 1.5*inch, y, "Subtotal")
            y -= 0.2 * inch

            c.setFont("Helvetica", 10)
            for item in ordem.itens:
                c.drawString(inch, y, str(item.produto.id))
                c.drawString(inch + 0.5*inch, y, item.produto.nome)
                c.drawString(width - 3.5*inch, y, str(item.quantidade))
                c.drawString(width - 2.8*inch, y, f"R$ {item.preco_unitario:.2f}")
                c.drawString(width - 1.5*inch, y, f"R$ {item.subtotal:.2f}")
                y -= 0.2 * inch
                if y < inch: 
                    c.showPage()
                    y = height - inch
                    c.setFont("Helvetica", 10)

            y -= 0.2 * inch
            c.line(inch, y, width - inch, y)
            y -= 0.3 * inch

            c.setFont("Helvetica-Bold", 12)
            c.drawString(width - 3*inch, y, f"VALOR TOTAL: R$ {ordem.valor_total:.2f}")

            c.save()
            messagebox.showinfo("Sucesso", f"Recibo PDF salvo com sucesso em:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erro ao Salvar PDF", f"Não foi possível salvar o arquivo PDF.\nErro: {e}")

    def _atualizar_tree_itens_nova_oc(self):
        for i in self.tree_itens_nova_oc.get_children():
            self.tree_itens_nova_oc.delete(i)
        for item in self.itens_oc_atual:
            self.tree_itens_nova_oc.insert("", "end", iid=item['produto_id'], values=(
                item['produto_id'], item['nome'], item['quantidade'],
                f"{item['preco_unitario']:.2f}", f"{item['subtotal']:.2f}"
            ))

    def _atualizar_filtros_relatorio(self, event=None):
        tipo_selecionado = self.relatorio_combo_tipo.get()

        self.relatorio_lbl_produto.grid_remove()
        self.relatorio_combo_produto.grid_remove()
        self.relatorio_lbl_data_inicio.grid_remove()
        self.relatorio_entry_data_inicio.grid_remove()
        self.relatorio_lbl_data_fim.grid_remove()
        self.relatorio_entry_data_fim.grid_remove()

        if tipo_selecionado == "Histórico de Movimentação por Item":
            self.relatorio_lbl_produto.grid(row=0, column=0, sticky='w', padx=5)
            self.relatorio_combo_produto.grid(row=1, column=0, sticky='ew', padx=5)
        elif tipo_selecionado == "Relatório de Vendas por Período":
            self.relatorio_lbl_data_inicio.grid(row=0, column=0, sticky='w', padx=5)
            self.relatorio_entry_data_inicio.grid(row=1, column=0, sticky='ew', padx=5)
            self.relatorio_lbl_data_fim.grid(row=2, column=0, sticky='w', padx=5, pady=(5,0))
            self.relatorio_entry_data_fim.grid(row=3, column=0, sticky='ew', padx=5)

    def _gerar_relatorio_detalhado_gui(self):
        tipo_relatorio = self.relatorio_combo_tipo.get()
        if not tipo_relatorio:
            messagebox.showerror("Erro", "Por favor, selecione um tipo de relatório.")
            return

        report_text = ""
        try:
            if tipo_relatorio == "Inventário Completo (Simplificado)":
                report_text = self.gerenciador.gerar_relatorio_estoque_simplificado()
            elif tipo_relatorio == "Valor Total do Inventário":
                report_text = self.gerenciador.gerar_relatorio_valor_total()
            elif tipo_relatorio == "Produtos com Baixo Estoque":
                report_text = self.gerenciador.gerar_relatorio_baixo_estoque()
            elif tipo_relatorio == "Produtos Mais Vendidos":
                report_text = self.gerenciador.gerar_relatorio_mais_vendidos()
            elif tipo_relatorio == "Histórico de Movimentação por Item":
                produto_id = self._get_id_from_combobox(self.relatorio_combo_produto.get())
                if not produto_id:
                    raise ValueError("Selecione um produto para gerar o histórico.")
                report_text = self.gerenciador.gerar_relatorio_movimentacao_item(produto_id)
            elif tipo_relatorio == "Relatório de Vendas por Período":
                str_inicio = self.relatorio_entry_data_inicio.get()
                str_fim = self.relatorio_entry_data_fim.get()
                if not str_inicio or not str_fim:
                    raise ValueError("As datas de início e fim são obrigatórias.")
                
                data_inicio = datetime.strptime(str_inicio, "%d/%m/%Y")
                data_fim = datetime.combine(datetime.strptime(str_fim, "%d/%m/%Y"), time.max)
                report_text = self.gerenciador.gerar_relatorio_vendas_periodo(data_inicio, data_fim)

        except ValueError as e:
            messagebox.showerror("Erro de Filtro", str(e))
            return
        except Exception as e:
            messagebox.showerror("Erro Inesperado", f"Ocorreu um erro ao gerar o relatório: {e}")
            return
            
        self.txt_relatorio.delete('1.0', tk.END)
        self.txt_relatorio.insert(tk.END, report_text)

    def atualizar_dashboard(self):
        self.lbl_valor_estoque.config(text=f"Valor Total do Estoque: R$ {self.gerenciador.calcular_valor_total_estoque():,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.'))
        self.lbl_itens_unicos.config(text=f"Itens Únicos: {len(self.gerenciador.produtos)}")
        
        for i in self.tree_alertas.get_children():
            self.tree_alertas.delete(i)
        for p in self.gerenciador.verificar_alertas_ressuprimento():
            self.tree_alertas.insert("", "end", values=(p.id, p.nome, p.get_estoque_total(), p.ponto_ressuprimento))

    def atualizar_tabela_produtos(self):
        for i in self.tree_produtos.get_children():
            self.tree_produtos.delete(i)
        for p in sorted(self.gerenciador.produtos.values(), key=lambda x: x.id):
            preco_venda_formatado = f"{p.preco_venda:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            self.tree_produtos.insert("", "end", iid=p.id, values=(
                p.id, p.nome, p.categoria, p.fornecedor.nome,
                p.get_estoque_total(), preco_venda_formatado
            ))

    def atualizar_combos(self):
        fornecedores_str = [str(f) for f in self.gerenciador.fornecedores.values()]
        localizacoes_str = [str(l) for l in self.gerenciador.localizacoes.values()]
        produtos_str = [f"{p.id} - {p.nome}" for p in self.gerenciador.produtos.values()]

        self.entries_prod["Fornecedor:"]['values'] = fornecedores_str
        self.entries_prod["Localização Inicial:"]['values'] = localizacoes_str
        self.mov_local['values'] = localizacoes_str
        self.oc_combo_fornecedor['values'] = fornecedores_str
        self.relatorio_combo_produto['values'] = produtos_str

    def atualizar_lista_ocs(self):
        for i in self.tree_lista_ocs.get_children():
            self.tree_lista_ocs.delete(i)
        for oc in sorted(self.gerenciador.ordens_compra.values(), key=lambda x: x.id, reverse=True):
            valor_total_formatado = f"R$ {oc.valor_total:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')
            self.tree_lista_ocs.insert("", "end", values=(
                oc.id, oc.fornecedor.nome, oc.data_criacao.strftime("%d/%m/%Y"),
                valor_total_formatado, oc.status
            ))

    def atualizar_tudo(self):
        selecao_atual_prod = self.tree_produtos.selection()
        selecao_atual_oc = self.tree_lista_ocs.selection()

        self.atualizar_dashboard()
        self.atualizar_tabela_produtos()
        self.atualizar_combos()
        self.atualizar_lista_ocs()
        
        if selecao_atual_prod:
            try:
                self.tree_produtos.selection_set(selecao_atual_prod)
            except tk.TclError: 
                pass
        if selecao_atual_oc:
            try:
                self.tree_lista_ocs.selection_set(selecao_atual_oc)
            except tk.TclError:
                pass


if __name__ == "__main__":
    db_existe = os.path.exists(DB_FILE)
    
    db = DatabaseManager(DB_FILE)
    db.connect()
    
    db.create_tables()

    gerenciador = GerenciadorEstoque(db)
    
    if not db_existe:
        print("Banco de dados não encontrado. Populando com dados iniciais...")
        deposito = gerenciador.adicionar_localizacao(nome="Depósito Central")
        loja_a = gerenciador.adicionar_localizacao(nome="Loja A - Shopping")

        asus = gerenciador.adicionar_fornecedor(nome="ASUS Brasil", contato="Carlos", email="contato@asus.br")
        logitech = gerenciador.adicionar_fornecedor(nome="Logitech BR", contato="Ana", email="vendas@logitech.com")
        dell = gerenciador.adicionar_fornecedor(nome="Dell Brasil", contato="Maria", email="comercial@dell.com")

        p1 = gerenciador.adicionar_produto(nome="Notebook ROG Strix", descricao="Notebook Gamer 16GB RAM, RTX 4060", categoria="Eletrônicos", fornecedor_id=asus.id, codigo_barras="789123456001", preco_compra=5000, preco_venda=7500, ponto_ressuprimento=10)
        p2 = gerenciador.adicionar_produto(nome="Mouse G502 Hero", descricao="Mouse Gamer com RGB e 25k DPI", categoria="Periféricos", fornecedor_id=logitech.id, codigo_barras="789789789002", preco_compra=250, preco_venda=450, ponto_ressuprimento=20)
        p3 = gerenciador.adicionar_produto(nome="Monitor Alienware 27''", descricao="Monitor Gamer 240Hz, QHD, Fast IPS", categoria="Eletrônicos", fornecedor_id=dell.id, codigo_barras="789456123003", preco_compra=2200, preco_venda=3800, ponto_ressuprimento=5)
        p4 = gerenciador.adicionar_produto(nome="Teclado Mecânico G PRO", descricao="Teclado TKL com switches GX Blue", categoria="Periféricos", fornecedor_id=logitech.id, codigo_barras="789789789005", preco_compra=450, preco_venda=700, ponto_ressuprimento=15)

        gerenciador.movimentar_estoque(p1.id, deposito.id, 15, "Compra")
        gerenciador.movimentar_estoque(p2.id, deposito.id, 50, "Compra")
        gerenciador.movimentar_estoque(p3.id, deposito.id, 8, "Compra")
        gerenciador.movimentar_estoque(p1.id, loja_a.id, 5, "Transferência")
        gerenciador.movimentar_estoque(p1.id, deposito.id, -2, "Venda")
        print("Dados iniciais populados.")

    gerenciador.carregar_dados_do_banco()

    root = tk.Tk()
    
    def on_closing():
        print("Fechando conexão com o banco de dados...")
        db.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing) 
    
    app = App(root, gerenciador)
    root.mainloop()