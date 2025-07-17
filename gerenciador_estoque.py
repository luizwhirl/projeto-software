import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
from collections import defaultdict
from dataclasses import dataclass, field

# 1: classes de modelo (elas representam os dados do sistema)

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

# 2: classe controladora (é aqui que está a lógica do programaaaaa)

class GerenciadorEstoque:
    def __init__(self):
        self.produtos: dict[int, Produto] = {}
        self.fornecedores: dict[int, Fornecedor] = {}
        self.localizacoes: dict[int, Localizacao] = {}
        self.historico: list[HistoricoMovimento] = []
        self._proximo_id_produto = 1
        self._proximo_id_fornecedor = 1
        self._proximo_id_localizacao = 1

    def _adicionar_item(self, item_dict, item_class, proximo_id_attr, **kwargs):
        """função genérica para adicionar itens (produto, fornecedor, localização)."""
        novo_id = getattr(self, proximo_id_attr)
        item = item_class(id=novo_id, **kwargs)
        item_dict[novo_id] = item
        setattr(self, proximo_id_attr, novo_id + 1)
        return item

    def adicionar_produto(self, fornecedor_id, **kwargs):
        if not (fornecedor := self.fornecedores.get(fornecedor_id)):
            raise ValueError("Fornecedor não encontrado.")
        return self._adicionar_item(self.produtos, Produto, '_proximo_id_produto', fornecedor=fornecedor, **kwargs)

    def adicionar_fornecedor(self, **kwargs):
        return self._adicionar_item(self.fornecedores, Fornecedor, '_proximo_id_fornecedor', **kwargs)

    def adicionar_localizacao(self, **kwargs):
        return self._adicionar_item(self.localizacoes, Localizacao, '_proximo_id_localizacao', **kwargs)

    def atualizar_produto(self, produto_id, **kwargs):
        if produto_id not in self.produtos:
            return False
        produto = self.produtos[produto_id]
        for key, value in kwargs.items():
            if hasattr(produto, key):
                if key == 'fornecedor':
                    value = self.fornecedores.get(int(value))
                    if not value: continue
                setattr(produto, key, value)
        return True

    def remover_produto(self, produto_id):
        if produto_id in self.produtos:
            del self.produtos[produto_id]
            return True
        return False

    def movimentar_estoque(self, produto_id, localizacao_id, quantidade, tipo_movimento):
        produto = self.produtos.get(produto_id)
        localizacao = self.localizacoes.get(localizacao_id)
        if not all([produto, localizacao]):
            raise ValueError("Produto ou Localização inválido.")

        quantidade = int(quantidade)
        if quantidade < 0 and produto.estoque_por_local[localizacao.nome] < abs(quantidade):
            raise ValueError(f"Estoque insuficiente em {localizacao.nome}")

        produto.estoque_por_local[localizacao.nome] += quantidade
        self.historico.append(HistoricoMovimento(produto, tipo_movimento, quantidade, localizacao))
        return True

    def verificar_alertas_ressuprimento(self):
        return [p for p in self.produtos.values() if p.get_estoque_total() <= p.ponto_ressuprimento]

    def calcular_valor_total_estoque(self):
        return sum(p.get_estoque_total() * p.preco_compra for p in self.produtos.values())

    def gerar_relatorio_estoque(self):
        report = f"""RELATÓRIO DE ESTOQUE
Data de Geração: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}
Valor Total do Estoque: R$ {self.calcular_valor_total_estoque():.2f}
{'='*50}\n\n"""
        for produto in self.produtos.values():
            estoque_locais = "\n".join([f"     - {local}: {qtd} unidades" for local, qtd in produto.estoque_por_local.items()])
            if not estoque_locais:
                estoque_locais = "     - Sem estoque registrado"

            report += f"""ID: {produto.id} - {produto.nome} ({produto.categoria})
   Estoque Total: {produto.get_estoque_total()} unidades
   Ponto de Ressuprimento: {produto.ponto_ressuprimento}
   Estoque por Local:
{estoque_locais}
{'-'*20}\n"""
        return report

# classe da visão, com interface otimizada

class App:
    def __init__(self, root: tk.Tk, gerenciador: GerenciadorEstoque):
        self.root = root
        self.gerenciador = gerenciador
        self.root.title("Software de Gerenciamento de Estoque")
        self.root.geometry("1280x780")

        self.vcmd_int = (self.root.register(lambda v: v.isdigit() or v == ""), '%P')
        self.vcmd_float = (self.root.register(self.validar_float), '%P')

        style = ttk.Style()
        style.theme_use('clam')
        style.map("Treeview", background=[('selected', '#B0E2FF')], foreground=[('selected', 'black')])

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        self.criar_aba_dashboard()
        self.criar_aba_produtos()
        self.criar_aba_fornecedores()
        self.criar_aba_relatorios()

        self.atualizar_tudo()

    def validar_float(self, val):
        if val == "": return True
        try:
            float(val)
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

        frame_alertas = self._criar_frame_com_titulo(aba, "Alertas de Baixo Estoque")
        frame_alertas.pack(fill='both', expand=True, pady=10)
        self.tree_alertas = ttk.Treeview(frame_alertas, columns=("ID", "Nome", "Estoque Atual", "Mínimo"), show="headings")
        for col in self.tree_alertas['columns']:
            self.tree_alertas.heading(col, text=col)
        self.tree_alertas.pack(fill='both', expand=True)

    def criar_aba_produtos(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Produtos')

        form_container = ttk.Frame(aba)
        form_container.pack(side="left", fill="y", padx=(0, 10))
        form_frame = self._criar_frame_com_titulo(form_container, "Gerenciar Produto")
        form_frame.pack(fill="both", expand=True)

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

    def criar_aba_relatorios(self):
        aba = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(aba, text='Relatórios')
        ttk.Button(aba, text="Gerar Relatório Completo de Estoque", command=self.gerar_relatorio_gui).pack(pady=10)
        self.txt_relatorio = tk.Text(aba, wrap='word', height=20, font=("Courier New", 10))
        self.txt_relatorio.pack(fill='both', expand=True)

    def _get_id_from_combobox(self, combo_value):
        return int(combo_value.split(" - ")[0])

    def adicionar_produto_gui(self):
        dados = {k.replace(':', ''): v.get() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        if not all(obrigatorios):
            return messagebox.showerror("Erro", "Campos obrigatórios: Nome, Fornecedor, Preços e Ponto de Ressuprimento.")
        if dados['Qtd. Inicial'] and not dados['Localização Inicial']:
            return messagebox.showerror("Erro", "Se a quantidade inicial for informada, a localização é obrigatória.")

        try:
            novo_produto = self.gerenciador.adicionar_produto(
                nome=dados['Nome'], descricao=dados['Descrição'] or "N/A", categoria=dados['Categoria'] or "Outro",
                fornecedor_id=self._get_id_from_combobox(dados['Fornecedor']),
                codigo_barras=dados['Cód. Barras'] or "N/A", preco_compra=float(dados['Preço Compra']),
                preco_venda=float(dados['Preço Venda']), ponto_ressuprimento=int(dados['Ponto Ressupr.'])
            )
            if dados['Qtd. Inicial']:
                self.gerenciador.movimentar_estoque(novo_produto.id, self._get_id_from_combobox(dados['Localização Inicial']),
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
            dados_atualizados = {
                'nome': dados['Nome'], 'descricao': dados['Descrição'] or "N/A",
                'categoria': dados['Categoria'], 'codigo_barras': dados['Cód. Barras'] or "N/A",
                'preco_compra': float(dados['Preço Compra']), 'preco_venda': float(dados['Preço Venda']),
                'ponto_ressuprimento': int(dados['Ponto Ressupr.']),
                'fornecedor': self._get_id_from_combobox(dados['Fornecedor'])
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
        if messagebox.askyesno("Confirmar Remoção", f"Tem certeza que deseja remover o produto '{produto_nome}'?"):
            self.gerenciador.remover_produto(produto_id)
            messagebox.showinfo("Sucesso", "Produto removido!")
            self.limpar_formulario_produtos()
            self.atualizar_tudo()


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
        self.entries_prod["Preço Compra:"].insert(0, str(produto.preco_compra))
        self.entries_prod["Preço Venda:"].insert(0, str(produto.preco_venda))   
        self.entries_prod["Ponto Ressupr.:"].insert(0, str(produto.ponto_ressuprimento))
        self.entries_prod["Fornecedor:"].set(str(produto.fornecedor))
        
        self.entries_prod["Qtd. Inicial:"].config(state='disabled')
        self.entries_prod["Localização Inicial:"].config(state='disabled')
        self.entries_prod["Fornecedor:"].config(state='readonly')
        self.entries_prod["Categoria:"].config(state='readonly')

    def limpar_formulario_produtos(self):
        self.tree_produtos.selection_remove(self.tree_produtos.selection())
        for widget in self.entries_prod.values():
            if isinstance(widget, ttk.Combobox):
                widget.set('')
                widget.config(state='readonly')
            else:
                widget.config(state='normal')
                widget.delete(0, tk.END)
        self.entries_prod["Categoria:"].set("Eletrônicos")

    def atualizar_dashboard(self):
        self.lbl_valor_estoque.config(text=f"Valor Total do Estoque: R$ {self.gerenciador.calcular_valor_total_estoque():.2f}")
        self.lbl_itens_unicos.config(text=f"Itens Únicos: {len(self.gerenciador.produtos)}")
        
        self.tree_alertas.delete(*self.tree_alertas.get_children())
        for p in self.gerenciador.verificar_alertas_ressuprimento():
            self.tree_alertas.insert("", "end", values=(p.id, p.nome, p.get_estoque_total(), p.ponto_ressuprimento))

    def atualizar_tabela_produtos(self):
        self.entries_prod["Fornecedor:"]['values'] = [str(f) for f in self.gerenciador.fornecedores.values()]
        self.entries_prod["Localização Inicial:"]['values'] = [str(l) for l in self.gerenciador.localizacoes.values()]
        
        self.tree_produtos.delete(*self.tree_produtos.get_children())
        for p in self.gerenciador.produtos.values():
            self.tree_produtos.insert("", "end", iid=p.id, values=(
                p.id, p.nome, p.categoria, p.fornecedor.nome,
                p.get_estoque_total(), f"{p.preco_venda:.2f}"
            ))

    def gerar_relatorio_gui(self):
        self.txt_relatorio.delete('1.0', tk.END)
        self.txt_relatorio.insert(tk.END, self.gerenciador.gerar_relatorio_estoque())

    def atualizar_tudo(self):
        self.atualizar_dashboard()
        self.atualizar_tabela_produtos()

# 4- ponto de entrada do programa
if __name__ == "__main__":
    gerenciador = GerenciadorEstoque()

    # so alguns dados de exemplo aqui
    deposito = gerenciador.adicionar_localizacao(nome="Depósito Central")
    loja_a = gerenciador.adicionar_localizacao(nome="Loja A - Shopping")

    asus = gerenciador.adicionar_fornecedor(nome="ASUS Brasil", contato="Carlos", email="contato@asus.br")
    logitech = gerenciador.adicionar_fornecedor(nome="Logitech BR", contato="Ana", email="vendas@logitech.com")
    dell = gerenciador.adicionar_fornecedor(nome="Dell Brasil", contato="Maria", email="comercial@dell.com")

    p1 = gerenciador.adicionar_produto(nome="Notebook ROG Strix", descricao="Notebook Gamer 16GB RAM, RTX 4060", categoria="Eletrônicos", fornecedor_id=asus.id, codigo_barras="789123456001", preco_compra=5000, preco_venda=7500, ponto_ressuprimento=10)
    p2 = gerenciador.adicionar_produto(nome="Mouse G502 Hero", descricao="Mouse Gamer com RGB e 25k DPI", categoria="Periféricos", fornecedor_id=logitech.id, codigo_barras="789789789002", preco_compra=250, preco_venda=450, ponto_ressuprimento=20)
    p3 = gerenciador.adicionar_produto(nome="Monitor Alienware 27''", descricao="Monitor Gamer 240Hz, QHD, Fast IPS", categoria="Eletrônicos", fornecedor_id=dell.id, codigo_barras="789456123003", preco_compra=2200, preco_venda=3800, ponto_ressuprimento=5)

    gerenciador.movimentar_estoque(p1.id, deposito.id, 15, "Compra")
    gerenciador.movimentar_estoque(p2.id, deposito.id, 50, "Compra")
    gerenciador.movimentar_estoque(p3.id, deposito.id, 8, "Compra") # gerar alerta
    gerenciador.movimentar_estoque(p1.id, loja_a.id, 5, "Transferência")
    
    root = tk.Tk()
    app = App(root, gerenciador)
    root.mainloop()