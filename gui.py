# gui.py
# Contém a classe App, responsável por toda a construção e gerenciamento 
# da interface gráfica (GUI) com Tkinter.

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog
from datetime import datetime, time

from manager import GerenciadorEstoque
from models import Produto, OrdemCompra
from config import REPORTLAB_DISPONIVEL

class App:
    """ gerencia toda a interface gráfica  usando Tkinter 💔"""
    def __init__(self, root: tk.Tk, gerenciador: GerenciadorEstoque):
        self.root = root
        self.gerenciador = gerenciador
        self.root.title("Gerenciamento de Estoque")
        self.root.geometry("1360x820")

        # pai e mãe 
        # ouro de mina
        # coração
        # desejo e sina

        # comandos de validação para campos de entrada 
        self.vcmd_int = (self.root.register(lambda v: v.isdigit() or v == ""), '%P')
        self.vcmd_float = (self.root.register(self.validar_float), '%P')
        
        # liista temporária para armazenar os itens de uma nova ordem de compra
        self.itens_oc_atual = []
        
        # --- Lógica do Leitor de Código de Barras ---
        self.barcode_buffer = ""
        self.barcode_timer = None
        # Associa o evento de pressionar tecla a um método para toda a janela
        self.root.bind('<Key>', self.lidar_com_keypress_barcode)
        # ---------------------------------------------------

        # config d eestilo da interface
        # usando o tema é o clam, aparentemente era pra esse tema ter uma aparência mais moderna
        # só que eu nao achei nao viu, negócio parece um windowx xp
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TNotebook.Tab", padding=[12, 5], font=('Helvetica', 10))
        style.configure("Red.TNotebook.Tab", foreground='red', font=('Helvetica', 10, 'bold'))
        style.map("Treeview", background=[('selected', '#B0E2FF')], foreground=[('selected', 'black')])

        self.notebook = ttk.Notebook(root, style="TNotebook")
        self.notebook.pack(pady=10, padx=10, fill="both", expand=True)

        # criação de cada uma das abas
        self.criar_aba_dashboard()
        self.criar_aba_produtos()
        self.criar_aba_fornecedores()
        self.criar_aba_localizacoes_transferencias()
        self.criar_aba_vendas()
        self.criar_aba_ordens_compra()
        self.criar_aba_relatorios()

        self.atualizar_tudo()

    def validar_float(self, val):
        """essa merda aqui valida se o valor é um número flutuante válido"""
        if val == "": return True
        try:
            float(val.replace(',', '.')) # Permite vírgula como separador decimal
            return True
        except ValueError:
            return False

    # funções auxiliares para criar widgets comuns e evitar repetição de código
    def _criar_frame_com_titulo(self, parent, text):
        return ttk.LabelFrame(parent, text=text, padding=(10, 5))

    def _criar_campo_formulario(self, parent, texto_label, tipo_widget, grid_row, **kwargs):
        label = ttk.Label(parent, text=texto_label)
        label.grid(row=grid_row, column=0, sticky='w', padx=5, pady=5)
        
        widget = tipo_widget(parent, **kwargs)
        widget.grid(row=grid_row, column=1, sticky='ew', padx=5, pady=5)
        return widget

    def _get_id_from_combobox(self, combo_value):
        """extrai o ID numérico do início de uma string """
        try:
            return int(combo_value.split(" - ")[0])
        except (ValueError, IndexError):
            return None

    #region Barcode Scanning Logic
    # Métodos para lidar com a leitura do código de barras

    def lidar_com_keypress_barcode(self, event):
        """
        Captura cada tecla pressionada na janela. Acumula caracteres em um buffer.
        Se a tecla 'Enter' for pressionada (comum em scanners) ou se houver uma pausa,
        o buffer é processado como um código de barras.
        """
        # --- INÍCIO DA CORREÇÃO ---
        # Primeiro, verifica qual widget está com o foco.
        widget_focado = self.root.focus_get()

        # Se o foco estiver em um campo de entrada de texto, ignora a lógica do leitor.
        if isinstance(widget_focado, (ttk.Entry, tk.Text, ttk.Combobox)):
            return
        # --- FIM DA CORREÇÃO ---

        # Cancela o timer anterior para reiniciar a contagem de tempo de inatividade
        if self.barcode_timer is not None:
            self.root.after_cancel(self.barcode_timer)

        # Se a tecla for 'Enter', processa o código imediatamente
        if event.keysym == 'Return':
            self.processar_barcode()
            return "break"  # Impede que o 'Enter' acione outros widgets (como botões)

        # Adiciona o caractere ao buffer apenas se for imprimível
        if event.char and event.char.isprintable():
            self.barcode_buffer += event.char

        # Inicia um novo timer. Se o usuário parar de digitar/escanear por 200ms,
        # o buffer é processado. Isso lida com scanners que não enviam 'Enter'.
        self.barcode_timer = self.root.after(200, self.processar_barcode)

    def processar_barcode(self):
        """
        Processa o buffer do código de barras, busca o produto e atualiza a GUI.
        """
        # Cancela o timer para evitar execuções duplicadas
        if self.barcode_timer is not None:
            self.root.after_cancel(self.barcode_timer)
            self.barcode_timer = None

        barcode_lido = self.barcode_buffer.strip()
        self.barcode_buffer = ""  # Limpa o buffer para a próxima leitura

        if not barcode_lido:
            return

        print(f"Código de barras recebido para processamento: '{barcode_lido}'")

        produto = self.gerenciador.buscar_produto_por_codigo_barras(barcode_lido)

        if produto:
            messagebox.showinfo(
                "Produto Encontrado",
                f"Código de barras correspondente ao produto:\n\nID: {produto.id}\nNome: {produto.nome}",
                parent=self.root
            )
            # Muda para a aba de produtos e foca no item
            self.notebook.select(self.aba_produtos)
            # Adiciona um pequeno delay para garantir que a aba foi renderizada antes de focar no item
            self.root.after(50, lambda: self.focar_no_produto_treeview(produto.id))
        else:
            messagebox.showwarning(
                "Produto Não Encontrado",
                f"Nenhum produto encontrado com o código de barras '{barcode_lido}'.",
                parent=self.root
            )

    def focar_no_produto_treeview(self, produto_id):
        """
        Seleciona, foca e garante a visibilidade de um item na tabela de produtos.
        """
        iid = str(produto_id)  # O iid do Treeview é uma string
        if self.tree_produtos.exists(iid):
            self.tree_produtos.selection_set(iid)
            self.tree_produtos.focus(iid)
            self.tree_produtos.see(iid)  # Rola a view para que o item fique visível
            # O evento de seleção chamará automaticamente self.carregar_produto_para_formulario

    #endregion
    
    #region GUI Creation
    # Mmtodos para se construir a interface de cada aba
    def criar_aba_dashboard(self):
        """cria os widgets do Painel Principal"""
        self.aba_dashboard = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_dashboard, text='Painel Principal')

        frame_metricas = self._criar_frame_com_titulo(self.aba_dashboard, "Métricas Principais")
        frame_metricas.pack(fill='x', pady=5)
        self.lbl_valor_estoque = ttk.Label(frame_metricas, text="Valor Total do Estoque: R$ 0.00", font=("Helvetica", 12, "bold"))
        self.lbl_valor_estoque.pack(pady=5, padx=10, anchor="w")
        self.lbl_itens_unicos = ttk.Label(frame_metricas, text="Itens Únicos: 0", font=("Helvetica", 12, "bold"))
        self.lbl_itens_unicos.pack(pady=5, padx=10, anchor="w")

        frame_alertas = self._criar_frame_com_titulo(self.aba_dashboard, "Alertas de Baixo Estoque (Itens que precisam de reposição)")
        frame_alertas.pack(fill='both', expand=True, pady=10)
        
        # Tabela (Treeview) para exibir os alertas de baixo estoque
        self.tree_alertas = ttk.Treeview(frame_alertas, columns=("ID", "Nome", "Estoque Atual", "Mínimo"), show="headings")
        for col in self.tree_alertas['columns']:
            self.tree_alertas.heading(col, text=col)
        self.tree_alertas.column("ID", width=50, anchor='center')
        self.tree_alertas.pack(fill='both', expand=True)

        ttk.Button(frame_alertas, text="Criar Ordem de Compra para Item Selecionado", command=self.criar_oc_do_alerta).pack(pady=(10,0))

    def criar_aba_produtos(self):
        """Cria os widgets da aba 'Produtos'."""
        self.aba_produtos = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_produtos, text='Produtos')

        # Container com painel divisório para organizar a tela
        left_container = ttk.PanedWindow(self.aba_produtos, orient=tk.VERTICAL)
        left_container.pack(side="left", fill="y", padx=(0, 10))

        # Formulário para adicionar/editar produtos
        form_frame = self._criar_frame_com_titulo(left_container, "Gerenciar Produto")
        left_container.add(form_frame)

        self.entries_prod = {}
        campos = {
            "Nome:": (ttk.Entry, {}), "Descrição:": (ttk.Entry, {}),
            "Categoria:": (ttk.Combobox, {}), # Combobox para categorias
            "Cód. Barras:": (ttk.Entry, {}), "Fornecedor:": (ttk.Combobox, {'state': 'readonly'}),
            "Preço Compra:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_float}),
            "Preço Venda:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_float}),
            "Ponto Ressupr.:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_int}),
            "Qtd. Inicial:": (ttk.Entry, {'validate': 'key', 'validatecommand': self.vcmd_int}),
            "Localização Inicial:": (ttk.Combobox, {'state': 'readonly'})
        }
        for i, (texto, (widget_class, kwargs)) in enumerate(campos.items()):
            self.entries_prod[texto] = self._criar_campo_formulario(form_frame, texto, widget_class, i, width=30, **kwargs)
        
        # Associa um evento para lidar com a criação de novas categorias
        self.entries_prod["Categoria:"].bind("<<ComboboxSelected>>", self.on_categoria_selecionada)

        # Botões de ação para o formulário de produtos
        btn_frame = ttk.Frame(form_frame)
        btn_frame.grid(row=len(campos), column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame, text="Adicionar Novo", command=self.adicionar_produto_gui).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame, text="Atualizar Selecionado", command=self.atualizar_produto_gui).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame, text="Remover Selecionado", command=self.remover_produto_gui).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(btn_frame, text="Limpar Formulário", command=self.limpar_formulario_produtos).grid(row=1, column=1, padx=5, pady=5)
        
        # Frame para ações rápidas de estoque (entrada manual, venda)
        movimento_frame = self._criar_frame_com_titulo(left_container, "Ações Rápidas de Estoque")
        left_container.add(movimento_frame)
        
        self.mov_local = self._criar_campo_formulario(movimento_frame, "Localização:", ttk.Combobox, 1, state='readonly')
        ttk.Button(movimento_frame, text="Registrar Entrada Manual", command=self.registrar_entrada_gui).grid(row=2, column=0, columnspan=2, pady=5, sticky='ew')
        ttk.Button(movimento_frame, text="Iniciar Venda com Itens Sel.", command=self.registrar_venda_gui).grid(row=3, column=0, columnspan=2, pady=5, sticky='ew')
        
        # Tabela para mostrar o detalhe do estoque por localização do produto selecionado
        stock_detail_frame = self._criar_frame_com_titulo(left_container, "Estoque por Local do Item Sel.")
        left_container.add(stock_detail_frame)
        self.tree_estoque_local = ttk.Treeview(stock_detail_frame, columns=("Localização", "Quantidade"), show="headings", height=4)
        self.tree_estoque_local.heading("Localização", text="Localização")
        self.tree_estoque_local.heading("Quantidade", text="Quantidade")
        self.tree_estoque_local.column("Quantidade", anchor='center', width=80)
        self.tree_estoque_local.pack(fill='both', expand=True)

        # Tabela principal com a lista de todos os produtos
        table_frame = self._criar_frame_com_titulo(self.aba_produtos, "Catálogo de Produtos (Use Ctrl/Shift ou leitor de código de barras)")
        table_frame.pack(side="right", fill='both', expand=True)

        self.tree_produtos = ttk.Treeview(table_frame, columns=("ID", "Nome", "Categoria", "Fornecedor", "Estoque Total", "Preço Venda"), show="headings", selectmode='extended')

        col_widths = {"ID": 50, "Nome": 200, "Estoque Total": 100, "Preço Venda": 100}
        for col in self.tree_produtos['columns']:
            self.tree_produtos.heading(col, text=col)
            self.tree_produtos.column(col, width=col_widths.get(col, 120), anchor='center' if col in ["ID", "Estoque Total"] else 'w')
        self.tree_produtos.column("Preço Venda", anchor='e')
        self.tree_produtos.pack(fill='both', expand=True)
        self.tree_produtos.bind("<<TreeviewSelect>>", self.carregar_produto_para_formulario)

    def criar_aba_fornecedores(self):
        """Cria os widgets da aba 'Fornecedores'."""
        self.aba_fornecedores = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_fornecedores, text='Fornecedores')
    
        main_pane = ttk.PanedWindow(self.aba_fornecedores, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)
    
        # Painel da Esquerda (Formulário)
        left_pane = ttk.Frame(main_pane)
        main_pane.add(left_pane, weight=1)
    
        form_frame = self._criar_frame_com_titulo(left_pane, "Gerenciar Fornecedor")
        form_frame.pack(padx=10, pady=10, fill=tk.X)
    
        self.entries_forn = {}
        campos_forn = {
            "Nome do Contato:": (ttk.Entry, {}),
            "Empresa:": (ttk.Entry, {}),
            "Telefone:": (ttk.Entry, {}),
            "Email:": (ttk.Entry, {}),
            "Morada:": (ttk.Entry, {})
        }
        for i, (texto, (widget_class, kwargs)) in enumerate(campos_forn.items()):
            self.entries_forn[texto] = self._criar_campo_formulario(form_frame, texto, widget_class, i, width=40, **kwargs)
    
        btn_frame_forn = ttk.Frame(form_frame)
        btn_frame_forn.grid(row=len(campos_forn), column=0, columnspan=2, pady=15)
        ttk.Button(btn_frame_forn, text="Adicionar", command=self.adicionar_fornecedor_gui).grid(row=0, column=0, padx=5)
        ttk.Button(btn_frame_forn, text="Atualizar", command=self.atualizar_fornecedor_gui).grid(row=0, column=1, padx=5)
        ttk.Button(btn_frame_forn, text="Remover", command=self.remover_fornecedor_gui).grid(row=1, column=0, padx=5, pady=5)
        ttk.Button(btn_frame_forn, text="Limpar", command=self.limpar_formulario_fornecedores).grid(row=1, column=1, padx=5, pady=5)
    
        # Painel da Direita (Listas)
        right_pane = ttk.PanedWindow(main_pane, orient=tk.VERTICAL)
        main_pane.add(right_pane, weight=3)
    
        frame_lista_forn = self._criar_frame_com_titulo(right_pane, "Fornecedores Cadastrados")
        right_pane.add(frame_lista_forn, weight=2)
    
        cols_forn = ("ID", "Nome", "Empresa", "Telefone", "Email")
        self.tree_fornecedores = ttk.Treeview(frame_lista_forn, columns=cols_forn, show="headings")
        for col in cols_forn:
            self.tree_fornecedores.heading(col, text=col)
            self.tree_fornecedores.column(col, width=120)
        self.tree_fornecedores.column("ID", width=40)
        self.tree_fornecedores.pack(fill=tk.BOTH, expand=True)
        self.tree_fornecedores.bind("<<TreeviewSelect>>", self.carregar_fornecedor_para_formulario)
    
        # Tabela para mostrar os produtos do fornecedor selecionado
        frame_produtos_forn = self._criar_frame_com_titulo(right_pane, "Produtos Fornecidos pelo Fornecedor Selecionado")
        right_pane.add(frame_produtos_forn, weight=1)
        
        cols_prod_forn = ("ID", "Nome do Produto", "Categoria")
        self.tree_produtos_do_fornecedor = ttk.Treeview(frame_produtos_forn, columns=cols_prod_forn, show="headings")
        for col in cols_prod_forn:
            self.tree_produtos_do_fornecedor.heading(col, text=col)
        self.tree_produtos_do_fornecedor.column("ID", width=40)
        self.tree_produtos_do_fornecedor.pack(fill=tk.BOTH, expand=True)

    def criar_aba_localizacoes_transferencias(self):
        """Cria os widgets da aba 'Localizações & Transferências'."""
        self.aba_loc_transf = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_loc_transf, text='Localizações & Transferências')

        main_pane = ttk.PanedWindow(self.aba_loc_transf, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Painel da Esquerda para Gerenciamento de Localizações
        left_pane = self._criar_frame_com_titulo(main_pane, "Gerenciar Localizações (Lojas/Armazéns)")
        main_pane.add(left_pane, weight=2)

        form_loc_frame = ttk.Frame(left_pane)
        form_loc_frame.pack(fill=tk.X, pady=5, padx=5)
        self.entry_loc_nome = self._criar_campo_formulario(form_loc_frame, "Nome:", ttk.Entry, 0)
        self.entry_loc_endereco = self._criar_campo_formulario(form_loc_frame, "Endereço:", ttk.Entry, 1)
        
        btn_loc_frame = ttk.Frame(form_loc_frame)
        btn_loc_frame.grid(row=2, column=0, columnspan=2, pady=10)
        ttk.Button(btn_loc_frame, text="Adicionar", command=self.adicionar_localizacao_gui).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_loc_frame, text="Atualizar Sel.", command=self.atualizar_localizacao_gui).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_loc_frame, text="Remover Sel.", command=self.remover_localizacao_gui).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_loc_frame, text="Limpar", command=self.limpar_formulario_localizacao).pack(side=tk.LEFT, padx=5)

        # Tabela de Localizações
        tree_loc_frame = ttk.Frame(left_pane)
        tree_loc_frame.pack(fill=tk.BOTH, expand=True, pady=5, padx=5)
        self.tree_localizacoes = ttk.Treeview(tree_loc_frame, columns=("ID", "Nome", "Endereço"), show="headings")
        self.tree_localizacoes.heading("ID", text="ID"); self.tree_localizacoes.column("ID", width=40)
        self.tree_localizacoes.heading("Nome", text="Nome"); self.tree_localizacoes.column("Nome", width=150)
        self.tree_localizacoes.heading("Endereço", text="Endereço"); self.tree_localizacoes.column("Endereço", width=250)
        self.tree_localizacoes.pack(fill=tk.BOTH, expand=True)
        self.tree_localizacoes.bind("<<TreeviewSelect>>", self.carregar_localizacao_para_formulario)

        # Painel da Direita para Transferência de Estoque
        right_pane = self._criar_frame_com_titulo(main_pane, "Transferir Estoque Entre Localizações")
        main_pane.add(right_pane, weight=1)

        self.transf_produto = self._criar_campo_formulario(right_pane, "Produto:", ttk.Combobox, 0, state='readonly')
        self.transf_origem = self._criar_campo_formulario(right_pane, "De (Origem):", ttk.Combobox, 1, state='readonly')
        self.transf_destino = self._criar_campo_formulario(right_pane, "Para (Destino):", ttk.Combobox, 2, state='readonly')
        self.transf_qtd = self._criar_campo_formulario(right_pane, "Quantidade:", ttk.Entry, 3, validate='key', validatecommand=self.vcmd_int)
        
        ttk.Button(right_pane, text="Confirmar Transferência", command=self.realizar_transferencia_gui).grid(row=4, column=0, columnspan=2, pady=20)
        
        # Evento para atualizar o combo de origem quando um produto é selecionado
        self.transf_produto.bind("<<ComboboxSelected>>", self.atualizar_combos_transferencia)


    def criar_aba_vendas(self):
        """Cria os widgets da aba 'Histórico de Vendas'."""
        self.aba_vendas = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_vendas, text='Histórico de Vendas')

        pane = ttk.PanedWindow(self.aba_vendas, orient=tk.HORIZONTAL)
        pane.pack(fill=tk.BOTH, expand=True)

        # Tabela de vendas realizadas
        frame_vendas = self._criar_frame_com_titulo(pane, "Vendas Realizadas")
        pane.add(frame_vendas, weight=2)
        
        self.tree_vendas = ttk.Treeview(frame_vendas, columns=("ID", "Data", "Cliente", "Valor Total"), show="headings")
        for col in self.tree_vendas['columns']: self.tree_vendas.heading(col, text=col)
        self.tree_vendas.column("ID", width=60); self.tree_vendas.column("Valor Total", anchor='e')
        self.tree_vendas.pack(fill=tk.BOTH, expand=True)
        self.tree_vendas.bind("<<TreeviewSelect>>", self._mostrar_itens_venda)

        # Tabela para detalhar os itens da venda selecionada
        frame_itens = self._criar_frame_com_titulo(pane, "Itens da Venda Selecionada")
        pane.add(frame_itens, weight=3)
        
        self.tree_itens_venda = ttk.Treeview(frame_itens, columns=("Produto", "Qtd", "Preço Un.", "Subtotal"), show="headings")
        for col in self.tree_itens_venda['columns']: self.tree_itens_venda.heading(col, text=col)
        self.tree_itens_venda.column("Qtd", width=50, anchor='center'); self.tree_itens_venda.column("Preço Un.", anchor='e'); self.tree_itens_venda.column("Subtotal", anchor='e')
        self.tree_itens_venda.pack(fill=tk.BOTH, expand=True)

    def criar_aba_ordens_compra(self):
        """Cria os widgets da aba 'Ordens de Compra'."""
        self.aba_ordens_compra = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_ordens_compra, text='Ordens de Compra')
        
        main_pane = ttk.PanedWindow(self.aba_ordens_compra, orient=tk.VERTICAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # Frame superior para criação de uma nova OC
        frame_criar = self._criar_frame_com_titulo(main_pane, "Criar Nova Ordem de Compra")
        main_pane.add(frame_criar, weight=1)

        # Parte do formulário para adicionar um item à OC
        frame_adicionar_item = ttk.Frame(frame_criar)
        frame_adicionar_item.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        
        self.oc_fornecedor_var = tk.StringVar()
        self.oc_combo_fornecedor = self._criar_campo_formulario(frame_adicionar_item, "Fornecedor:", ttk.Combobox, 0, state='readonly', textvariable=self.oc_fornecedor_var)
        self.oc_fornecedor_var.trace_add("write", self._atualizar_combo_produtos_oc) # Atualiza produtos ao mudar fornecedor

        self.oc_combo_produto = self._criar_campo_formulario(frame_adicionar_item, "Produto:", ttk.Combobox, 1, state='readonly')
        self.oc_entry_quantidade = self._criar_campo_formulario(frame_adicionar_item, "Quantidade:", ttk.Entry, 2, validate='key', validatecommand=self.vcmd_int)
        
        btn_add_item = ttk.Button(frame_adicionar_item, text="Adicionar Item ➔", command=self._adicionar_item_oc_lista)
        btn_add_item.grid(row=3, column=0, columnspan=2, pady=10)

        # Tabela para listar os itens da OC que está sendo criada
        frame_itens_oc = self._criar_frame_com_titulo(frame_criar, "Itens da Nova Ordem")
        frame_itens_oc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        self.tree_itens_nova_oc = ttk.Treeview(frame_itens_oc, columns=("ID", "Nome", "Qtd", "Preço Un.", "Subtotal"), show="headings")
        for col in self.tree_itens_nova_oc['columns']: self.tree_itens_nova_oc.heading(col, text=col)
        self.tree_itens_nova_oc.column("ID", width=40); self.tree_itens_nova_oc.column("Qtd", width=50, anchor="center"); self.tree_itens_nova_oc.column("Preço Un.", width=80, anchor="e"); self.tree_itens_nova_oc.column("Subtotal", width=80, anchor="e")
        self.tree_itens_nova_oc.pack(fill=tk.BOTH, expand=True)

        btn_remover_item = ttk.Button(frame_itens_oc, text="Remover Item Selecionado", command=self._remover_item_oc_lista)
        btn_remover_item.pack(pady=5)

        # Botões para salvar ou limpar o formulário da OC
        frame_salvar_oc = ttk.Frame(frame_criar)
        frame_salvar_oc.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=5)
        btn_salvar = ttk.Button(frame_salvar_oc, text="Salvar Ordem de Compra", command=self._salvar_oc)
        btn_salvar.pack(pady=10)
        btn_limpar = ttk.Button(frame_salvar_oc, text="Limpar Formulário", command=self._limpar_form_oc)
        btn_limpar.pack()

        # Frame inferior para listar todas as OCs já registradas
        frame_lista = self._criar_frame_com_titulo(main_pane, "Ordens de Compra Registradas")
        main_pane.add(frame_lista, weight=1)

        self.tree_lista_ocs = ttk.Treeview(frame_lista, columns=("ID", "Fornecedor", "Data", "Valor Total", "Status"), show="headings")
        for col in self.tree_lista_ocs['columns']: self.tree_lista_ocs.heading(col, text=col)
        self.tree_lista_ocs.pack(fill=tk.BOTH, expand=True, pady=5)

        # Botões de ação para as OCs da lista (visualizar, receber, etc.)
        frame_botoes_lista = ttk.Frame(frame_lista)
        frame_botoes_lista.pack(fill=tk.X, pady=5)
        ttk.Button(frame_botoes_lista, text="Visualizar/Salvar Recibo", command=self._visualizar_oc).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_lista, text="Marcar como Recebida", command=self._marcar_oc_recebida).pack(side=tk.LEFT, padx=5)
        ttk.Button(frame_botoes_lista, text="Marcar como Enviada", command=lambda: self._atualizar_status_oc_gui("Enviada")).pack(side=tk.LEFT, padx=5)

    def criar_aba_relatorios(self):
        """Cria os widgets da aba 'Relatórios'."""
        self.aba_relatorios = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(self.aba_relatorios, text='Relatórios')

        # Painel de controle à esquerda para selecionar o tipo de relatório e filtros
        painel_controle = self._criar_frame_com_titulo(self.aba_relatorios, "Opções de Relatório")
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

        # Frame para os filtros dinâmicos (aparecem dependendo do relatório)
        self.relatorio_frame_filtros = self._criar_frame_com_titulo(painel_controle, "Filtros")
        self.relatorio_frame_filtros.grid(row=2, column=0, sticky='ew', padx=5)
        
        # Widgets de filtro (inicialmente ocultos)
        self.relatorio_lbl_produto = ttk.Label(self.relatorio_frame_filtros, text="Selecione o Produto:")
        self.relatorio_combo_produto = ttk.Combobox(self.relatorio_frame_filtros, state='readonly')
        
        self.relatorio_lbl_data_inicio = ttk.Label(self.relatorio_frame_filtros, text="Data de Início (DD/MM/AAAA):")
        self.relatorio_entry_data_inicio = ttk.Entry(self.relatorio_frame_filtros)
        self.relatorio_lbl_data_fim = ttk.Label(self.relatorio_frame_filtros, text="Data de Fim (DD/MM/AAAA):")
        self.relatorio_entry_data_fim = ttk.Entry(self.relatorio_frame_filtros)

        ttk.Button(painel_controle, text="Gerar Relatório", command=self._gerar_relatorio_detalhado_gui).grid(row=3, column=0, pady=20, padx=5)

        # Área de texto à direita para exibir o relatório gerado
        frame_resultado = self._criar_frame_com_titulo(self.aba_relatorios, "Visualização do Relatório")
        frame_resultado.pack(side="right", fill="both", expand=True)

        self.txt_relatorio = tk.Text(frame_resultado, wrap='word', height=20, font=("Courier New", 10))
        self.txt_relatorio.pack(fill='both', expand=True)
    #endregion

    #region GUI Actions
    # Métodos que são chamados por eventos da GUI (cliques de botão, seleções, etc.)
    # e que interagem com a classe GerenciadorEstoque.

    # --- Ações de Fornecedores ---
    def adicionar_fornecedor_gui(self):
        """Coleta dados do formulário e chama o gerenciador para adicionar um fornecedor."""
        dados = {k.replace(':', '').replace(' ', '_').lower(): v.get() for k, v in self.entries_forn.items()}
        if not dados['nome_do_contato'] or not dados['empresa']:
            return messagebox.showerror("Erro de Validação", "O nome do contato e da empresa são obrigatórios.")
            
        dados_finais = {
            'nome': dados['nome_do_contato'],
            'empresa': dados['empresa'],
            'telefone': dados['telefone'],
            'email': dados['email'],
            'morada': dados['morada']
        }

        try:
            self.gerenciador.adicionar_fornecedor(**dados_finais)
            messagebox.showinfo("Sucesso", "Fornecedor adicionado com sucesso!")
            self.limpar_formulario_fornecedores()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Adicionar", f"Ocorreu um erro: {e}")

    def atualizar_fornecedor_gui(self):
        """Coleta dados do formulário e chama o gerenciador para atualizar o fornecedor selecionado."""
        if not (selected_items := self.tree_fornecedores.selection()):
            return messagebox.showwarning("Aviso", "Selecione um fornecedor da lista para atualizar.")
            
        fornecedor_id = int(selected_items[0])
        dados = {k.replace(':', '').replace(' ', '_').lower(): v.get() for k, v in self.entries_forn.items()}
        if not dados['nome_do_contato'] or not dados['empresa']:
            return messagebox.showerror("Erro de Validação", "O nome do contato e da empresa são obrigatórios.")

        dados_finais = {
            'nome': dados['nome_do_contato'],
            'empresa': dados['empresa'],
            'telefone': dados['telefone'],
            'email': dados['email'],
            'morada': dados['morada']
        }

        try:
            self.gerenciador.atualizar_fornecedor(fornecedor_id, **dados_finais)
            messagebox.showinfo("Sucesso", "Fornecedor atualizado com sucesso!")
            self.limpar_formulario_fornecedores()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Atualizar", f"Ocorreu um erro: {e}")

    def remover_fornecedor_gui(self):
        """Pede confirmação e chama o gerenciador para remover o fornecedor selecionado."""
        if not (selected_items := self.tree_fornecedores.selection()):
            return messagebox.showwarning("Aviso", "Selecione um fornecedor da lista para remover.")
            
        fornecedor_id = int(selected_items[0])
        item_selecionado = self.tree_fornecedores.item(selected_items[0])
        fornecedor_nome = item_selecionado['values'][1]
        
        aviso = (f"Tem certeza que deseja remover o fornecedor '{fornecedor_nome}'?\n\n"
                 "ATENÇÃO: Todos os produtos associados a este fornecedor também serão removidos permanentemente. "
                 "Esta ação não pode ser desfeita.")

        if messagebox.askyesno("Confirmar Remoção Permanente", aviso, icon='warning'):
            try:
                self.gerenciador.remover_fornecedor(fornecedor_id)
                messagebox.showinfo("Sucesso", "Fornecedor e seus produtos foram removidos.")
                self.limpar_formulario_fornecedores()
                self.atualizar_tudo()
            except Exception as e:
                messagebox.showerror("Erro ao Remover", f"Ocorreu um erro: {e}")

    def limpar_formulario_fornecedores(self, limpar_selecao=True):
        """Limpa os campos do formulário de fornecedores e a seleção na tabela."""
        if limpar_selecao and self.tree_fornecedores.selection():
            self.tree_fornecedores.selection_remove(self.tree_fornecedores.selection())
            
        for widget in self.entries_forn.values():
            widget.delete(0, tk.END)
        
        # Limpa a lista de produtos do fornecedor
        for i in self.tree_produtos_do_fornecedor.get_children():
            self.tree_produtos_do_fornecedor.delete(i)

    def carregar_fornecedor_para_formulario(self, event=None):
        """Carrega os dados do fornecedor selecionado na tabela para o formulário."""
        if not (selected_items := self.tree_fornecedores.selection()):
            return

        fornecedor_id = int(selected_items[0])
        fornecedor = self.gerenciador.fornecedores.get(fornecedor_id)
        if not fornecedor:
            return
            
        self.limpar_formulario_fornecedores(limpar_selecao=False)
        self.entries_forn["Nome do Contato:"].insert(0, fornecedor.nome)
        self.entries_forn["Empresa:"].insert(0, fornecedor.empresa)
        self.entries_forn["Telefone:"].insert(0, fornecedor.telefone)
        self.entries_forn["Email:"].insert(0, fornecedor.email)
        self.entries_forn["Morada:"].insert(0, fornecedor.morada)

        # Atualiza a lista de produtos fornecidos por este fornecedor
        for i in self.tree_produtos_do_fornecedor.get_children():
            self.tree_produtos_do_fornecedor.delete(i)
            
        produtos_fornecidos = [p for p in self.gerenciador.produtos.values() if p.fornecedor.id == fornecedor_id]
        for produto in produtos_fornecidos:
            self.tree_produtos_do_fornecedor.insert("", "end", values=(
                produto.id, produto.nome, produto.categoria
            ))
    #endregion

    #region GUI Actions - Localizações e Transferências
    def adicionar_localizacao_gui(self):
        """Adiciona uma nova localização a partir dos dados do formulário."""
        nome = self.entry_loc_nome.get()
        endereco = self.entry_loc_endereco.get()
        if not nome:
            return messagebox.showerror("Erro de Validação", "O nome da localização é obrigatório.")
        try:
            self.gerenciador.adicionar_localizacao(nome=nome, endereco=endereco)
            messagebox.showinfo("Sucesso", f"Localização '{nome}' adicionada com sucesso!")
            self.limpar_formulario_localizacao()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Adicionar", str(e))

    def atualizar_localizacao_gui(self):
        """Atualiza a localização selecionada."""
        selected = self.tree_localizacoes.selection()
        if not selected:
            return messagebox.showwarning("Aviso", "Selecione uma localização para atualizar.")
        
        loc_id = int(selected[0])
        nome = self.entry_loc_nome.get()
        endereco = self.entry_loc_endereco.get()
        if not nome:
            return messagebox.showerror("Erro de Validação", "O nome da localização é obrigatório.")

        try:
            self.gerenciador.atualizar_localizacao(loc_id, nome=nome, endereco=endereco)
            messagebox.showinfo("Sucesso", f"Localização '{nome}' atualizada com sucesso!")
            self.limpar_formulario_localizacao()
            self.atualizar_tudo()
        except Exception as e:
            messagebox.showerror("Erro ao Atualizar", str(e))

    def remover_localizacao_gui(self):
        """Remove a localização selecionada, após confirmação."""
        selected = self.tree_localizacoes.selection()
        if not selected:
            return messagebox.showwarning("Aviso", "Selecione uma localização para remover.")
        
        loc_id = int(selected[0])
        loc_nome = self.gerenciador.localizacoes[loc_id].nome
        aviso = f"Tem certeza que deseja remover a localização '{loc_nome}'?\n\nEsta ação não pode ser desfeita."

        if messagebox.askyesno("Confirmar Remoção", aviso, icon='warning'):
            try:
                self.gerenciador.remover_localizacao(loc_id)
                messagebox.showinfo("Sucesso", "Localização removida.")
                self.limpar_formulario_localizacao()
                self.atualizar_tudo()
            except Exception as e:
                messagebox.showerror("Erro ao Remover", str(e))

    def carregar_localizacao_para_formulario(self, event=None):
        """Carrega os dados da localização selecionada para o formulário."""
        selected = self.tree_localizacoes.selection()
        if not selected: return

        loc_id = int(selected[0])
        loc = self.gerenciador.localizacoes.get(loc_id)
        if not loc: return

        self.limpar_formulario_localizacao(limpar_selecao=False)
        self.entry_loc_nome.insert(0, loc.nome)
        self.entry_loc_endereco.insert(0, loc.endereco)

    def limpar_formulario_localizacao(self, limpar_selecao=True):
        """Limpa o formulário de localizações."""
        if limpar_selecao and self.tree_localizacoes.selection():
            self.tree_localizacoes.selection_remove(self.tree_localizacoes.selection())
        self.entry_loc_nome.delete(0, tk.END)
        self.entry_loc_endereco.delete(0, tk.END)
    
    def atualizar_combos_transferencia(self, event=None):
        """Atualiza o combo de localização de origem com base no produto selecionado para transferência."""
        self.transf_origem.set('')
        self.transf_destino.set('')
        
        produto_id = self._get_id_from_combobox(self.transf_produto.get())
        if not produto_id:
            self.transf_origem['values'] = []
            return
        
        # Popula o combo de origem apenas com locais que têm estoque do produto selecionado
        produto = self.gerenciador.produtos[produto_id]
        locais_com_estoque = [
            str(l) for l in self.gerenciador.localizacoes.values() 
            if produto.estoque_por_local.get(l.nome, 0) > 0
        ]
        self.transf_origem['values'] = locais_com_estoque

    def realizar_transferencia_gui(self):
        """Coleta dados do formulário de transferência e chama o gerenciador para executá-la."""
        try:
            produto_id = self._get_id_from_combobox(self.transf_produto.get())
            origem_id = self._get_id_from_combobox(self.transf_origem.get())
            destino_id = self._get_id_from_combobox(self.transf_destino.get())
            
            if not all([produto_id, origem_id, destino_id]):
                raise ValueError("Produto, origem e destino devem ser selecionados.")
            
            quantidade = int(self.transf_qtd.get())

            self.gerenciador.transferir_estoque(produto_id, origem_id, destino_id, quantidade)
            messagebox.showinfo("Sucesso", "Transferência realizada com sucesso!")
            self.atualizar_tudo()
            # Limpa campos do formulário de transferência
            self.transf_produto.set('')
            self.transf_origem.set('')
            self.transf_destino.set('')
            self.transf_qtd.delete(0, tk.END)

        except Exception as e:
            messagebox.showerror("Erro na Transferência", str(e))

    #endregion

    #region GUI Actions - Produtos e outros
    def on_categoria_selecionada(self, event=None):
        """Lida com a criação de uma nova categoria diretamente pelo combobox."""
        combo = self.entries_prod["Categoria:"]
        if combo.get() == "--- Adicionar Nova Categoria ---":
            nova_categoria = simpledialog.askstring("Nova Categoria", "Digite o nome da nova categoria:", parent=self.root)
            if nova_categoria and nova_categoria.strip():
                # Adiciona a nova categoria à lista do combobox e a seleciona
                valores_atuais = list(combo['values'])
                valores_atuais.insert(-1, nova_categoria) # Insere antes da opção "Adicionar"
                combo['values'] = valores_atuais
                combo.set(nova_categoria)
            else:
                combo.set("") # Limpa se o usuário cancelar ou não digitar nada

    def _exibir_alerta_reabastecimento(self, produto: Produto):
        """Mostra um popup de alerta quando um produto atinge o ponto de ressuprimento."""
        messagebox.showwarning(
            "Alerta de Reabastecimento",
            f"O stock do produto atingiu o nível mínimo!\n\n"
            f"Produto: {produto.nome}\n"
            f"Stock Atual: {produto.get_estoque_total()} unidades\n"
            f"Nível Mínimo: {produto.ponto_ressuprimento} unidades\n\n"
            "Verifique o Painel Principal para criar uma Ordem de Compra."
        )
    
    def registrar_entrada_gui(self):
        """Registra a entrada manual de estoque para os produtos selecionados."""
        selected_items = self.tree_produtos.selection()
        if not selected_items:
            return messagebox.showwarning("Aviso", "Selecione um ou mais produtos da lista.")

        try:
            # Pede a quantidade em uma janela de diálogo
            quantidade = simpledialog.askinteger("Quantidade", f"Digite a quantidade a ser adicionada para os {len(selected_items)} produtos selecionados:", parent=self.root, minvalue=1)
            if not quantidade:
                return 
        except (ValueError, TypeError):
            return messagebox.showerror("Erro", "Insira uma quantidade válida (número inteiro > 0).")

        localizacao_str = self.mov_local.get()
        if not localizacao_str:
            return messagebox.showerror("Erro", "Selecione uma localização para a entrada.")
        localizacao_id = self._get_id_from_combobox(localizacao_str)
        
        sucessos = []
        falhas = []
        alertas = []

        # Itera sobre os produtos selecionados para movimentar o estoque
        for item_iid in selected_items:
            produto_id = int(item_iid)
            produto = self.gerenciador.produtos[produto_id]
            try:
                _, produto_alertado = self.gerenciador.movimentar_estoque(
                    produto_id, localizacao_id, quantidade, "Entrada Manual Múltipla"
                )
                sucessos.append(produto.nome)
                if produto_alertado:
                    alertas.append(produto_alertado)
            except Exception as e:
                falhas.append(f"{produto.nome}: {e}")
        
        msg_final = f"{len(sucessos)} produto(s) tiveram entrada registrada com sucesso."
        if falhas:
            msg_final += "\n\nFalhas:\n" + "\n".join(falhas)
        
        messagebox.showinfo("Resultado da Operação", msg_final)
        self.atualizar_tudo()
        self.mov_local.set('')

        # Exibe alertas de reabastecimento, se houver
        for p_alerta in alertas:
            self._exibir_alerta_reabastecimento(p_alerta)

    def registrar_venda_gui(self):
        """Inicia o processo de venda para os produtos selecionados."""
        selected_iids = self.tree_produtos.selection()
        if not selected_iids:
            return messagebox.showwarning("Aviso", "Selecione um ou mais produtos para vender.")
        
        # Abre uma nova janela (Toplevel) para registrar os detalhes da venda
        self._abrir_dialogo_venda_multipla(selected_iids)

    def _abrir_dialogo_venda_multipla(self, selected_iids: tuple):
        """Cria e exibe a janela de diálogo para registrar uma nova venda."""
        top = tk.Toplevel(self.root)
        top.title(f"Registrar Venda - {len(selected_iids)} Itens")
        top.geometry("600x500")
        top.transient(self.root) # Mantém a janela na frente da principal
        top.grab_set() # Bloqueia interação com a janela principal

        info_frame = self._criar_frame_com_titulo(top, "Informações da Venda")
        info_frame.pack(padx=10, pady=10, fill='x')
        
        entry_cliente = self._criar_campo_formulario(info_frame, "Nome do Cliente:", ttk.Entry, 0)
        combo_local_saida = self._criar_campo_formulario(info_frame, "Local de Saída:", ttk.Combobox, 1, state='readonly', values=[str(l) for l in self.gerenciador.localizacoes.values()])

        # Frame com scroll para a lista de itens da venda
        canvas_frame = self._criar_frame_com_titulo(top, "Itens e Quantidades")
        canvas_frame.pack(padx=10, pady=(0,10), fill='both', expand=True)

        canvas = tk.Canvas(canvas_frame)
        scrollbar = ttk.Scrollbar(canvas_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        entries_qtd = {}
        
        ttk.Label(scrollable_frame, text="Produto", font=('Helvetica', 10, 'bold')).grid(row=0, column=0, padx=5, pady=5, sticky='w')
        ttk.Label(scrollable_frame, text="Estoque no Local", font=('Helvetica', 10, 'bold')).grid(row=0, column=1, padx=5, pady=5)
        ttk.Label(scrollable_frame, text="Quantidade a Vender", font=('Helvetica', 10, 'bold')).grid(row=0, column=2, padx=5, pady=5)

        # Adiciona uma linha para cada produto selecionado
        for i, iid in enumerate(selected_iids, start=1):
            produto_id = int(iid)
            produto = self.gerenciador.produtos[produto_id]
            
            ttk.Label(scrollable_frame, text=f"{produto.nome}").grid(row=i, column=0, sticky='w', padx=5, pady=2)
            
            lbl_estoque = ttk.Label(scrollable_frame, text="Selecione o local")
            lbl_estoque.grid(row=i, column=1, padx=5, pady=2)

            entry_qtd = ttk.Entry(scrollable_frame, width=10, validate='key', validatecommand=self.vcmd_int)
            entry_qtd.grid(row=i, column=2, padx=5, pady=2)
            entries_qtd[produto_id] = (entry_qtd, lbl_estoque)

        def on_local_change(*args):
            """Atualiza a label de estoque disponível quando o local de saída muda."""
            local_str = combo_local_saida.get()
            if not local_str: return
            
            local_obj = self.gerenciador.localizacoes[self._get_id_from_combobox(local_str)]
            for pid, (_, lbl) in entries_qtd.items():
                estoque_disponivel = self.gerenciador.produtos[pid].estoque_por_local.get(local_obj.nome, 0)
                lbl.config(text=f"{estoque_disponivel} un.")

        combo_local_saida.bind("<<ComboboxSelected>>", on_local_change)

        btn_frame = ttk.Frame(top)
        btn_frame.pack(pady=10)
        
        btn_confirmar = ttk.Button(btn_frame, text="Confirmar Venda", command=lambda: self._processar_venda_multipla(
            top, entry_cliente, combo_local_saida, entries_qtd
        ))
        btn_confirmar.pack(side='left', padx=10)
        ttk.Button(btn_frame, text="Cancelar", command=top.destroy).pack(side='left')

    def _processar_venda_multipla(self, toplevel, entry_cliente, combo_local, entries_qtd):
        """Valida e processa os dados da janela de venda."""
        nome_cliente = entry_cliente.get().strip()
        if not nome_cliente:
            return messagebox.showerror("Erro de Validação", "O nome do cliente é obrigatório.", parent=toplevel)
        
        local_str = combo_local.get()
        if not local_str:
            return messagebox.showerror("Erro de Validação", "Selecione o local de saída do estoque.", parent=toplevel)
        
        localizacao_id = self._get_id_from_combobox(local_str)

        itens_para_venda = []
        erros_validacao = []

        # Coleta e valida a quantidade para cada item
        for produto_id, (entry_qtd, _) in entries_qtd.items():
            qtd_str = entry_qtd.get()
            if not qtd_str: continue 

            try:
                quantidade = int(qtd_str)
                if quantidade <= 0:
                    erros_validacao.append(f"- {self.gerenciador.produtos[produto_id].nome}: Quantidade deve ser maior que zero.")
                    continue
                
                itens_para_venda.append({
                    'produto_id': produto_id,
                    'quantidade': quantidade
                })
            except ValueError:
                erros_validacao.append(f"- {self.gerenciador.produtos[produto_id].nome}: Quantidade inválida.")

        if erros_validacao:
            return messagebox.showerror("Erros de Validação", "Corrija os seguintes erros:\n" + "\n".join(erros_validacao), parent=toplevel)

        if not itens_para_venda:
            return messagebox.showwarning("Aviso", "Nenhum item com quantidade válida para vender.", parent=toplevel)

        if not messagebox.askyesno("Confirmar Venda", f"Confirma a venda de {len(itens_para_venda)} tipo(s) de produto para '{nome_cliente}'?", parent=toplevel):
            return

        try:
            # Chama o gerenciador para registrar a venda
            nova_venda, produtos_alertados = self.gerenciador.registrar_venda(itens_para_venda, nome_cliente, localizacao_id)
            messagebox.showinfo("Sucesso", f"Venda #{nova_venda.id} registrada com sucesso!")
            toplevel.destroy() # Fecha a janela de venda
            self.atualizar_tudo()
            if produtos_alertados:
                for p in produtos_alertados:
                    self._exibir_alerta_reabastecimento(p)
        except ValueError as e:
            messagebox.showerror("Erro de Venda", str(e), parent=toplevel)
        except Exception as e:
            messagebox.showerror("Erro Inesperado", f"Ocorreu um erro: {e}", parent=toplevel)


    def adicionar_produto_gui(self):
        """Adiciona um novo produto a partir do formulário."""
        dados = {k.replace(':', ''): v.get().strip() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        
        categoria_selecionada = dados['Categoria']
        if not categoria_selecionada:
            return messagebox.showerror("Erro de Validação", "O campo Categoria é obrigatório.")

        if not all(obrigatorios):
            return messagebox.showerror("Erro", "Campos obrigatórios: Nome, Fornecedor, Preços e Ponto de Ressuprimento.")
        # Se for informada uma quantidade inicial, o local também deve ser informado
        if dados['Qtd. Inicial'] and not dados['Localização Inicial']:
            return messagebox.showerror("Erro", "Se a quantidade inicial for informada, a localização é obrigatória.")

        try:
            fornecedor_id = self._get_id_from_combobox(dados['Fornecedor'])
            if not fornecedor_id:
                raise ValueError("Fornecedor inválido ou não selecionado.")

            preco_compra = float(dados['Preço Compra'].replace(',', '.'))
            preco_venda = float(dados['Preço Venda'].replace(',', '.'))

            novo_produto = self.gerenciador.adicionar_produto(
                nome=dados['Nome'], descricao=dados['Descrição'] or "N/A", categoria=categoria_selecionada,
                fornecedor_id=fornecedor_id,
                codigo_barras=dados['Cód. Barras'] or "N/A", preco_compra=preco_compra,
                preco_venda=preco_venda, ponto_ressuprimento=int(dados['Ponto Ressupr.'])
            )
            # Se houver quantidade inicial, movimenta o estoque
            if dados['Qtd. Inicial']:
                local_id = self._get_id_from_combobox(dados['Localização Inicial'])
                if not local_id:
                    self.gerenciador.remover_produto(novo_produto.id) # Desfaz a criação do produto
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
        """Atualiza o produto selecionado na tabela com os dados do formulário."""
        selected_items = self.tree_produtos.selection()
        if not selected_items:
            return messagebox.showwarning("Aviso", "Selecione um produto para atualizar.")
        if len(selected_items) > 1:
            return messagebox.showwarning("Aviso", "A atualização só pode ser feita em um produto por vez.")
        
        dados = {k.replace(':', ''): v.get().strip() for k, v in self.entries_prod.items()}
        obrigatorios = [dados['Nome'], dados['Fornecedor'], dados['Preço Compra'], dados['Preço Venda'], dados['Ponto Ressupr.']]
        
        categoria_selecionada = dados['Categoria']
        if not categoria_selecionada:
            return messagebox.showerror("Erro de Validação", "O campo Categoria é obrigatório.")

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
                'categoria': categoria_selecionada, 'codigo_barras': dados['Cód. Barras'] or "N/A",
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
        """Remove o(s) produto(s) selecionado(s) na tabela."""
        if not (selected_items := self.tree_produtos.selection()):
            return messagebox.showwarning("Aviso", "Selecione um ou mais produtos para remover.")
        
        nomes_produtos = [self.gerenciador.produtos[int(iid)].nome for iid in selected_items]
        
        aviso = (f"Tem certeza que deseja remover os {len(nomes_produtos)} produtos selecionados?\n\n"
                 f"- {', '.join(nomes_produtos)}\n\n"
                 "Esta ação não pode ser desfeita e removerá todo o histórico associado.")

        if messagebox.askyesno("Confirmar Remoção", aviso):
            removidos = 0
            for iid in selected_items:
                if self.gerenciador.remover_produto(int(iid)):
                    removidos += 1
            
            messagebox.showinfo("Sucesso", f"{removidos} produto(s) removido(s)!")
            self.limpar_formulario_produtos()
            self.atualizar_tudo()

    def carregar_produto_para_formulario(self, event=None):
        """Carrega os dados do produto selecionado para o formulário de produtos."""
        # Limpa a tabela de estoque por local
        for i in self.tree_estoque_local.get_children():
            self.tree_estoque_local.delete(i)

        selected_items = self.tree_produtos.selection()
        # Se mais de um item estiver selecionado, apenas limpa o formulário
        if len(selected_items) != 1:
            self.limpar_formulario_produtos(limpar_selecao=False)
            return
        
        produto_id = int(selected_items[0])
        produto = self.gerenciador.produtos.get(produto_id)
        if not produto:
            return

        self.limpar_formulario_produtos(limpar_selecao=False)

        # Preenche os campos do formulário
        self.entries_prod["Nome:"].insert(0, produto.nome)
        self.entries_prod["Descrição:"].insert(0, produto.descricao)
        self.entries_prod["Categoria:"].set(produto.categoria)
        self.entries_prod["Cód. Barras:"].insert(0, produto.codigo_barras)
        self.entries_prod["Preço Compra:"].insert(0, str(produto.preco_compra).replace('.', ','))
        self.entries_prod["Preço Venda:"].insert(0, str(produto.preco_venda).replace('.', ',')) 
        self.entries_prod["Ponto Ressupr.:"].insert(0, str(produto.ponto_ressuprimento))
        self.entries_prod["Fornecedor:"].set(str(produto.fornecedor))
        
        # Desabilita campos que não fazem sentido na atualização (como qtd inicial)
        self.entries_prod["Qtd. Inicial:"].config(state='disabled')
        self.entries_prod["Localização Inicial:"].config(state='disabled')

        # Preenche a tabela de estoque por localização para o produto selecionado
        for local, qtd in sorted(produto.estoque_por_local.items()):
            if qtd > 0:
                self.tree_estoque_local.insert("", "end", values=(local, qtd))

    def limpar_formulario_produtos(self, limpar_selecao=True):
        """Limpa todos os campos do formulário de produtos."""
        if limpar_selecao and self.tree_produtos.selection():
            self.tree_produtos.selection_remove(self.tree_produtos.selection())
            
        for widget in self.entries_prod.values():
            widget.config(state='normal')
            if isinstance(widget, ttk.Combobox):
                widget.set('')
            else:
                widget.delete(0, tk.END)
                
        # Garante que alguns combos voltem ao estado 'readonly'
        for key in ["Fornecedor:", "Localização Inicial:"]:
            if key in self.entries_prod:
                self.entries_prod[key].config(state='readonly')
        
        self.mov_local.set('')

        for i in self.tree_estoque_local.get_children():
            self.tree_estoque_local.delete(i)

    def _mostrar_itens_venda(self, event=None):
        """Exibe os itens da venda selecionada na tabela de detalhes."""
        for i in self.tree_itens_venda.get_children():
            self.tree_itens_venda.delete(i)
        
        if not (selected_items := self.tree_vendas.selection()): return
        
        venda_id = int(self.tree_vendas.item(selected_items[0])['values'][0])
        venda = self.gerenciador.vendas.get(venda_id)
        
        if venda:
            for item in venda.itens:
                self.tree_itens_venda.insert("", "end", values=(
                    item.produto.nome, item.quantidade,
                    f"R$ {item.preco_venda_unitario:,.2f}", f"R$ {item.subtotal:,.2f}"
                ))

    def _atualizar_combo_produtos_oc(self, *args):
        """Atualiza o combobox de produtos na aba de OC com base no fornecedor selecionado."""
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
        """Adiciona um item à lista temporária da nova OC."""
        try:
            produto_id = self._get_id_from_combobox(self.oc_combo_produto.get())
            if not produto_id:
                raise ValueError("Selecione um produto.")
            
            quantidade = int(self.oc_entry_quantidade.get())
            if quantidade <= 0:
                raise ValueError("A quantidade deve ser maior que zero.")
            
            produto = self.gerenciador.produtos[produto_id]

            # Se o produto já está na lista, apenas soma a quantidade
            for item in self.itens_oc_atual:
                if item['produto_id'] == produto_id:
                    item['quantidade'] += quantidade
                    item['subtotal'] = item['quantidade'] * item['preco_unitario']
                    self._atualizar_tree_itens_nova_oc()
                    return

            # Caso contrário, adiciona como um novo item
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
        """Remove um item da lista temporária da nova OC."""
        if not (selected_tree_items := self.tree_itens_nova_oc.selection()):
            return messagebox.showwarning("Aviso", "Selecione um item da lista para remover.")
        
        item_id = int(self.tree_itens_nova_oc.item(selected_tree_items[0])['values'][0])
        self.itens_oc_atual = [item for item in self.itens_oc_atual if item['produto_id'] != item_id]
        self._atualizar_tree_itens_nova_oc()

    def _salvar_oc(self):
        """Salva a nova ordem de compra com os itens da lista temporária."""
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
        """Limpa o formulário de criação de OC."""
        self.oc_fornecedor_var.set('')
        self.oc_combo_produto.set('')
        self.oc_combo_produto['values'] = []
        self.oc_entry_quantidade.delete(0, tk.END)
        self.itens_oc_atual.clear()
        self._atualizar_tree_itens_nova_oc()

    def _marcar_oc_recebida(self):
        """Marca uma OC como 'Recebida' e atualiza o estoque."""
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        ordem = self.gerenciador.ordens_compra.get(ordem_id)

        if ordem.status == "Recebida":
            return messagebox.showinfo("Informação", "Esta ordem já foi recebida.")

        localizacoes = list(self.gerenciador.localizacoes.values())
        if not localizacoes:
            return messagebox.showerror("Erro", "Nenhuma localização de estoque cadastrada. Cadastre uma localização primeiro.")
        
        # Pede ao usuário para escolher a localização de entrada do estoque
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
        """atualiza o status de uma OC para um status que não envolve estoque (tipo é o caso de Enviada)"""
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
        """abre uma janela para visualizar e salvar o recibo """
        if not (selected_items := self.tree_lista_ocs.selection()):
            return messagebox.showwarning("Aviso", "Selecione uma Ordem de Compra da lista.")
        
        ordem_id = int(self.tree_lista_ocs.item(selected_items[0])['values'][0])
        ordem = self.gerenciador.ordens_compra.get(ordem_id)
        if not ordem: return

        # cria uma nova janela 
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
{ordem.fornecedor.empresa} (Contato: {ordem.fornecedor.nome}, ID: {ordem.fornecedor.id})
Telefone: {ordem.fornecedor.telefone} | Email: {ordem.fornecedor.email}
Morada: {ordem.fornecedor.morada}
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
        # se caso o rebortlab nao estiver instalado, desabilita o botão
        if not REPORTLAB_DISPONIVEL:
            btn_pdf.config(state="disabled")

        ttk.Button(frame_botoes_salvar, text="Salvar como TXT", command=lambda: self._salvar_oc_txt(ordem)).pack(side=tk.RIGHT)

    def _gerar_texto_recibo(self, ordem: OrdemCompra) -> str:
        """formatando o recibo de uma Ordem de Compra em texto simples (um txt)"""
        linhas = [
            "==========================================",
            "        ORDEM DE COMPRA (RECIBO)        ",
            "==========================================",
            f"Número do Pedido: {ordem.id}",
            f"Data de Emissão: {ordem.data_criacao.strftime('%d/%m/%Y %H:%M:%S')}",
            f"Status: {ordem.status}",
            "\n--- DADOS DO FORNECEDOR ---",
            f"Empresa: {ordem.fornecedor.empresa}",
            f"Nome do Contato: {ordem.fornecedor.nome}",
            f"Telefone: {ordem.fornecedor.telefone}",
            f"Email: {ordem.fornecedor.email}",
            f"Morada: {ordem.fornecedor.morada}",
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
        """Salva o recibo de uma OC em um arquivo de texto (.txt)."""
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
        """Salva o recibo de uma OC em um arquivo PDF usando a biblioteca ReportLab."""
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
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch

            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter
            
            # posição inicial Y (começa do topo da página)
            y = height - inch
            c.setFont("Helvetica-Bold", 16)
            c.drawString(inch, y, f"ORDEM DE COMPRA #{ordem.id}")
            y -= 0.5 * inch
            
            # desenha as informações do cabeçalho
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, f"Data de Emissão: {ordem.data_criacao.strftime('%d/%m/%Y')}")
            c.drawString(width - 2.5*inch, y, f"Status: {ordem.status}")
            y -= 0.3 * inch

            c.line(inch, y, width - inch, y) # Linha horizontal
            y -= 0.3 * inch
            
            # desenha as informações do fornecedor
            c.setFont("Helvetica-Bold", 11)
            c.drawString(inch, y, "Dados do Fornecedor:")
            y -= 0.2 * inch
            c.setFont("Helvetica", 10)
            c.drawString(inch, y, f"Empresa: {ordem.fornecedor.empresa} (Contato: {ordem.fornecedor.nome})")
            y -= 0.2 * inch
            c.drawString(inch, y, f"Telefone: {ordem.fornecedor.telefone} | Email: {ordem.fornecedor.email}")
            y -= 0.2 * inch
            c.drawString(inch, y, f"Morada: {ordem.fornecedor.morada}")
            y -= 0.4 * inch
            
            c.line(inch, y, width - inch, y)
            y -= 0.3 * inch
            
            # kacabeçalho da tabela de itens
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

            # desenha cada item da OC
            c.setFont("Helvetica", 10)
            for item in ordem.itens:
                c.drawString(inch, y, str(item.produto.id))
                c.drawString(inch + 0.5*inch, y, item.produto.nome)
                c.drawString(width - 3.5*inch, y, str(item.quantidade))
                c.drawString(width - 2.8*inch, y, f"R$ {item.preco_unitario:.2f}")
                c.drawString(width - 1.5*inch, y, f"R$ {item.subtotal:.2f}")
                y -= 0.2 * inch
                # Quebra de página se o conteúdo chegar perto do final
                if y < inch: 
                    c.showPage()
                    y = height - inch
                    c.setFont("Helvetica", 10)

            y -= 0.2 * inch
            c.line(inch, y, width - inch, y)
            y -= 0.3 * inch

            # Desenha o valor total
            c.setFont("Helvetica-Bold", 12)
            c.drawString(width - 3*inch, y, f"VALOR TOTAL: R$ {ordem.valor_total:.2f}")

            c.save() # Salva o arquivo PDF
            messagebox.showinfo("Sucesso", f"Recibo PDF salvo com sucesso em:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Erro ao Salvar PDF", f"Não foi possível salvar o arquivo PDF.\nErro: {e}")

    def _atualizar_filtros_relatorio(self, event=None):
        """Mostra ou esconde os campos de filtro com base no tipo de relatório selecionado."""
        tipo_selecionado = self.relatorio_combo_tipo.get()

        # Esconde todos os filtros primeiro
        self.relatorio_lbl_produto.grid_remove()
        self.relatorio_combo_produto.grid_remove()
        self.relatorio_lbl_data_inicio.grid_remove()
        self.relatorio_entry_data_inicio.grid_remove()
        self.relatorio_lbl_data_fim.grid_remove()
        self.relatorio_entry_data_fim.grid_remove()

        # Mostra os filtros necessários para o relatório selecionado
        if tipo_selecionado == "Histórico de Movimentação por Item":
            self.relatorio_lbl_produto.grid(row=0, column=0, sticky='w', padx=5)
            self.relatorio_combo_produto.grid(row=1, column=0, sticky='ew', padx=5)
        elif tipo_selecionado == "Relatório de Vendas por Período":
            self.relatorio_lbl_data_inicio.grid(row=0, column=0, sticky='w', padx=5)
            self.relatorio_entry_data_inicio.grid(row=1, column=0, sticky='ew', padx=5)
            self.relatorio_lbl_data_fim.grid(row=2, column=0, sticky='w', padx=5, pady=(5,0))
            self.relatorio_entry_data_fim.grid(row=3, column=0, sticky='ew', padx=5)

    def _gerar_relatorio_detalhado_gui(self):
        """Chama o método apropriado do gerenciador para gerar o relatório selecionado e o exibe na tela."""
        tipo_relatorio = self.relatorio_combo_tipo.get()
        if not tipo_relatorio:
            return messagebox.showerror("Erro", "Por favor, selecione um tipo de relatório.")
        
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
                
                # Converte as strings de data para objetos datetime
                data_inicio = datetime.strptime(str_inicio, "%d/%m/%Y")
                data_fim = datetime.combine(datetime.strptime(str_fim, "%d/%m/%Y"), time.max)
                report_text = self.gerenciador.gerar_relatorio_vendas_periodo(data_inicio, data_fim)

        except ValueError as e:
            return messagebox.showerror("Erro de Filtro", str(e))
        except Exception as e:
            return messagebox.showerror("Erro Inesperado", f"Ocorreu um erro ao gerar o relatório: {e}")
            
        # Exibe o texto do relatório no widget Text
        self.txt_relatorio.delete('1.0', tk.END)
        self.txt_relatorio.insert(tk.END, report_text)
    
    def criar_oc_do_alerta(self):
        """Cria uma OC a partir de um item selecionado na lista de alertas do dashboard."""
        if not (selected_items := self.tree_alertas.selection()):
            return messagebox.showwarning("Aviso", "Selecione um item da lista de alertas primeiro.")
        
        produto_id = int(selected_items[0])
        produto = self.gerenciador.produtos.get(produto_id)
        if not produto:
            return messagebox.showerror("Erro", f"Produto com ID {produto_id} não encontrado.")

        # Muda para a aba de Ordens de Compra
        self.notebook.select(self.aba_ordens_compra)

        # Preenche o formulário da OC com os dados do produto
        self._preencher_form_oc(produto)

    def _preencher_form_oc(self, produto: Produto):
        """Função auxiliar para preencher o formulário de OC com os dados de um produto."""
        self._limpar_form_oc()

        fornecedor_str = str(produto.fornecedor)
        self.oc_fornecedor_var.set(fornecedor_str)

        produto_str = f"{produto.id} - {produto.nome}"
        self.oc_combo_produto.set(produto_str)

        self.oc_entry_quantidade.focus() # Coloca o foco no campo de quantidade
        messagebox.showinfo(
            "Formulário Preenchido",
            f"O formulário de Ordem de Compra foi preenchido para o produto '{produto.nome}'.\n\n"
            "Por favor, insira a quantidade desejada e adicione o item à ordem."
        )

    # --- Métodos de Atualização Geral ---
    def atualizar_dashboard(self):
        """Atualiza todas as informações na aba do Painel Principal."""
        valor_estoque_str = f"R$ {self.gerenciador.calcular_valor_total_estoque():,.2f}"
        self.lbl_valor_estoque.config(text=f"Valor Total do Estoque: {valor_estoque_str}")
        self.lbl_itens_unicos.config(text=f"Itens Únicos: {len(self.gerenciador.produtos)}")
        
        # Limpa e preenche novamente a tabela de alertas
        for i in self.tree_alertas.get_children():
            self.tree_alertas.delete(i)
        
        alertas = self.gerenciador.verificar_alertas_ressuprimento()
        
        tab_id = self.aba_dashboard
        if alertas:
            # Muda a cor da aba para vermelho se houver alertas
            self.notebook.tab(tab_id, text='Painel Principal (!)') # A API para mudar estilo é mais complexa, um '!' é mais simples
        else:
            self.notebook.tab(tab_id, text='Painel Principal')
            
        for p in sorted(alertas, key=lambda x: x.id):
            self.tree_alertas.insert("", "end", iid=p.id, values=(
                p.id, p.nome, p.get_estoque_total(), p.ponto_ressuprimento
            ))

    def atualizar_tabela_produtos(self):
        """Limpa e preenche novamente a tabela de produtos."""
        for i in self.tree_produtos.get_children():
            self.tree_produtos.delete(i)
        for p in sorted(self.gerenciador.produtos.values(), key=lambda x: x.id):
            preco_venda_formatado = f"R$ {p.preco_venda:,.2f}"
            self.tree_produtos.insert("", "end", iid=p.id, values=(
                p.id, p.nome, p.categoria, p.fornecedor.nome,
                p.get_estoque_total(), preco_venda_formatado
            ))
            
    def atualizar_tabela_vendas(self):
        """Limpa e preenche novamente a tabela de histórico de vendas."""
        for i in self.tree_vendas.get_children():
            self.tree_vendas.delete(i)
        for venda in sorted(self.gerenciador.vendas.values(), key=lambda v: v.id, reverse=True):
            valor_total_fmt = f"R$ {venda.valor_total:,.2f}"
            self.tree_vendas.insert("", "end", values=(
                venda.id, venda.data.strftime("%d/%m/%Y %H:%M"), venda.cliente, valor_total_fmt
            ))
        if not self.tree_vendas.selection():
            self._mostrar_itens_venda()

    def atualizar_tabela_fornecedores(self):
        """Limpa e preenche novamente a tabela de fornecedores."""
        for i in self.tree_fornecedores.get_children():
            self.tree_fornecedores.delete(i)
        for f in sorted(self.gerenciador.fornecedores.values(), key=lambda x: x.id):
            self.tree_fornecedores.insert("", "end", iid=f.id, values=(
                f.id, f.nome, f.empresa, f.telefone, f.email
            ))

    def atualizar_tabela_localizacoes(self):
        """Limpa e preenche novamente a tabela de localizações."""
        for i in self.tree_localizacoes.get_children():
            self.tree_localizacoes.delete(i)
        for loc in sorted(self.gerenciador.localizacoes.values(), key=lambda x: x.id):
            self.tree_localizacoes.insert("", "end", iid=loc.id, values=(
                loc.id, loc.nome, loc.endereco
            ))

    def atualizar_combos(self):
        """Atualiza os valores de todos os ComboBoxes da aplicação."""
        fornecedores_str = [str(f) for f in self.gerenciador.fornecedores.values()]
        localizacoes_str = [str(l) for l in self.gerenciador.localizacoes.values()]
        produtos_str = [f"{p.id} - {p.nome}" for p in self.gerenciador.produtos.values()]

        self.entries_prod["Fornecedor:"]['values'] = fornecedores_str
        self.entries_prod["Localização Inicial:"]['values'] = localizacoes_str
        self.mov_local['values'] = localizacoes_str
        self.oc_combo_fornecedor['values'] = fornecedores_str
        self.relatorio_combo_produto['values'] = produtos_str
        self.transf_produto['values'] = produtos_str
        self.transf_destino['values'] = localizacoes_str

        categorias = self.gerenciador.get_todas_categorias()
        if "--- Adicionar Nova Categoria ---" not in categorias:
            categorias.append("--- Adicionar Nova Categoria ---")
        self.entries_prod["Categoria:"]['values'] = categorias


    def atualizar_lista_ocs(self):
        """Limpa e preenche novamente a tabela de Ordens de Compra."""
        for i in self.tree_lista_ocs.get_children():
            self.tree_lista_ocs.delete(i)
        for oc in sorted(self.gerenciador.ordens_compra.values(), key=lambda x: x.id, reverse=True):
            valor_total_formatado = f"R$ {oc.valor_total:,.2f}"
            self.tree_lista_ocs.insert("", "end", values=(
                oc.id, oc.fornecedor.nome, oc.data_criacao.strftime("%d/%m/%Y"),
                valor_total_formatado, oc.status
            ))

    def _atualizar_tree_itens_nova_oc(self):
        """limpa e preenche a tabela de itens da OC que está sendo criada"""
        for i in self.tree_itens_nova_oc.get_children():
            self.tree_itens_nova_oc.delete(i)
        for item in self.itens_oc_atual:
            self.tree_itens_nova_oc.insert("", "end", iid=item['produto_id'], values=(
                item['produto_id'], item['nome'], item['quantidade'],
                f"R$ {item['preco_unitario']:.2f}", f"R$ {item['subtotal']:.2f}"
            ))

    def atualizar_tudo(self):
        """função mestre para chamar todas as outras funções de atualização para recarregar a GUI"""
        # salva as seleções atuais para restaurá-las depois da atualização
        selecao_atual_prod = self.tree_produtos.selection()
        selecao_atual_oc = self.tree_lista_ocs.selection()
        selecao_atual_forn = self.tree_fornecedores.selection()
        selecao_atual_loc = self.tree_localizacoes.selection() 

        self.atualizar_combos()
        self.atualizar_dashboard()
        self.atualizar_tabela_produtos()
        self.atualizar_tabela_vendas()
        self.atualizar_tabela_fornecedores()
        self.atualizar_lista_ocs()
        self.atualizar_tabela_localizacoes() 
        
        # tentativa de restaurar as seleções anteriores
        try:
            if selecao_atual_prod: self.tree_produtos.selection_set(selecao_atual_prod)
            if selecao_atual_oc: self.tree_lista_ocs.selection_set(selecao_atual_oc)
            if selecao_atual_forn: self.tree_fornecedores.selection_set(selecao_atual_forn)
            if selecao_atual_loc: self.tree_localizacoes.selection_set(selecao_atual_loc) 
        except tk.TclError:
            # esse erro pode acontecer se o item selecionado não existir mais, mas aí ele só ignora
            pass

# Oiiiii. Eu tentei comentar esse código o máximo possivel pra que ficasse mais facil de se entendê-lo
# Tambem tentei deixar os nomes de variáveis, funções e classes o mais descritivos possível
# Alguns dos comentários foram feitos pelo copilot, mas eu revisei todos eles 
# Mas sei que pode ter uma coisa ou outra que esteja meio estranha e confusa
# Por isso, se você tiver qualquer dúvida, pode me chamar no zap que eu respondo... em algum momento
# 82 98763-8329
# E me desculpa se voce encontrar qualquer atrocidade, é o meu jeitinho 😋