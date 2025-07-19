# main.py
# Ponto de entrada principal da aplicação de gerenciamento de estoque.
# Responsável por inicializar o banco de dados, o gerenciador de lógica
# e a interface gráfica.

import tkinter as tk
from database import DatabaseManager
from manager import GerenciadorEstoque
from gui import App
from config import DB_FILE

# pponto de entrada da aplicação, é a main ne 
if __name__ == "__main__":
    db = DatabaseManager(DB_FILE)
    db.connect()
    
    # garante que as tabelas existam no banco de dados
    db.create_tables()

    gerenciador = GerenciadorEstoque(db)
    
    gerenciador.carregar_dados_do_banco()
    
    # agora, se o banco de dados estiver vazio, ele vai popular com dados iniciais para demonstração
    if not gerenciador.fornecedores: 
        print("Banco de dados parece vazio. Populando com dados iniciais...")
        deposito = gerenciador.adicionar_localizacao(nome="Depósito Central", endereco="Rua Principal, 123")
        loja_a = gerenciador.adicionar_localizacao(nome="Loja A - Shopping", endereco="Shopping Center, Loja 15")

        asus = gerenciador.adicionar_fornecedor(
            nome="Carlos Silva", empresa="ASUS Brasil", telefone="11987654321", 
            email="carlos.silva@asus.com.br", morada="Av. Paulista, 1000, Maceió, AL"
        )
        logitech = gerenciador.adicionar_fornecedor(
            nome="Ana Pereira", empresa="Logitech BR", telefone="21912345678", 
            email="ana.pereira@logitech.com", morada="Rua da Praia, 50, Carneiros, AL"
        )
        dell = gerenciador.adicionar_fornecedor(
            nome="Maria Souza", empresa="Dell Brasil", telefone="51998761234", 
            email="maria.souza@dell.com", morada="Av. Ipiranga, 6681, Inferno, PE"
        )

        p1 = gerenciador.adicionar_produto(nome="Notebook ROG Strix", descricao="Notebook Gamer 16GB RAM, RTX 4060", categoria="Eletrônicos", fornecedor_id=asus.id, codigo_barras="789123456001", preco_compra=5000, preco_venda=7500, ponto_ressuprimento=10)
        p2 = gerenciador.adicionar_produto(nome="Mouse G502 Hero", descricao="Mouse Gamer com RGB e 25k DPI", categoria="Periféricos", fornecedor_id=logitech.id, codigo_barras="789789789002", preco_compra=250, preco_venda=450, ponto_ressuprimento=20)
        p3 = gerenciador.adicionar_produto(nome="Monitor Alienware 27''", descricao="Monitor Gamer 240Hz, QHD, Fast IPS", categoria="Eletrônicos", fornecedor_id=dell.id, codigo_barras="789456123003", preco_compra=2200, preco_venda=3800, ponto_ressuprimento=5)
        p4 = gerenciador.adicionar_produto(nome="Half-Life: Episode 3", descricao="Jogo nunca antes existido", categoria="Jogos", fornecedor_id=logitech.id, codigo_barras="789789789005", preco_compra=450, preco_venda=700, ponto_ressuprimento=15)
        
        gerenciador.movimentar_estoque(p1.id, deposito.id, 15, "Carga Inicial")
        gerenciador.movimentar_estoque(p2.id, deposito.id, 50, "Carga Inicial")
        gerenciador.movimentar_estoque(p3.id, deposito.id, 8, "Carga Inicial")
        
        gerenciador.transferir_estoque(p1.id, deposito.id, loja_a.id, 5)
        
        gerenciador.registrar_venda([{'produto_id': p1.id, 'quantidade': 2}], 'João da Silva', loja_a.id)
        
        print("Dados iniciais populados.")
        # Recarrega os dados para que a memória reflita o que foi salvo no DB
        gerenciador.carregar_dados_do_banco()


    root = tk.Tk()
    
    def on_closing():
        print("Fechando conexão com o banco de dados...")
        db.close()
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_closing) 
    
    app = App(root, gerenciador)
    root.mainloop()